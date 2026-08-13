# Terminology

The vocabulary used across these docs, with the field, resource, or table each term maps to.

## Terms

### activation

A Subscription activates once every gate its spec implies has passed: the referenced Offering is ready, a named parent is active, any offerings its Offering requires are covered elsewhere in its family, and a named `lifecycle.targetRef` resolves to an object that exists. The reconciler stamps `status.activatedAt` at that moment, and every charge is computed relative to it.

See: [Subscription](subscription.md).

### active PriceBook

The one PriceBook whose rates OpenCost and the charge collector price against. You choose it by annotating it `finops.stakater.com/active: "true"`; the operator reconciles that choice into `status.active` and demotes whichever book held the slot before, and only elects a book on its own when none is annotated. Selection is cluster-wide, so exactly one book is active at a time.

See: [switch the active PriceBook](../guides/switch-active-pricebook.md).

### allocation

One hour of measured resource consumption for one workload, as reported by OpenCost's allocation API and stored in the operator's `provider_allocations` table. An allocation row is measurement only: charges are priced later from PriceBook rates rather than from OpenCost's own cost figures.

### charge window

The one-hour span a charge row covers. Charges are written one row per subscription, per window, per charge source, and a window is marked finalized once it will not be recomputed; the hour still in progress is marked not finalized and rewritten on every collection tick.

### compatibility root

The `metadata.uid` of a Subscription's root ancestor, resolved once and stamped onto `status.compatibilityRoot`. It identifies the family whose members can satisfy the Subscription's compatibility requirements.

See: [compatibility and hierarchy](compatibility-and-hierarchy.md).

### deactivation

The end of a Subscription's billable life, recorded as `status.deactivatedAt`. It happens when the Subscription is deleted, when its parent deactivates and the lifecycle policy is `Deactivate`, when compatibility coverage it relied on disappears, or when its lifecycle target is gone. Deactivation is terminal, so a deactivated Subscription never reactivates.

See: [deactivate a subscription](../guides/deactivate-a-subscription.md).

### deactivation snap

The rule that a deactivating Subscription is billed to a tick boundary rather than to the instant it stopped. When the fee is calculated, `deactivatedAt` is snapped forward to the next tick boundary, so the final tick is always charged in full and there is never a partial final tick.

See: [billing model](billing-model.md).

### family

The connected tree of Subscriptions that share one compatibility root. Coverage for a compatibility requirement is looked for across the whole family except the Subscription itself and everything below it, so ancestors, siblings, uncles, and cousins can provide it while the Subscription's own children and their descendants cannot.

### first-tick proration

The reduction applied to the opening tick under `HourBoundary`, `DayBoundary`, or `MonthBoundary` alignment, where activation lands mid-period and the first tick is therefore short. `ActivatedAt` alignment never prorates, because its first tick is a full period by construction.

See: [billing model](billing-model.md).

### margin

The adjustment an Offering applies to a meter's PriceBook rate to arrive at the price consumers see. `absoluteMicros` adds a fixed amount in micro-currency; `factorMilli` multiplies in milli-units, where 1000 is 1.000x and 980 is a two percent discount. The two are mutually exclusive and neither may be negative, so a discount is expressed as a factor below 1000.

See: [`Margins`](../reference/api.md#margins).

### meter

A named unit of consumption an Offering can price. The names are exactly `subscription`, `cpuHour`, `gpuHour`, `ramGbHour`, `pvGbHour`, and `networkGb`: `subscription` carries the recurring fee, and the other five are priced from allocation data. Meters appear in `Offering.status.resolvedPricing.meters` and in the `breakdown` of each entry in `Subscription.status.costs`.

See: [`MeterName`](../reference/api.md#metername).

### micro-currency

The integer convention every monetary value in the API and the database follows: one millionth of the PriceBook's currency, so 1,000,000 micros is 1.00 unit and `priceMicros: 40000000` is 40.00. Integers rather than floats keep billing arithmetic exact and reproducible.

### `minPeriods`

An optional field on an Offering's `subscriptionFee` giving the number of full ticks that must elapse after activation before the operator releases a deleted Subscription. It is a cleanup guard rather than a charge: billing continues unchanged during the wait, no shortfall is added for the periods that never ran, and the finalizer comes off once the tick count is reached and charges are finalized through the Subscription's last billable hour.

See: [`SubscriptionFee`](../reference/api.md#subscriptionfee).

### proration

Charging a fraction of `priceMicros` for a tick that a Subscription only partly covered, computed as the elapsed seconds over the seconds in a full period. It applies to the first tick under the three boundary alignments and to nothing else; the final tick is never prorated, because deactivation snaps forward to a boundary.

See: [billing model](billing-model.md).

### ResourceCostCollection

The default `CostJob` type. Its CronJob runs the operator in `cronjob` mode, fetching allocation data from OpenCost and streaming it into the `provider_allocations` table.

See: [`CostJob`](costjob.md).

### SubscriptionChargeCollection

The `CostJob` type that bills. Its CronJob runs the operator in `collectionjob` mode, computing hourly charges for every activated Subscription, writing them to the `subscription_charges` table, refreshing each Subscription's `status.costs`, and releasing the finalizer of Subscriptions whose charges have settled.

See: [`CostJob`](costjob.md).

### tick

One complete billing period of an Offering's subscription fee. Each tick adds `priceMicros` to the total, and the fee for any window is `priceMicros` multiplied by the number of tick boundaries that window crosses, which is what makes recomputing a window produce the same number every time.

See: [billing model](billing-model.md).

### tick alignment

Where tick boundaries fall. `ActivatedAt` puts them at `status.activatedAt` plus multiples of `period`; `HourBoundary`, `DayBoundary`, and `MonthBoundary` put them on wall-clock hour, day, and month boundaries. The choice also fixes the format of `period`, a Go duration for `ActivatedAt` and a plain integer count for the three boundary modes, and whether the first tick is prorated.

See: [`TickAlignment`](../reference/api.md#tickalignment).
