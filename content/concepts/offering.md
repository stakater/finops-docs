# Offering

An `Offering` is the priced thing. It declares what a subscriber is charged for — a recurring fee, a set of metered resources, or both — and every [Subscription](subscription.md) bound to it is billed on those terms. A platform engineer creates one per commercial unit: a plan tier, a GPU slot, a platform base fee. It is namespace-scoped, so an Offering can live alongside the manifests of whichever team owns the thing being sold.

Its defining property is that the spec is frozen at creation. An Offering is a contract, not a setting you tune.

```yaml
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
      priceMicros: 40000000
      minPeriods: 24
    resourcePricing:
      - name: cpuHour
        margins:
          factorMilli: 1150
      - name: ramGbHour
        margins:
          absoluteMicros: 200
  lifecycle:
    onParentDeactivate: Deactivate
```

## The spec cannot change

One CEL validation rule is attached to the `spec` field of the type:

| Rule | Message on rejection |
| --- | --- |
| `self == oldSelf` | `offering spec is immutable` |

The API server evaluates it on every update, so any edit to `pricing`, `compatibility`, or `lifecycle` is refused with that message whether or not the operator is running, and `kubectl apply --dry-run=server` reports it. The Offering's validating webhook is not involved: its update path is an empty no-op, and immutability is a property of the CRD. Nothing lands in `status` when an edit is rejected either, because the request never reaches the reconciler — the message appears in the `kubectl` output and nowhere else.

The reason for the rule is attribution. A Subscription activates under one set of terms and accrues charge rows against them for its whole life, and a charge row records the Offering version it was priced from. If the fee could be edited in place, every historical row would become ambiguous about what it represented. Labels, annotations, and status are untouched by the rule; only `spec` is closed.

Adding a field later counts as a change. An Offering created without `compatibility` can never grow one, so decide on requirements and lifecycle before the first apply.

## Pricing

`spec.pricing` is required, and both blocks inside it are optional. An Offering can charge a recurring fee only, price resource usage only, or do both.

`pricing.subscriptionFee` is the part that accrues from being active, independent of any workload:

| Field | Required | What it sets |
| --- | --- | --- |
| `priceMicros` | yes | The price of one tick, in micro-currency, minimum `1`. `40000000` is 40.00 of the PriceBook's currency. |
| `period` | yes | The tick length. A Go duration such as `1h` under `ActivatedAt`, a plain integer count under the boundary alignments. |
| `tickAlignment` | yes | Where tick boundaries fall: `ActivatedAt`, `HourBoundary`, `DayBoundary`, or `MonthBoundary`. |
| `minPeriods` | no | Ticks that must elapse after activation before a deleted Subscription is released. Minimum `1`. |

A second CEL rule couples the first two: `period` must match `^[0-9]+[hms]$` under `ActivatedAt` and `^[0-9]+$` under the three boundary alignments, and a mismatch is rejected with `period must be a Go duration (e.g. '1h') for ActivatedAt alignment, or a plain integer for boundary alignments`. How ticks are counted, when the first one is prorated, and how the final one is handled is the [billing model](billing-model.md).

`minPeriods` is a cleanup guard and nothing more. It holds the finalizer of a deleted Subscription until the tick count is reached; billing carries on unchanged in the meantime and no shortfall is charged for ticks that never ran.

`pricing.resourcePricing` prices measured consumption. Each entry names one meter and, optionally, the margin to apply to it:

| Meter | Billed on |
| --- | --- |
| `cpuHour` | Average cores used, integrated over the billable span |
| `gpuHour` | Average GPUs used, integrated over the billable span |
| `ramGbHour` | Average memory used, integrated over the billable span |
| `pvGbHour` | Persistent volume capacity attached, per GiB-hour |
| `networkGb` | Data transferred and received, per GiB, with no time dimension |

An entry carries no rate of its own. The per-unit rate comes from the active [PriceBook](pricebook.md) and the entry's `margins` adjust it: `absoluteMicros` adds a fixed amount in micro-currency, `factorMilli` multiplies in milli-units where `1000` is 1.000x and `980` a two percent discount. Three more CEL rules police the pair: the two are mutually exclusive (`absoluteMicros and factorMilli are mutually exclusive — set only one`) and neither may be negative (`absoluteMicros must be >= 0`, `factorMilli must be >= 0`), so a discount is a factor below `1000` and never a negative addition. A meter listed with no `margins` at all resolves to the PriceBook rate unchanged.

Declaring a meter is only half of what it takes to bill it. Usage is charged only for a Subscription that also declares `usageSources`; without them the Offering's `resourcePricing` produces no usage calculators at all. [Price resource usage](../guides/price-resource-usage.md) walks through both sides.

!!! note
    The schema also accepts `subscription` as a meter name, but no usage calculator is registered for that name. An entry called `subscription` under `resourcePricing` resolves to a price and then never charges anything; the recurring fee belongs in `subscriptionFee`. An Offering with an empty `pricing: {}` is likewise admitted and becomes ready, and charges nothing.

## Compatibility requirements

`compatibility.requiredOfferings` lists Offerings that must be in play for a Subscription to this one to activate. Each entry needs an explicit `namespace`; references are never resolved against the referring object's namespace.

```yaml
spec:
  compatibility:
    requiredOfferings:
      - name: platform-core
        namespace: finops-operator-system
```

The list is enforced in two different places. On the Offering itself, the reconciler holds `status.ready` false until every required Offering exists and is itself ready, reporting `RequiredOfferingNotFound` or `RequiredOfferingNotReady`, and it walks the requirement graph for cycles. A self-reference or a cycle is also refused at admission, by the one check the Offering webhook performs on create. On a Subscription that binds to the Offering, the same list becomes a coverage test against the Subscription's family, which is where the interesting rules live: see [compatibility and hierarchy](compatibility-and-hierarchy.md).

## Lifecycle

`lifecycle.onParentDeactivate` decides what happens to a Subscription of this Offering when the Subscription's parent deactivates. `Deactivate`, the default, ends it too; `Orphan` leaves it active and keeps the parent reference for traceability. The Offering's value is consulted only when the Subscription itself carries no `spec.lifecycle` block.

!!! warning
    `lifecycle.allowOverride` is declared in the API and nothing reads it at this release. A Subscription that carries a `spec.lifecycle` block always supplies its own `onParentDeactivate`, whichever way `allowOverride` is set. Because that field defaults to `Deactivate`, a Subscription that sets only `lifecycle.targetRef` silently overrides an Offering's `Orphan` policy back to `Deactivate`.

## Readiness and resolved pricing

`status.ready` is `True` or `False` and is the `Ready` column of `kubectl get offerings`. It turns true once the requirement check passes and pricing has resolved, and the reconciler records a `PricingResolved` condition alongside it.

`status.resolvedPricing` is what the Offering publishes to consumers:

| Field | What it holds |
| --- | --- |
| `resolvedAt` | When pricing was resolved. |
| `meters[].name` | One entry per meter declared in `resourcePricing`. Empty when the Offering prices no usage. |
| `meters[].unitPriceMicros` | The effective per-unit price: the active PriceBook's rate for that meter with the entry's margins applied. |
| `subscriptionFee` | The spec's fee block copied through verbatim. |
| `meters[].includedUsage` | In the schema, never populated at this release. |

Because the spec cannot change, this is computed once and then left alone. A later edit to the PriceBook's rates does not move an already-resolved unit price, and a usage charge takes its rate from the PriceBook row recorded with the allocation rather than from this field, so the two can differ after a rate change; [changing rates later](pricebook.md#changing-rates-later) covers the consequences.

A metered Offering needs an active PriceBook whose `valuationMode` is `currency`. Without one, resolution is refused rather than published, and the Offering stays not ready with reason `NoActivePricebook`, because margins applied to a missing rate would publish the margin itself as the price. A rate that cannot be parsed gives `PricebookParseFailed` the same way. An Offering with no `resourcePricing` needs no PriceBook and resolves regardless.

## Deletion

The reconciler adds the finalizer `offerings.finops.stakater.com/finalizer` the first time it sees an Offering. Deletion is then refused at admission, by the validating webhook on delete, while either a Subscription references the Offering through `offeringRef` (`DependentSubscriptionsExist`) or another Offering requires it (`DependentOfferingsExist`). If an Offering does acquire a deletion timestamp, the reconciler runs the same check, records `Deleting=False` while dependents remain, and only writes `Deleting=True` with reason `DeletionAllowed` and drops the finalizer once nothing is left pointing at it.

Both checks select on `status.ready` being `True`, which narrows them more than it first appears. A Subscription that is not ready — including one that has already deactivated, since deactivation sets `Ready=False` — does not block the delete.

!!! warning
    That gap has a sharp edge. A deleting, deactivated Subscription still needs its Offering: every collection run fetches it to price the remaining hours and to evaluate `minPeriods`. Delete the Offering first and each subsequent run records a fetch error against that Subscription and skips the finalizer removal, so the Subscription never finishes deleting. Let Subscriptions clear completely before removing the Offering they were billed under.

## Replacing an Offering

There is no in-place price change, and there is no re-pointing an existing Subscription either, since `offeringRef` is immutable as well. The migration is therefore always the same shape:

1. Create a second Offering carrying the new terms, under a name that says what changed, for example `platform-base-v2`.
1. Point new Subscriptions at the new Offering. Existing ones keep running against the old one on the terms they activated under.
1. Retire the old Offering once its last Subscription has finished deleting, not before.

Keeping both Offerings for a while is the normal state, not a failure to clean up. It is also what makes a charge row from last month explainable: the Offering it names still exists and still says what it said.

## Related

- [Define an offering](../guides/define-offering.md) for authoring the first one, and [price resource usage](../guides/price-resource-usage.md) for the metered half.
- [Billing model](billing-model.md) for tick counting, proration, and the deactivation snap.
- [`OfferingSpec`](../reference/api.md#offeringspec), [`SubscriptionFee`](../reference/api.md#subscriptionfee), [`Margins`](../reference/api.md#margins), and [`ResolvedPricing`](../reference/api.md#resolvedpricing) for the field-level reference.
