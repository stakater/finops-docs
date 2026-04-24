# Subscription (reference)

## Purpose

`Subscription` ties a tenant or workload to an [Offering](./offering.md) and drives charge accrual. The operator activates the Subscription when its Offering is ready, accumulates costs tick by tick according to the Offering's pricing rules, and writes rolling cost summaries into `status.costs`. Create a Subscription for each workload or tenant that should be billed against a defined Offering.

## Scope and name constraints

`Subscription` is `namespaced`. There are no naming requirements beyond standard Kubernetes name constraints. `kubectl get subscription` shows a Ready column summarizing the Subscription's activation status.

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `offeringRef.name` | string | yes | — | Name of the [Offering](./offering.md) this Subscription is billed against. |
| `offeringRef.namespace` | string | optional | Subscription's namespace | Namespace of the Offering. Defaults to the Subscription's own namespace. |

### Activation rule

A Subscription becomes active (`ready: True`) when its Offering exists and is `Ready: True`. If the Offering is missing or not ready, the Subscription stays `Ready: False` with a descriptive reason in `status.conditions` (for example `OfferingNotFound` or `OfferingNotReady`).

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
| `current` | int64 (micro-currency) | Accumulated spend from completed ticks in the bucket so far. |
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

## Lifecycle notes

The operator maintains a finalizer on every Subscription. A finalizer is a marker that prevents Kubernetes from removing an object until the operator explicitly releases it.

**Deletion flow:** when a user deletes a Subscription, the object is not immediately removed. The operator marks it deactivated (status condition `Deleting` with reason `MarkedForDeletion`) and keeps the finalizer in place. The `SubscriptionChargeCollection` scheduled job removes the finalizer once at least `minPeriods` full ticks have elapsed since `activatedAt`. Until that threshold is reached, the condition reason is `WaitingForCollectionJob`. Once the finalizer is removed, Kubernetes garbage-collects the object.

**Deactivation snap:** `deactivatedAt` is set to the next tick boundary after the actual deactivation moment. The Subscription is charged for the full final tick — there are no partial final ticks.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

## Examples

The following example creates a Subscription for an ACME tenant, billed against the `platform-base` Offering. The Subscription activates as soon as the Offering is Ready.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-platform
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-base
```

The following illustrates what `status.costs` looks like 30 minutes after activation, before the first tick has completed. With `tickAlignment: ActivatedAt` and `period: 1h`, the first tick boundary is at `10:00:00Z`. At `09:30:00Z`, no ticks have settled yet.

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-01T09:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-01T09:00:00Z"
      endExclusive: "2026-04-01T10:00:00Z"
      current: 0               # no ticks settled yet
      projected: 40000000      # $40.00 projected for the full hour
      breakdown:
        - name: subscription
          current: 0
          projected: 40000000
    - granularity: day
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-04-02T00:00:00Z"
      current: 0               # no ticks settled yet
      projected: 560000000     # 14 full ticks until day-end × $40.00
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 0               # no ticks settled yet
      projected: 28400000000   # 710 full ticks until month-end × $40.00
```

Charges settle at tick boundaries. `current` reflects ticks that have completed inside the bucket; `projected` extrapolates the number of tick boundaries remaining until the bucket ends. Within a tick, `current` stays at its last settled value.

## Related guides

- [Subscribe to an offering](../../guides/subscribe-to-offering.md) — create a Subscription and read costs.
- [Deactivation and cleanup](../../guides/deactivation-and-cleanup.md) — what happens on delete, the snap-forward, and the `minPeriods` cleanup guard.
- [Read subscription costs](../../guides/read-subscription-costs.md) — interpreting `status.costs`.
