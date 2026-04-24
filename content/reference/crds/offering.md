# Offering (reference)

## Purpose

`Offering` defines a billable service that tenants can subscribe to. It sets the recurring subscription fee and the tick interval and alignment that determine when charges accrue. Create an Offering for each distinct service tier or add-on you want to make available; tenants then create [Subscriptions](./subscription.md) against it.

## Scope and name constraints

`Offering` is `namespaced`. The `spec` is immutable: once created, no field may be changed. To revise pricing, create a new Offering and point new Subscriptions at it. Deletion is blocked while any Subscription still references this one. `kubectl get offering` shows a Ready column summarizing the Offering's activation status.

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `pricing.subscriptionFee` | object | required in practice | — | Recurring fee that accrues while a Subscription is active. See subsection below. |

### pricing.subscriptionFee

| Field | Type | Required | Validation | Description |
|---|---|---|---|---|
| `priceMicros` | int64 | yes | minimum `1` | Price charged per tick, in micro-currency units. `1000000` equals 1.00 of the configured currency (e.g. `40000000` = $40.00). |
| `period` | string | yes | Format depends on `tickAlignment` (see below) | The tick interval. |
| `tickAlignment` | `enum` | yes | One of `ActivatedAt`, `HourBoundary`, `DayBoundary`, `MonthBoundary` | Where tick boundaries fall relative to the Subscription's activation time. |
| `minPeriods` | int32 | optional | minimum `1` | Minimum number of full ticks that must elapse after activation before the operator releases a deleted Subscription. This is a cleanup guard, not a billing mechanism — charges accrue normally during this time. |

#### Period format by tick alignment

The format of `period` depends on `tickAlignment`. Values that do not match the required format are rejected at admission.

| `tickAlignment` | `period` format | Examples | Behavior |
|---|---|---|---|
| `ActivatedAt` | Go-style duration (hours, minutes, seconds) | `1h`, `30m`, `24h`, `90s` | Tick boundaries at `activatedAt + N × period`. No proration; every tick is a full period. |
| `HourBoundary` | Integer number of hours | `"1"`, `"2"`, `"6"` | Tick boundaries at wall-clock hour boundaries (`HH:00:00`). First tick is prorated. |
| `DayBoundary` | Integer number of days | `"1"`, `"7"`, `"30"` | Tick boundaries at 00:00 UTC each day. First tick is prorated. |
| `MonthBoundary` | Integer number of months | `"1"`, `"3"`, `"12"` | Tick boundaries at 00:00 UTC on the 1st of each month. First tick is prorated using a fixed 30-day-10-hour-30-minute denominator per month. |

## Status

| Field | Type | Description |
|---|---|---|
| `ready` | `True` / `False` / `Unknown` | Whether this Offering is ready to be subscribed to. |
| `conditions` | list | Standard Kubernetes conditions. See the Ready and Deleting condition reasons below. |
| `resolvedPricing` | object | Effective pricing the operator derived from the Offering spec after resolution. Present once the Offering becomes Ready. See subsection below. |

### resolvedPricing

| Field | Type | Description |
|---|---|---|
| `meters` | list of object | Per-meter resolved unit prices. Empty when no resource pricing is configured. Today the `subscription` meter is populated from `spec.pricing.subscriptionFee`. |
| `resolvedAt` | timestamp | When pricing was last resolved. |
| `subscriptionFee` | object | Resolved subscription fee, if configured. Same schema as `spec.pricing.subscriptionFee`. |

#### resolvedPricing.meters[]

Each entry in `meters` reports the effective price for one meter.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `enum` | yes | Meter name. One of: `subscription`, `cpuHour`, `gpuHour`, `ramGbHour`, `pvcGbHour`, `networkIngressGbHour`, `networkEgressGbHour`. |
| `unitPriceMicros` | int64 | yes | Effective per-unit price in micro-currency units (10^-6). |
| `includedUsage` | object | optional | Free usage included per subscription for this meter. Contains `unit` (string, e.g. `"GbHour"`, `"CoreHour"`) and `value` (int64). |

## Validation rules

- `spec` is immutable. Any attempt to modify it after creation is rejected and surfaces the condition reason `SpecImmutable`.
- Exactly one of the tick alignment values (`ActivatedAt`, `HourBoundary`, `DayBoundary`, `MonthBoundary`) must be set in `tickAlignment`.
- `period` must match the format required by the chosen `tickAlignment` (duration string vs. plain integer).
- `priceMicros` must be at least `1`.
- `minPeriods`, when set, must be at least `1`.
- Deleting an Offering while any Subscription references it is rejected.

## Lifecycle notes

The operator maintains a finalizer (a marker that prevents Kubernetes from garbage-collecting the object until the operator is done with it) on every Offering. This allows the operator to block deletion while dependents exist.

When this Offering's `status.ready` is `False`, [Subscriptions](./subscription.md) referencing it will not activate.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

For how ticks are counted and how the first tick is prorated by alignment, see the [Billing model](../../concepts/billing-model.md) concept page.

## Examples

The following example creates an hourly Offering with a $40.00 per-hour fee, activated at subscription time, with a two-hour minimum period.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: managed-postgres
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      minPeriods: 2
      priceMicros: 40000000   # $40.00 per hour
```

The following example creates a monthly Offering, wall-clock aligned to the 1st of each month, at $500.00 per month.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: platform-base
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: "1"
      tickAlignment: MonthBoundary
      priceMicros: 500000000   # $500.00 per month
```

## Related guides

- [Define an offering](../../guides/define-offering.md) — immutability, the `subscriptionFee` block, and `minPeriods`.
