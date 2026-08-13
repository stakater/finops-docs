# Key features

## Pricing declared as a resource

A [`PriceBook`](../concepts/pricebook.md) holds a three-letter currency code, a valuation mode of either `currency` or `percent`, and per-unit rates written as plain decimal strings, so a price list is reviewed and rolled out through the same pull request and GitOps machinery as everything else in the cluster.

Which PriceBook is in force is your decision, not the operator's. Annotate the one you want with `finops.stakater.com/active: "true"` and the operator reconciles that choice into `status.active` and demotes whichever book held the slot before. Only when no PriceBook carries the annotation does the operator fall back to keeping an existing active book, or bootstrapping the newest one when there is no incumbent. Switching prices is therefore a matter of moving an annotation, which the [switch the active PriceBook](../guides/switch-active-pricebook.md) guide walks through.

## Cost collection on a schedule

A [`CostJob`](../concepts/costjob.md) is a schedule, and the operator owns the `CronJob` behind it. Set `spec.interval` to `1h`, `6h`, `12h`, or `24h` and the operator writes the matching cron expression onto the CronJob; `1m` and `5m` also map through for debugging, and any other value falls back to daily. The interval defaults to `24h`.

`spec.type` decides what the job does. The default, `ResourceCostCollection`, pulls allocation data out of OpenCost and loads it into PostgreSQL. `SubscriptionChargeCollection` runs the charge collector instead, which prices each active Subscription and persists the result. The two are separate CostJobs, so collection and billing can run at different cadences.

## Recurring subscription fees

An Offering can charge a flat recurring fee for being subscribed at all, independent of any resource usage. The fee accrues in discrete ticks of length `period`, each tick contributing `priceMicros`, and `tickAlignment` decides where those tick boundaries fall.

| Alignment | Where ticks fall | `period` format |
| --- | --- | --- |
| `ActivatedAt` | At `status.activatedAt` plus multiples of `period` | Go duration, for example `1h` or `30m` |
| `HourBoundary` | On wall-clock hour boundaries | Whole number of hours, for example `1` |
| `DayBoundary` | On wall-clock day boundaries | Whole number of days, for example `7` |
| `MonthBoundary` | On wall-clock month boundaries | Whole number of months, for example `3` |

`ActivatedAt` gives each subscription its own billing cycle, which suits add-ons. The three boundary modes line every subscription up on the same windows, which suits reporting, and they prorate the first partial tick after activation by the fraction of the period actually covered. For any window the fee is computed as the number of tick boundaries crossed, so re-running a collection over the same window always yields the same number.

`minPeriods` on the fee is a cleanup guard rather than a charge. Delete a Subscription whose Offering sets it and the charge collector keeps the subscription's finalizer until at least that many ticks have elapsed since `status.activatedAt`; billing carries on unchanged during the wait and the object is released once the count is reached. A second, independent gate applies alongside it: the finalizer is also held until charges are finalized through the subscription's last billable hour, so nothing is torn down before its final hour has been charged. Details are in [`SubscriptionFee`](../reference/api.md#subscriptionfee) and the [billing model](../concepts/billing-model.md).

## Margins on measured usage

Beyond the flat fee, an Offering can price measured consumption meter by meter through `pricing.resourcePricing`. The meter names are `subscription`, `cpuHour`, `gpuHour`, `ramGbHour`, `pvGbHour`, and `networkGb`; the five usage meters are the ones that read allocation data, and `networkGb` bills total data transferred per GiB, so it has no time dimension. Each usage meter takes its base rate from the active `currency`-mode PriceBook, then applies that meter's [`margins`](../reference/api.md#margins): either `absoluteMicros`, an additive amount in micro-currency where 1,000,000 micros is one currency unit, or `factorMilli`, a multiplier in milli-units where 1000 is 1.000x and 980 is a two percent discount. The two are mutually exclusive and neither may be negative, so a discount is expressed as a factor below 1000.

The result is published on `Offering.status.resolvedPricing` as an effective unit price per meter, which is the number consumers see. If an Offering declares metered resources and no active currency PriceBook exists, the Offering stays not ready rather than publishing margins applied to a zero base. The [price resource usage](../guides/price-resource-usage.md) guide covers the mechanics.

## Composition and compatibility

A [`Subscription`](../concepts/subscription.md) may name a parent Subscription, which is how add-ons attach to the thing they extend: a storage subscription hanging off a VM subscription, for example. The Offering controls what happens when that parent goes away through `lifecycle.onParentDeactivate`, either `Deactivate` to follow the parent down or `Orphan` to keep running while retaining the parent reference for traceability.

An Offering can also declare `compatibility.requiredOfferings`, which a Subscription must satisfy before it activates. Coverage is looked for across the whole family sharing a root ancestor, but never among the subscription's own descendants: ancestors, siblings, uncles, and cousins all count, its own children do not. Coverage is enforced continuously and losing it deactivates an active Subscription, which is terminal. Both `offeringRef` and `parent` are immutable, enforced by CRD validation rules, because a subscription's activation is a billing epoch that cannot be re-pointed. Offering and Subscription each also have a validating webhook, described in [webhooks](../reference/webhooks.md). See [compatibility and hierarchy](../concepts/compatibility-and-hierarchy.md) for the coverage rules in full.

## Provider independence

Cloud specifics are confined to a single cluster-scoped [`FinOpsProvider`](../concepts/finops-provider.md) named `default`, which carries exactly one of `awsoptions`, `gcpoptions`, `azureoptions`, or `onpremoptions`. CRD-level validation enforces both the name and the exactly-one rule. Nothing downstream changes shape when that option changes: PriceBooks, Offerings, Subscriptions, and the charge history are written identically on any provider, because rates come from your PriceBook rather than from a provider price list.

## Durable charge history

Subscription status carries rolling summaries for the current hour, day, and month, which is enough to answer "what is this costing right now" from `kubectl`. The record that survives lives in PostgreSQL: the charge collector writes one row per cluster, subscription, hour, and charge source, so a month of billing is a queryable time series rather than a snapshot.

The in-progress hour is written with `finalized = false` and rewritten on each tick; once the hour closes it is replaced by a finalized row. Each row references the exact Offering and Subscription versions used to price it, and both resources are mirrored into the database version by version, so a charge can always be explained by the pricing that was in effect when it was incurred. See [read subscription costs](../guides/read-subscription-costs.md).
