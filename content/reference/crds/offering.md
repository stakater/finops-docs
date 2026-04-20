# Offering (reference)

## Purpose

`Offering` defines a billable service that tenants can subscribe to. It sets the recurring subscription fee, the tick interval and alignment that determine when charges accrue, optional minimum commitment periods, and compatibility constraints that gate which other Offerings must be present before this one can be activated. Create an Offering for each distinct service tier or add-on you want to make available; tenants then create [Subscriptions](./subscription.md) against it.

## Scope and name constraints

`Offering` is namespaced. The `spec` is immutable: once created, no field may be changed. To revise pricing or compatibility rules, create a new Offering and point new Subscriptions at it. Deletion is blocked while any Subscription or other Offering still references this one. `kubectl get offering` shows a Ready column summarizing the Offering's activation status.

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `pricing.subscriptionFee` | object | required in practice | — | Recurring fee that accrues while a Subscription is active. See subsection below. |
| `compatibility.requiredOfferings` | list of object references | optional | — | Other Offerings that must be present (and ready) before this Offering can be subscribed to. See subsection below. |
| `lifecycle.onParentDeactivate` | enum | optional | `Deactivate` | Default behavior for child Subscriptions when their parent deactivates. One of `Deactivate` or `Orphan`. |
| `lifecycle.allowOverride` | boolean | optional | `false` | Whether a Subscription referencing this Offering may set its own `lifecycle.onParentDeactivate`. |

> **Note:** `lifecycle.allowOverride` is accepted by the API but is not currently enforced. A Subscription that sets its own `lifecycle.onParentDeactivate` takes precedence over the Offering's policy regardless of this field's value.

### pricing.subscriptionFee

| Field | Type | Required | Validation | Description |
|---|---|---|---|---|
| `priceMicros` | int64 | yes | minimum `1` | Price charged per tick, in micro-currency units. `1000000` equals 1.00 of the configured currency (e.g. `40000000` = $40.00). |
| `period` | string | yes | Format depends on `tickAlignment` (see below) | The tick interval. |
| `tickAlignment` | enum | yes | One of `ActivatedAt`, `HourBoundary`, `DayBoundary`, `MonthBoundary` | Where tick boundaries fall relative to the Subscription's activation time. |
| `minPeriods` | int32 | optional | minimum `1` | Minimum number of full ticks that must elapse after activation before the operator releases a deleted Subscription. This is a cleanup guard, not a billing mechanism — charges accrue normally during this time. |

#### Period format by tick alignment

The format of `period` depends on `tickAlignment`. Values that do not match the required format are rejected at admission.

| `tickAlignment` | `period` format | Examples | Behavior |
|---|---|---|---|
| `ActivatedAt` | Go-style duration (hours, minutes, seconds) | `1h`, `30m`, `24h`, `90s` | Tick boundaries at `activatedAt + N × period`. No proration; every tick is a full period. |
| `HourBoundary` | Integer number of hours | `"1"`, `"2"`, `"6"` | Tick boundaries at wall-clock hour boundaries (`HH:00:00`). First tick is prorated. |
| `DayBoundary` | Integer number of days | `"1"`, `"7"`, `"30"` | Tick boundaries at 00:00 UTC each day. First tick is prorated. |
| `MonthBoundary` | Integer number of months | `"1"`, `"3"`, `"12"` | Tick boundaries at 00:00 UTC on the 1st of each month. First tick is prorated using a fixed 30-day-10-hour-30-minute denominator per month. |

### compatibility.requiredOfferings

Each entry in `compatibility.requiredOfferings` is an object reference with the following fields.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Name of the required Offering. |
| `namespace` | string | optional | Namespace of the required Offering. Defaults to the namespace of the referencing Offering. |

## Status

| Field | Type | Description |
|---|---|---|
| `ready` | `True` / `False` / `Unknown` | Whether this Offering is ready to be subscribed to. `True` means all required Offerings are present and ready and no circular dependency exists. |
| `conditions` | list | Standard Kubernetes conditions. See the Ready and Deleting condition reasons below. |

## Validation rules

- `spec` is immutable. Any attempt to modify it after creation is rejected and surfaces the condition reason `SpecImmutable`.
- Exactly one of the tick alignment values (`ActivatedAt`, `HourBoundary`, `DayBoundary`, `MonthBoundary`) must be set in `tickAlignment`.
- `period` must match the format required by the chosen `tickAlignment` (duration string vs. plain integer).
- `priceMicros` must be at least `1`.
- `minPeriods`, when set, must be at least `1`.
- Self-references in `compatibility.requiredOfferings` (an Offering listing itself) are rejected at admission.
- Cycles in the `requiredOfferings` graph are rejected at admission; the reason `CircularDependencyDetected` is set on the Offering's Ready condition.
- Deleting an Offering while any Subscription or other Offering references it is rejected.

## Lifecycle notes

The operator maintains a finalizer (a marker that prevents Kubernetes from garbage-collecting the object until the operator is done with it) on every Offering. This allows the operator to block deletion while dependents exist.

When a required Offering is missing or not yet ready, this Offering is marked `Ready: False` with one of the reasons `RequiredOfferingNotFound`, `RequiredOfferingNotReady`, or `CircularDependencyDetected`. Once the dependency becomes ready, the operator reconciles this Offering back to `Ready: True`. This transient not-ready state is expected during rollout.

When this Offering's `status.ready` is `False`, [Subscriptions](./subscription.md) referencing it will not activate.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

For how ticks are counted and how the first tick is prorated by alignment, see the [Billing model](../../concepts/billing-model.md) concept page.

## Examples

The following example creates an hourly Offering with a $40.00 per-hour fee, activated at subscription time, with a two-hour minimum period, requiring the `platform-base` Offering to be present.

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
  compatibility:
    requiredOfferings:
      - name: platform-base
  lifecycle:
    onParentDeactivate: Deactivate
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

- [Define an offering](../../guides/define-offering.md) — immutability, the subscriptionFee block, and `minPeriods`.
- [Required offerings](../../guides/required-offerings.md) — composition via `compatibility.requiredOfferings`.
