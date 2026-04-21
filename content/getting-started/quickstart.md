# Quickstart

This is a 15-minute walk-through that takes you from a fresh install to an active Subscription with populated `status.costs`. By the end, the operator is collecting resource cost data, an Offering has a recurring fee, and a Subscription is accruing charges you can read back from its status. The walk-through assumes the operator is already installed as described in [Installation](./installation.md).

All resources in this guide are created in the `finops-operator-system` namespace.

---

## Step 1: Install the prerequisites

Confirm the following are in place before proceeding:

- **cert-manager** is installed and its pods are running.
- **OpenCost** is reachable from the cluster (either BYO or MDO-managed).
- **PostgreSQL** is reachable and the `finops-operator-postgres-config` Secret exists in `finops-operator-system`.

See [Prerequisites](./prerequisites.md) for installation guidance on each component.

---

## Step 2: Install the operator

If you have not installed the operator yet, follow [Installation](./installation.md). Confirm it is running:

```bash
kubectl get deployment -n finops-operator-system
```

You should see `finops-operator-controller-manager` with all replicas ready before continuing.

---

## Step 3: Create a FinOpsProvider

The `FinOpsProvider` is a cluster-scoped singleton that tells the operator which environment it is running in and how pricing reaches OpenCost. It must be named exactly `default`.

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

Apply it:

```bash
kubectl apply -f finopsprovider.yaml
```

Confirm it synced:

```bash
kubectl get finopsprovider default
```

You should see a `lastSyncTime` in the status within a few seconds, indicating the operator has pushed the configuration to OpenCost.

---

## Step 4: Create a PriceBook

The `PriceBook` defines per-resource rates that OpenCost uses to cost raw allocation data. Setting `valuationMode: currency` and providing rates in the `currency` you choose activates the custom pricing path.

```yaml
# pricebook.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: PriceBook
metadata:
  name: onprem-pricing
  namespace: finops-operator-system
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

Apply it:

```bash
kubectl apply -f pricebook.yaml
```

Confirm the PriceBook is active:

```bash
kubectl get pricebook -n finops-operator-system
```

The `active` field in the status becomes `true` once the operator has written the pricing configuration to OpenCost.

---

## Step 5: Create a CostJob for resource cost collection

A `CostJob` of type `ResourceCostCollection` tells the operator how often to pull allocation data from OpenCost and store it for later reporting. The operator converts the `interval` to a Kubernetes `CronJob` that runs on that schedule.

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

Apply it:

```bash
kubectl apply -f costjob-resource.yaml
```

The operator creates a `CronJob` in the operator's namespace that runs at the top of every hour (`0 * * * *`). You can verify it appeared:

```bash
kubectl get cronjob -n finops-operator-system
```

---

## Step 6: Create an Offering

An `Offering` defines a named pricing contract — a recurring fee that any Subscription can accrue. The spec is immutable after creation; to change pricing, create a new Offering.

The example below charges USD 40.00 per hour (`40000000` micro-currency, where `1,000,000` = USD 1.00), with tick boundaries anchored to the moment the Subscription activates.

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
      priceMicros: 40000000   # USD 40.00 per hour
```

Apply it:

```bash
kubectl apply -f offering.yaml
```

Confirm the Offering is ready:

```bash
kubectl get offering -n finops-operator-system
```

The `READY` column should show `True`. A value of `False` means a required Offering is missing or not yet ready — expected during reconciliation, and recovers automatically once dependencies are satisfied.

---

## Step 7: Create a Subscription

A `Subscription` binds a workload or tenant to an Offering and starts accruing charges. Because this Subscription has no `parent` and no `lifecycle.targetRef`, it activates as soon as the referenced Offering is ready.

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
```

Apply it:

```bash
kubectl apply -f subscription.yaml
```

Confirm it is active:

```bash
kubectl get subscription -n finops-operator-system
```

The `READY` column should show `True` within a few seconds, and `status.activatedAt` is set to the moment the Subscription became active.

---

## Step 8: Create a CostJob for subscription charge collection

A `CostJob` of type `SubscriptionChargeCollection` tells the operator how often to compute per-Subscription charges and update each active Subscription's `status.costs`. It also handles cleanup of deleted Subscriptions once their `minPeriods` guard has elapsed.

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

Apply it:

```bash
kubectl apply -f costjob-charges.yaml
```

The operator creates a second `CronJob` that runs at the top of every hour. After the first run, `status.costs` on your Subscription is populated.

---

## Step 9: Inspect status.costs

After the `SubscriptionChargeCollection` job runs (up to 1 hour after you created it), fetch the Subscription and inspect the costs:

```bash
kubectl get subscription my-platform-sub -n finops-operator-system -o yaml
```

The `status.costs` field contains exactly three rolling buckets: `hour`, `day`, and `month`. Here is a trimmed example of what you will see:

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-20T09:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-20T09:00:00Z"
      endExclusive: "2026-04-20T10:00:00Z"
      current: 20000000        # USD 20.00 accrued so far this hour
      projected: 40000000      # USD 40.00 projected for the full hour
      breakdown:
        - name: subscription
          current: 20000000
          projected: 40000000
    - granularity: day
      start: "2026-04-20T00:00:00Z"
      endExclusive: "2026-04-21T00:00:00Z"
      current: 20000000        # USD 20.00 since midnight
      projected: 960000000     # USD 960.00 projected for the full day (24 hours × USD 40)
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 20000000        # USD 20.00 since the first of the month
      projected: 28800000000   # USD 28,800 projected for the full month (30 days × 24h × USD 40)
```

How to read the three buckets:

- **`hour`** — the current calendar hour. `current` is what has accrued since the hour started. `projected` is the estimated total if the Subscription stays active for the full hour.
- **`day`** — the current calendar day from midnight to midnight. `projected` accounts for remaining hours.
- **`month`** — the current calendar month. `projected` is based on the remaining days in the month.

All values are in micro-currency. Divide by `1,000,000` to get the amount in the PriceBook's currency (USD in this example). The `breakdown` list names individual meters; `subscription` is the recurring fee from the Offering's `subscriptionFee`.

---

## What you did

You installed the operator, defined an on-premises pricing model with a `FinOpsProvider` and a `PriceBook`, configured hourly resource cost collection with a `CostJob`, created a paid capability with an `Offering`, subscribed to it with a `Subscription`, and configured hourly charge computation with a second `CostJob`. The Subscription's `status.costs` now shows rolling hour, day, and month buckets with the accumulated and projected charges.

## Next

- [Concepts](../concepts/index.md) — understand the mental model behind the five CRDs.
- [Define an offering](../guides/define-offering.md) — learn about tick alignment, immutability, and lifecycle rules.
- [Parent-child subscriptions](../guides/parent-child-subscriptions.md) — model hierarchical billing relationships.
- [Subscription CRD reference](../reference/crds/subscription.md) — full field reference including all status fields.
