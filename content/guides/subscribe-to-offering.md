# Subscribe to an offering

This guide walks you through creating a `Subscription` that binds a tenant or workload to an `Offering`. When the Subscription becomes active, it begins accruing charges according to the Offering's pricing terms, and those charges appear in `status.costs`.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- An `Offering` that is `Ready: True`. See [Define an offering](./define-offering.md).
- A `CostJob` of type `SubscriptionChargeCollection` scheduled so charges are computed. See [Collect cost data](./collect-cost-data.md).
- `kubectl` access to the namespace where you will create the Subscription (typically `finops-operator-system`).

## Steps

### 1. Reference the Offering

Every Subscription must declare `spec.offeringRef.name`. This is the name of the `Offering` the Subscription binds to. The namespace defaults to the Subscription's own namespace; set `spec.offeringRef.namespace` explicitly if the `Offering` lives in a different namespace.

### 2. Understand the activation rule

A Subscription becomes active (`ready: True`) when its `Offering` exists and is `Ready: True`. If the Offering is missing or not ready, the Subscription stays `Ready: False` with a descriptive reason in `status.conditions` (for example `OfferingNotFound` or `OfferingNotReady`).

### 3. Apply the Subscription

A simple Subscription that activates as soon as the Offering is ready:

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-platform-base
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-base
```

Apply it:

```bash
kubectl apply -f subscription.yaml
```

### 4. Verify activation

Check the Subscription's readiness:

```bash
kubectl get subscription acme-platform-base -n finops-operator-system
```

Expected output:

```text
NAME                READY
acme-platform-base  True
```

For the full status:

```bash
kubectl get subscription acme-platform-base -n finops-operator-system -o yaml
```

Look for:

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-20T10:00:00Z"
```

`activatedAt` records the moment the Subscription transitioned to active. All billing calculations use this timestamp as the origin.

### 5. Read the first costs update

The `status.costs` field is populated by the `SubscriptionChargeCollection` `CostJob` on its configured schedule. After the first run following activation, you will see three rolling buckets:

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-20T10:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-20T10:00:00Z"
      endExclusive: "2026-04-20T11:00:00Z"
      current: 0
      projected: 40000000
    - granularity: day
      start: "2026-04-20T00:00:00Z"
      endExclusive: "2026-04-21T00:00:00Z"
      current: 0
      projected: 600000000
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 0
      projected: 28800000000
```

All values are in micro-currency. Divide by `1,000,000` to get the human-readable amount in your configured currency.

See [Read subscription costs](./read-subscription-costs.md) for a full explanation of the buckets and breakdown meters.

## Verify it worked

```bash
kubectl describe subscription acme-platform-base -n finops-operator-system
```

The `Conditions` section should show:

```text
Type:   Ready
Status: True
Reason: ActivationSucceeded
```

If the Subscription has not yet activated, the reason will indicate what is blocking it. Common reasons are `OfferingNotFound` and `OfferingNotReady`.

## Troubleshooting

If the Subscription stays `Ready: False`, check the condition reason and see [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Define an offering](./define-offering.md) — create the `Offering` this Subscription references.
- [Read subscription costs](./read-subscription-costs.md) — interpret `status.costs` in detail.
- [Deactivation and cleanup](./deactivation-and-cleanup.md) — understand what happens when you delete a Subscription.
- [Subscription CRD reference](../reference/crds/subscription.md)
