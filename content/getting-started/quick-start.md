# Quick start

This walk-through goes from a fresh cluster to a Subscription whose `status.costs` carries charges. Every resource below is created in `finops-operator-system`, the namespace the rest of the documentation assumes.

## Prerequisites

- A cluster with `cluster-admin`, plus `kubectl` and the Helm CLI.
- cert-manager, because the chart issues the webhook serving certificate through it.
- A reachable PostgreSQL database and a reachable OpenCost instance. [Installation overview](installation/overview.md) explains what each one is used for, and how the chart can bring both up for you.

## 1. Install the operator

Create the namespace and the two Secrets the controller mounts by name, then install the chart. Neither `secretKeyRef` is optional, so the controller pod does not start until both Secrets exist.

```sh
kubectl create namespace finops-operator-system

kubectl create secret generic finops-operator-postgres-config \
  --namespace finops-operator-system \
  --from-literal=POSTGRES_CONNECTION_STRING='postgres://finops:PASSWORD@postgres.example.svc:5432/finops?sslmode=require'

kubectl create secret generic finops-operator-opencost-config \
  --namespace finops-operator-system \
  --from-literal=OPENCOST_CONNECTION_STRING='http://opencost.opencost.svc:9003'

helm install finops-operator oci://ghcr.io/stakater/public/charts/finops-operator \
  --namespace finops-operator-system
```

```sh
kubectl get deployment -n finops-operator-system
```

`finops-operator-controller-manager` and `finops-operator-finops-gateway-gateway` both report their replicas available once the install has settled. A default install creates no `PriceBook`, `CostJob`, or `FinOpsProvider`, so nothing is priced or collected until you author them below. [On Kubernetes](installation/kubernetes.md) covers the chart values, the OpenShift variant, and what to read when a pod will not start.

## 2. Create a PriceBook

A `PriceBook` holds per-unit rates. The operator renders the active book into OpenCost's custom pricing document, and a metered Offering resolves its prices from it. The `finops.stakater.com/active` annotation is how you choose which book is active.

```yaml
# pricebook.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: PriceBook
metadata:
  name: onprem-pricing
  namespace: finops-operator-system
  annotations:
    finops.stakater.com/active: "true"
spec:
  currency: USD
  valuationMode: currency
  rates:
    cpuHour: "0.031"
    ramGbHour: "0.004"
    pvGbHour: "0.00012"
    gpuHour: "1.80"
    networkGiB: "0.09"
```

```sh
kubectl apply -f pricebook.yaml
kubectl get pricebook -n finops-operator-system
```

The `ACTIVE` column reads `true` on the book the operator selected, and `READY` reads `True` once its rates parsed. [Define pricing](../guides/define-pricing.md) walks through the rates, and [PriceBook](../concepts/pricebook.md) explains all three selection tiers and why a namespace that collects allocations should hold only one book.

## 3. Create a FinOpsProvider

`FinOpsProvider` records where the cluster runs. It is cluster-scoped and there is exactly one of it: CEL rules on the CRD require the name `default` and exactly one option block.

```yaml
# finopsprovider.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  onpremoptions:
    pricingModelSource: Pricebook
```

```sh
kubectl apply -f finopsprovider.yaml
kubectl get finopsprovider default
```

This reconciler writes no status, so the object existing is all `kubectl get` reports; the controller log is where an applied provider shows up. Outside Multi Tenant Operator mode the provider also changes nothing about pricing on its own, since the pricing document is written by the PriceBook reconciler. [FinOpsProvider](../concepts/finops-provider.md) covers the four option blocks and what each one switches on.

## 4. Collect resource costs

A `CostJob` of type `ResourceCostCollection` pulls hourly allocation rows from OpenCost and stores them, priced from a PriceBook in its own namespace.

```yaml
# costjob-resource.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: resource-cost-collection
  namespace: finops-operator-system
spec:
  type: ResourceCostCollection
  interval: 1h
```

```sh
kubectl apply -f costjob-resource.yaml
kubectl get cronjob -n finops-operator-system
```

The operator generates a CronJob named `resource-cost-collection-cronjob` in the CostJob's namespace, and `interval: 1h` becomes the schedule `0 * * * *`. [Collect cost data](../guides/collect-cost-data.md) covers what a run reads and writes, and [CostJob](../concepts/costjob.md) lists the intervals that map to a schedule of their own.

## 5. Create an Offering

An `Offering` is the priced thing. Its spec is immutable once created, enforced by a CEL rule, so pricing changes mean a new Offering rather than an edit.

```yaml
# offering.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: platform-base
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 40000000
```

```sh
kubectl apply -f offering.yaml
kubectl get offering -n finops-operator-system
```

`priceMicros` is micro-currency in the PriceBook's currency, where 1,000,000 is 1.00, so this Offering charges 40.00 per tick and `period` with `tickAlignment: ActivatedAt` puts a tick boundary one hour after each Subscription activates. It prices no metered resources, so its `READY` column reaches `True` without needing a rate from the PriceBook. [Define an offering](../guides/define-offering.md) covers tick alignment, `minPeriods`, and compatibility requirements.

## 6. Create a Subscription

A `Subscription` binds a subscriber to the Offering and starts the clock.

```yaml
# subscription.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: my-platform-sub
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-base
    namespace: finops-operator-system
```

```sh
kubectl apply -f subscription.yaml
kubectl get subscription -n finops-operator-system
```

`offeringRef.namespace` is required and is never filled in from the Subscription's own namespace, so set it on every reference. The `READY` column reaches `True` once all four activation gates pass, which for a Subscription with no parent, no target, and an Offering that requires nothing means as soon as that Offering is ready. Activation stamps `status.activatedAt`, and every charge is computed from it. [Subscription](../concepts/subscription.md) describes the gates; [subscribe to an offering](../guides/subscribe-to-offering.md) covers parents, usage sources, and targets.

## 7. Collect subscription charges

A second `CostJob`, of type `SubscriptionChargeCollection`, computes each Subscription's charges, writes `status.costs`, and releases the finalizer of a Subscription that has been deleted. Nothing else does those three things, so a cluster without this CostJob accrues no readable charges and never finishes deleting a Subscription.

```yaml
# costjob-charges.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: subscription-charge-collection
  namespace: finops-operator-system
spec:
  type: SubscriptionChargeCollection
  interval: 1h
```

```sh
kubectl apply -f costjob-charges.yaml
kubectl get cronjob subscription-charge-collection-cronjob -n finops-operator-system
```

This CronJob also runs on `0 * * * *`, so `status.costs` is written on its first run at the top of the hour.

## 8. Read the charges

```sh
kubectl get subscription my-platform-sub -n finops-operator-system -o yaml
```

The figures below are illustrative, for a Subscription activated four hours earlier. Run the command straight after the previous step and you will see no `costs` at all until the charge collector's first run, and near-zero `current` values for a while after that.

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-01T09:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-01T13:00:00Z"
      endExclusive: "2026-04-01T14:00:00Z"
      projected: 40000000
      breakdown:
        - name: subscription
          projected: 40000000
    - granularity: day
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-04-02T00:00:00Z"
      current: 160000000
      projected: 600000000
      breakdown:
        - name: subscription
          current: 160000000
          projected: 600000000
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 160000000
      projected: 28440000000
      breakdown:
        - name: subscription
          current: 160000000
          projected: 28440000000
```

There are always exactly three buckets, one per granularity, each covering the window from `start` to `endExclusive`. `current` is what has settled inside that window and `projected` is the figure for the whole of it, both in micro-currency, and `breakdown` splits them by meter, where `subscription` is the Offering's recurring fee. Zero values are omitted from the object, so a bucket with nothing settled yet shows only its window and its projection. [Read subscription costs](../guides/read-subscription-costs.md) works through how each figure is arrived at.

## Next

- [Read subscription costs](../guides/read-subscription-costs.md) to interpret the buckets above.
- [Price resource usage](../guides/price-resource-usage.md) to charge for measured consumption as well as a fee.
- [Architecture](../concepts/architecture.md) for what the controller and the generated CronJobs each do.
- [Uninstalling](uninstalling.md) for the order to tear this down in.
