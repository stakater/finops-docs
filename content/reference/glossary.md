# Glossary

Terms used throughout the FinOps Operator docs.

## Terms

### activation

A Subscription becomes active when its Offering is ready, all parent Subscriptions (if any) are active, and any target Kubernetes resource (if specified) exists and is ready. An active Subscription accrues charges on its meter and begins charging according to its Offering's billing model.

See: [Subscription](./crds/subscription.md).

### active PriceBook

The PriceBook currently feeding pricing data to OpenCost. When a PriceBook is created or changed, the operator marks it active and rewrites the OpenCost pricing configuration. Only one PriceBook is active at a time per Kubernetes cluster.

See: [PriceBook](./crds/pricebook.md).

### allocation

Cost data calculated by OpenCost for cluster resources (CPU, RAM, storage, GPU, network). The FinOps Operator queries allocation data and uses it to report per-Subscription costs. Allocation is distinct from billing: it tracks actual resource usage, while billing applies pricing and subscription fees.

### BYO-OpenCost mode

An operating mode where the operator writes pricing data to a ConfigMap in the OpenCost namespace. This mode is the default when the `MTO_ENABLED` environment variable is not set or is set to anything other than the literal string `"true"`. The operator manages the entire OpenCost deployment lifecycle.

See: [Operating Modes](../concepts/operating-modes.md).

### deactivation

A Subscription becomes inactive when its parent Subscription deactivates (if `onParentDeactivate: Deactivate` applies), its target Kubernetes resource disappears, or the user deletes it. Once deactivated, a Subscription stops accruing new charges (though its status continues to be updated until cleanup).

See: [Subscription](./crds/subscription.md).

### deactivation snap

When a Subscription deactivates, its `deactivatedAt` timestamp is snapped forward to the next tick boundary for its billing alignment. This ensures the Subscription is always charged for a complete final tick — there is never a partial final tick charge.

See: [Billing Model](../concepts/billing-model.md).

### first-tick proration

When a Subscription with `tickAlignment` set to `HourBoundary`, `DayBoundary`, or `MonthBoundary` first activates, its opening tick is prorated. The charge for that first tick is reduced based on the time elapsed from activation to the first tick boundary, scaled against the full period duration.

See: [Billing Model](../concepts/billing-model.md).

### meter

A named component of a Subscription's cost breakdown. Meters include `subscription` (the Offering's recurring fee), `cpuHour`, `ramGbHour`, `gpuHour`, `pvcGbHour`, and network ingress/egress. Meters appear in the `status.costs[].breakdown[]` array.

See: [Subscription](./crds/subscription.md).

### micro-currency

Billing values are always stored and reported as integers representing micro-units of the configured ISO 4217 currency. One million micro-units equals 1.00 unit (e.g., 1,000,000 micros = $1.00 USD). This avoids floating-point arithmetic and ensures reproducible billing calculations.

### `minPeriods`

A field on an Offering that specifies the minimum number of full billing ticks that must elapse after a Subscription's activation before the operator will allow its deletion. During this minimum period, billing continues normally. After `minPeriods` ticks have passed, the cleanup finalizer is removed and Kubernetes garbage-collects the object.

See: [Offering](./crds/offering.md).

### MTO-bundled mode

An operating mode where the operator patches a separate OpenCost Custom Resource managed by Stakater's Multi-Dependency Operator (MDO). MDO handles OpenCost reconciliation, and the FinOps Operator restarts OpenCost after MDO applies changes. Enabled when `MTO_ENABLED=true`.

See: [Operating Modes](../concepts/operating-modes.md).

### orphan

A child Subscription that remains active after its parent Subscription deactivates. This happens when the child's effective `onParentDeactivate` policy is `Orphan` rather than `Deactivate`. Orphaned Subscriptions continue to accrue charges independently.

See: [Subscription](./crds/subscription.md).

### parent/child subscription

A hierarchical relationship between Subscriptions. A child Subscription references its parent via `spec.parent.subscriptionRef`. When the parent deactivates, the child either deactivates or becomes orphaned based on the effective `onParentDeactivate` policy. Parent/child relationships enable hierarchical cost tracking and cascading lifecycle management.

See: [Subscription](./crds/subscription.md).

### proration

Partial billing for a tick when activation or deactivation occurs mid-period. Prorated charges are calculated as `priceMicros × (seconds elapsed) / (seconds in full period)`. Proration applies to the first tick after activation with `HourBoundary`, `DayBoundary`, or `MonthBoundary` alignment, and is not used with `ActivatedAt` alignment.

See: [Billing Model](../concepts/billing-model.md).

### required offering

An Offering that must be present (and ready) on a parent Subscription or sibling Subscription for another Offering to be considered ready. Required Offerings are declared via `spec.compatibility.requiredOfferings[]` and enforce compatibility constraints between offerings.

See: [Offering](./crds/offering.md).

### ResourceCostCollection

A type of scheduled CostJob that pulls allocation data from OpenCost and stores it for later use. The operator converts the CostJob's interval into a Kubernetes `CronJob` that runs in `CronJob` mode and populates the resource cost database.

See: [CostJob](./crds/costjob.md).

### SubscriptionChargeCollection

A type of scheduled CostJob that computes per-Subscription charges and updates each active Subscription's `status.costs` array. It is also responsible for removing the cleanup finalizer from Subscriptions whose `minPeriods` has elapsed, enabling garbage collection.

See: [CostJob](./crds/costjob.md).

### tick

A discrete billing interval. Each tick adds `priceMicros` to a Subscription's total charge. Where tick boundaries fall is determined by the `tickAlignment` setting: `ActivatedAt` (relative to activation), `HourBoundary` (wall-clock hours), `DayBoundary` (UTC midnight), or `MonthBoundary` (UTC month start).

See: [Billing Model](../concepts/billing-model.md).

### tick alignment

The billing model's alignment rule that determines where tick boundaries fall. The four alignments are `ActivatedAt` (relative to activation time), `HourBoundary` (wall-clock hour boundaries), `DayBoundary` (UTC midnight), and `MonthBoundary` (UTC month start). The alignment also determines the format of the `period` field and whether the first tick is prorated.

See: [Billing Model](../concepts/billing-model.md).
