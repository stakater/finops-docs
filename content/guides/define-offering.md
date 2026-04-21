# Define an offering

This guide explains how to create an `Offering` — a named, immutable pricing contract for a service or workload. By the end, you will have an `Offering` that Subscriptions can reference to accrue recurring charges.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- A `PriceBook` in place. See [Define pricing](./define-pricing.md).
- A `CostJob` of type `SubscriptionChargeCollection` scheduled so charges are computed. See [Collect cost data](./collect-cost-data.md).
- `kubectl` access to the operator namespace (typically `finops-operator-system`).

## Offering immutability

An `Offering`'s `spec` is immutable: once created, you cannot change its pricing, lifecycle defaults, or compatibility rules. If you need different terms, create a new `Offering` with a new name and migrate new Subscriptions to it. Old Subscriptions continue using the original `Offering` until they are deactivated.

The reason for immutability is billing integrity: active Subscriptions must always be charged under the exact terms they were activated under.

**Versioning in practice:**

```text
managed-postgres-v1   # original; still referenced by existing Subscriptions
managed-postgres-v2   # new pricing; new Subscriptions reference this one
```

When the last Subscription referencing `managed-postgres-v1` is deactivated, you can delete `managed-postgres-v1`.

## The `subscriptionFee` block

The `pricing.subscriptionFee` block is the core of an `Offering`. It defines the recurring charge.

| Field | Type | Required | Description |
|---|---|---|---|
| `priceMicros` | int64 | yes | Price per tick in micro-currency. `1000000` = 1.00 of your configured currency. |
| `period` | string | yes | Tick interval. Format depends on `tickAlignment` (see table below). |
| `tickAlignment` | `enum` | yes | Where tick boundaries fall. |
| `minPeriods` | int32 | no | Minimum number of full ticks before cleanup is allowed after deletion. |

### Tick alignment and period format

| `tickAlignment` | `period` format | Example | Tick boundary description |
|---|---|---|---|
| `ActivatedAt` | Go-style duration: integer hours, minutes, seconds | `1h`, `30m`, `24h`, `90s` | Every N units after `activatedAt`. No proration. |
| `HourBoundary` | Integer number of hours | `"1"`, `"2"`, `"6"` | Wall-clock hour boundaries (`HH:00:00`). First tick is prorated. |
| `DayBoundary` | Integer number of days | `"1"`, `"7"`, `"30"` | 00:00 UTC of each day. First tick is prorated. |
| `MonthBoundary` | Integer number of months | `"1"`, `"3"`, `"12"` | 00:00 UTC on the 1st of each month. First tick is prorated using a fixed 30-day 10-hour 30-minute month length. |

Values that do not match the expected format for the chosen `tickAlignment` are rejected at admission.

### `minPeriods` as a cleanup guard

`minPeriods` is not a billing mechanism — it controls when a deleted Subscription is allowed to be garbage-collected. After a Subscription is deleted, the operator keeps the Kubernetes object visible (via a finalizer, a marker that prevents deletion until explicitly released) until at least `minPeriods` full ticks have elapsed since `activatedAt`. Billing continues normally during this window. Once the tick count is reached, the finalizer is removed and Kubernetes deletes the object.

Set `minPeriods: 2` on a monthly Offering to require that any Subscription runs for at least two full months before it can be cleaned up.

## Compatibility and required offerings

The `compatibility.requiredOfferings` list names other `Offerings` that must be active on the parent Subscription or a sibling Subscription before this `Offering` can be activated. This is the mechanism for expressing service dependencies — for example, a "Managed Postgres" offering that requires a "Platform Base" offering to be present.

See [Required offerings](./required-offerings.md) for a detailed walk-through with examples.

## Lifecycle defaults

The `lifecycle` block sets default behavior for child Subscriptions when this Offering's Subscriptions are deactivated:

| Field | Default | Description |
|---|---|---|
| `lifecycle.onParentDeactivate` | `Deactivate` | Whether child Subscriptions deactivate (`Deactivate`) or stay active (`Orphan`) when their parent deactivates. |
| `lifecycle.allowOverride` | `false` | Whether the Subscription may override `onParentDeactivate`. |

> **Note:** `lifecycle.allowOverride` is accepted by the API but is not currently enforced by the operator. A Subscription can always set its own `lifecycle.onParentDeactivate`, and it will take precedence over the Offering's default regardless of `allowOverride`. Do not rely on `allowOverride: false` to prevent Subscriptions from overriding cascade behavior.

See [Parent-child subscriptions](./parent-child-subscriptions.md) for a full explanation of the cascade rules.

## YAML examples

### ActivatedAt hourly Offering

Charges $40.00 per hour from the moment of activation, with no proration. Requires at least two full ticks before cleanup:

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
      priceMicros: 40000000
      minPeriods: 2
  compatibility:
    requiredOfferings:
      - name: platform-base
  lifecycle:
    onParentDeactivate: Deactivate
```

### MonthBoundary monthly Offering

Charges $500.00 per calendar month, aligned to the 1st of each month. The first tick is prorated from the activation date to the 1st of the next month:

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
      priceMicros: 500000000
  lifecycle:
    onParentDeactivate: Deactivate
```

## Verify it worked

```bash
kubectl get offering -n finops-operator-system
```

Expected output:

```text
NAME              READY
managed-postgres  True
platform-base     True
```

For more detail:

```bash
kubectl describe offering managed-postgres -n finops-operator-system
```

Look for a `Ready` condition with `status: "True"` and reason `ValidationSucceeded`. If the Offering references `requiredOfferings` and those are not yet ready, you will see `Ready: False` with reason `RequiredOfferingNotFound` or `RequiredOfferingNotReady` — this is expected while the referenced Offerings are being created.

## Troubleshooting

If the `Offering` stays `Ready: False` or is rejected on creation, see [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Subscribe to an offering](./subscribe-to-offering.md) — create a Subscription that references this Offering.
- [Required offerings](./required-offerings.md) — configure `compatibility.requiredOfferings` with a concrete example.
- [Parent-child subscriptions](./parent-child-subscriptions.md) — understand lifecycle cascade options.
- [Offering CRD reference](../reference/crds/offering.md)
