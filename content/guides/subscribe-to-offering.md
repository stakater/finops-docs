# Subscribe to an offering

This guide walks you through creating a `Subscription` that binds a workload to an `Offering`. When the Subscription becomes active, it begins accruing charges according to the Offering's pricing terms, and those charges appear in `status.costs`.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- An `Offering` that is `Ready: True`. See [Define an offering](./define-offering.md).
- A `CostJob` of type `SubscriptionChargeCollection` scheduled so charges are computed. See [Collect cost data](./collect-cost-data.md).
- `kubectl` access to the namespace where you will create the Subscription (typically `finops-operator-system`).

## Steps

### 1. Reference the Offering

Every Subscription must declare `spec.offeringRef.name`. This is the name of the `Offering` the Subscription binds to. The namespace defaults to the Subscription's own namespace; set `spec.offeringRef.namespace` explicitly if the `Offering` lives in a different namespace.

### 2. Optionally bind to a target resource

A Subscription can be tied to any Kubernetes resource — a `Deployment`, a `StatefulSet`, a custom resource — via `spec.lifecycle.targetRef`. When a `targetRef` is set:

- The Subscription only activates once the target resource exists and its own `status.conditions` include a `Ready` condition with `status: "True"`.
- If the target resource is deleted, the Subscription deactivates automatically.

`targetRef` accepts any Kubernetes resource by `apiVersion`, `kind`, `namespace`, and `name`. It does not need to be in the same namespace as the Subscription.

### 3. Understand the activation rule

A Subscription becomes active (`ready: True`) when all of the following hold:

1. Its `Offering` exists and is `Ready: True`.
2. If `parent.subscriptionRef` is set, the parent Subscription is active.
3. If `lifecycle.targetRef` is set, the referenced resource exists and is `Ready`.
4. If neither `parent` nor `targetRef` is set, the Subscription activates as soon as it validates.

If any condition is not met, the Subscription stays `Ready: False` with a descriptive reason in `status.conditions` (for example `OfferingNotReady`, `TargetNotFound`, or `ParentSubscriptionNotReady`).

### 4. Apply the Subscription

A Subscription tied to a `Deployment` in the `acme` namespace:

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-postgres
  namespace: finops-operator-system
spec:
  offeringRef:
    name: managed-postgres
  lifecycle:
    targetRef:
      apiVersion: apps/v1
      kind: Deployment
      namespace: acme
      name: postgres
```

Apply it:

```
kubectl apply -f subscription.yaml
```

A Subscription without a target (activates immediately, useful for platform-level charges):

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

### 5. Verify activation

Check the Subscription's readiness:

```
kubectl get subscription acme-postgres -n finops-operator-system
```

Expected output:

```
NAME           READY
acme-postgres  True
```

For the full status:

```
kubectl get subscription acme-postgres -n finops-operator-system -o yaml
```

Look for:

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-20T10:00:00Z"
```

`activatedAt` records the moment the Subscription transitioned to active. All billing calculations use this timestamp as the origin.

### 6. Read the first costs update

The `status.costs` field is populated by the `SubscriptionChargeCollection` `CostJob` on its configured schedule. After the first run following activation, you will see three rolling buckets:

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-20T10:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-20T10:00:00Z"
      endExclusive: "2026-04-20T11:00:00Z"
      current: 20000000
      projected: 40000000
    - granularity: day
      start: "2026-04-20T00:00:00Z"
      endExclusive: "2026-04-21T00:00:00Z"
      current: 20000000
      projected: 600000000
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 20000000
      projected: 28800000000
```

All values are in micro-currency. Divide by `1,000,000` to get the human-readable amount in your configured currency.

See [Read subscription costs](./read-subscription-costs.md) for a full explanation of the buckets and breakdown meters.

## Verify it worked

```
kubectl describe subscription acme-postgres -n finops-operator-system
```

The `Conditions` section should show:

```
Type:   Ready
Status: True
Reason: ActivationSucceeded
```

If the Subscription has not yet activated, the reason will indicate what is blocking it. Common reasons are `OfferingNotFound`, `OfferingNotReady`, and `TargetNotFound`.

## Troubleshooting

If the Subscription stays `Ready: False`, check the condition reason and see [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Define an offering](./define-offering.md) — create the `Offering` this Subscription references.
- [Parent-child subscriptions](./parent-child-subscriptions.md) — link Subscriptions together for traceability and lifecycle cascading.
- [Read subscription costs](./read-subscription-costs.md) — interpret `status.costs` in detail.
- [Deactivation and cleanup](./deactivation-and-cleanup.md) — understand what happens when you delete a Subscription.
- [Subscription CRD reference](../reference/crds/subscription.md)
