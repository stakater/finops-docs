# Subscription (reference)

## Purpose

`Subscription` ties a tenant workload to an [Offering](./offering.md) and drives charge accrual. The operator activates the Subscription when its prerequisites are met, accumulates costs tick by tick according to the Offering's pricing rules, and writes rolling cost summaries into `status.costs`. Create a Subscription for each workload or tenant that should be billed against a defined Offering.

## Scope and name constraints

`Subscription` is `namespaced`. There are no naming requirements beyond standard Kubernetes name constraints. A Subscription cannot reference itself as its own parent, and cannot point `lifecycle.targetRef` at itself — both are enforced at admission (create time only). `kubectl get subscription` shows a Ready column summarizing the Subscription's activation status.

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `offeringRef.name` | string | yes | — | Name of the [Offering](./offering.md) this Subscription is billed against. |
| `offeringRef.namespace` | string | optional | Subscription's namespace | Namespace of the Offering. Defaults to the Subscription's own namespace. |
| `parent.subscriptionRef.name` | string | optional | — | Name of the parent Subscription, for traceability and lifecycle cascading. |
| `parent.subscriptionRef.namespace` | string | optional | Subscription's namespace | Namespace of the parent Subscription. |
| `lifecycle.onParentDeactivate` | `enum` | optional | Offering's policy, then `Deactivate` | How this Subscription behaves when its parent deactivates. One of `Deactivate` or `Orphan`. Overrides the Offering's `lifecycle.onParentDeactivate` when set. |
| `lifecycle.targetRef.apiVersion` | string | optional | — | API version of the Kubernetes resource whose existence gates activation. |
| `lifecycle.targetRef.kind` | string | optional | — | Kind of the target resource. |
| `lifecycle.targetRef.namespace` | string | optional | — | Namespace of the target resource. |
| `lifecycle.targetRef.name` | string | optional | — | Name of the target resource. |

### Effective onParentDeactivate precedence

The effective `onParentDeactivate` policy is resolved in this order:

1. `Subscription.spec.lifecycle.onParentDeactivate` (if set on this Subscription).
1. `Offering.spec.lifecycle.onParentDeactivate` (from the referenced Offering).
1. `Deactivate` (the built-in default).

### Activation rule

A Subscription becomes active (`ready: True`) when all of the following are satisfied:

- Its Offering exists and is `Ready: True`.
- If `parent.subscriptionRef` is set, the parent Subscription is active.
- If `lifecycle.targetRef` is set, the referenced Kubernetes resource exists and is `Ready`.
- If neither `parent` nor `targetRef` is set, the Subscription activates as soon as it validates.

### Deactivation triggers

- The parent Subscription deactivates and the effective `onParentDeactivate` policy is `Deactivate`. If the policy is `Orphan`, this Subscription stays active.
- The resource referenced by `lifecycle.targetRef` disappears.
- The user deletes the Subscription (see lifecycle notes below for what happens next).

## Status

| Field | Type | Description |
|---|---|---|
| `ready` | `True` / `False` / `Unknown` | Whether the Subscription is currently active. |
| `activatedAt` | timestamp | When the Subscription first became active. |
| `deactivatedAt` | timestamp | When the Subscription was deactivated. Snapped forward to the next tick boundary so there are never partial final ticks. |
| `costs` | list | Rolling cost summary, containing up to three buckets: `hour`, `day`, `month`. Populated by the `SubscriptionChargeCollection` job. |
| `conditions` | list | Standard Kubernetes conditions. |

### costs (CostBucket)

When populated, `status.costs` contains exactly three entries, one per granularity.

| Field | Type | Description |
|---|---|---|
| `granularity` | `enum` | One of `hour`, `day`, `month`. |
| `start` | timestamp | Inclusive start of the bucket. |
| `endExclusive` | timestamp | Exclusive end of the bucket. |
| `current` | int64 (micro-currency) | Accumulated spend in the bucket so far. |
| `projected` | int64 (micro-currency) | Projected spend for the full bucket period. |
| `breakdown` | list | Per-meter cost entries. Omitted when there is nothing to report. |

### breakdown (CostMetric)

Each entry in `breakdown` reports costs for one meter.

| Field | Type | Description |
|---|---|---|
| `name` | `enum` | Meter name. One of: `subscription`, `cpuHour`, `gpuHour`, `ramGbHour`, `pvcGbHour`, `networkIngressGbHour`, `networkEgressGbHour`. |
| `current` | int64 (micro-currency) | Accumulated cost for this meter in the current bucket. |
| `projected` | int64 (micro-currency) | Projected cost for this meter for the full bucket period. |

**Meter meanings:**

- `subscription` — the Offering's recurring subscription fee, accruing tick by tick.
- `cpuHour` — CPU usage (vCPU-hours).
- `gpuHour` — GPU usage (GPU-hours).
- `ramGbHour` — RAM usage (GB-hours).
- `pvcGbHour` — persistent-volume usage (GB-hours).
- `networkIngressGbHour` / `networkEgressGbHour` — network transfer.

The `subscription` meter is always populated when the Offering has a `subscriptionFee`. Whether resource meters (`cpuHour`, etc.) are populated depends on what the scheduled `ResourceCostCollection` job has computed.

## Validation rules

- `offeringRef.name` is required.
- A Subscription cannot reference itself as its own parent (`parent.subscriptionRef` pointing to itself).
- `lifecycle.targetRef` cannot point to the Subscription itself.
- Self-reference checks are enforced at create time only; updates and deletes are not checked.
- `lifecycle.onParentDeactivate` must be one of `Deactivate` or `Orphan` when set.

## Lifecycle notes

The operator maintains a finalizer on every Subscription. A finalizer is a marker that prevents Kubernetes from removing an object until the operator explicitly releases it.

**Deletion flow:** when a user deletes a Subscription, the object is not immediately removed. The operator marks it deactivated (status condition `Deleting` with reason `MarkedForDeletion`) and keeps the finalizer in place. The `SubscriptionChargeCollection` scheduled job removes the finalizer once at least `minPeriods` full ticks have elapsed since `activatedAt`. Until that threshold is reached, the condition reason is `WaitingForCollectionJob`. Once the finalizer is removed, Kubernetes garbage-collects the object.

**Parent deactivation cascade:** when a parent Subscription deactivates, child Subscriptions with the effective policy `Deactivate` are also deactivated (reason `ParentDeactivated`). Children with the effective policy `Orphan` remain active (reason `Orphaned`).

**Deactivation snap:** `deactivatedAt` is set to the next tick boundary after the actual deactivation moment. The Subscription is charged for the full final tick — there are no partial final ticks.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

## Examples

The following example creates a Subscription for a PostgreSQL deployment in the `acme` namespace, billed against the `managed-postgres` Offering. The Subscription activates when the referenced Deployment exists and is ready.

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

The following example creates a child Subscription for add-on storage, linked to the `acme-postgres` parent Subscription, with an `Orphan` policy so that it remains active if the parent deactivates.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-postgres-storage
  namespace: finops-operator-system
spec:
  offeringRef:
    name: managed-postgres-storage
  parent:
    subscriptionRef:
      name: acme-postgres
  lifecycle:
    onParentDeactivate: Orphan
```

The following illustrates what `status.costs` looks like after the `SubscriptionChargeCollection` job has run for an hourly $40.00 Offering activated at 09:00 UTC.

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-01T09:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-01T09:00:00Z"
      endExclusive: "2026-04-01T10:00:00Z"
      current: 20000000        # $20.00 accumulated so far this hour
      projected: 40000000      # $40.00 projected for the full hour
      breakdown:
        - name: subscription
          current: 20000000
          projected: 40000000
    - granularity: day
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-04-02T00:00:00Z"
      current: 20000000
      projected: 600000000     # $600.00 projected for the full day
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 20000000
      projected: 28800000000   # $28,800.00 projected for the full month
```

## Related guides

- [Subscribe to an offering](../../guides/subscribe-to-offering.md) — create a Subscription, link to a workload, and read costs.
- [Parent-child subscriptions](../../guides/parent-child-subscriptions.md) — hierarchy and the Deactivate vs Orphan choice.
- [Deactivation and cleanup](../../guides/deactivation-and-cleanup.md) — what happens on delete, the snap-forward, and the `minPeriods` cleanup guard.
- [Read subscription costs](../../guides/read-subscription-costs.md) — interpreting `status.costs`.
