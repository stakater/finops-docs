# Read subscription costs

`status.costs` is the operator's answer to what a subscriber is costing right now, and it is written by the `SubscriptionChargeCollection` CostJob rather than by the reconciler. It holds three rolling buckets, each carrying an accumulated figure, a projected figure, and a split by meter, all in micro-currency. This guide reads one bucket at a time, converts the numbers, checks the arithmetic against the Offering's terms, and says what each figure does and does not include. It is for whoever owns the billing data: a platform engineer checking an accrual, or the person writing the report that consumes it.

## Prerequisites

- A `Subscription` that has activated, so `status.activatedAt` is set. [Subscribe to an offering](subscribe-to-offering.md) creates one.
- A [`SubscriptionChargeCollection` CostJob](collect-cost-data.md) that has completed at least one run. Nothing else writes `status.costs`.
- `kubectl` read access to the namespace the Subscription lives in.

Every figure below comes from one scenario, the same one the [quick start](../getting-started/quick-start.md) leaves you with: an Offering charging 40.00 an hour with `tickAlignment: ActivatedAt` and `period: 1h`, a Subscription that activated at `2026-04-01T09:00:00Z`, and a collection run scheduled for `13:00:00Z` the same day.

## Step 1: Read the buckets off the Subscription

```sh
kubectl get subscription acme-platform-base -n finops-operator-system -o yaml
```

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-01T09:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-01T13:00:00Z"
      endExclusive: "2026-04-01T14:00:00Z"
      projected: 40000000
      breakdown:
        - name: subscription
          projected: 40000000
    - granularity: day
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-04-02T00:00:00Z"
      current: 160000000
      projected: 600000000
      breakdown:
        - name: subscription
          current: 160000000
          projected: 600000000
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 160000000
      projected: 28440000000
      breakdown:
        - name: subscription
          current: 160000000
          projected: 28440000000
```

There are always exactly three buckets once anything is written, one per granularity, and they are written together. `current`, `projected` and `breakdown` are all omitted when they are zero, which is why the `hour` bucket above shows a projection and no accumulation rather than a `current: 0`. An absent field means zero, not unknown.

## Step 2: Place the three windows

Each bucket covers the half-open window from `start` to `endExclusive`, and all three are anchored to the hour the collection run was scheduled for, not to the moment you read the object:

| `granularity` | Window | Anchor | In the example |
| --- | --- | --- | --- |
| `hour` | The scheduled hour itself, one hour long | The run's scheduled timestamp, truncated to the hour | `13:00:00Z` to `14:00:00Z` |
| `day` | Midnight UTC to the next midnight UTC | The UTC date the scheduled hour falls on | `2026-04-01T00:00:00Z` to `2026-04-02T00:00:00Z` |
| `month` | The 1st at 00:00 UTC to the 1st of the next month | The UTC calendar month the scheduled hour falls in | `2026-04-01T00:00:00Z` to `2026-05-01T00:00:00Z` |

The three are computed independently over their own windows. The `hour` bucket does not roll up into `day`, and `day` does not roll up into `month`; each is the same calculation evaluated over a different span, which is why the `day` and `month` figures agree in the example. They only agree because the Subscription activated on the first day of the month, so both windows contain the same tick boundaries so far.

Two details are easy to misread. The `month` window is a real calendar month, so it is 28 to 31 days long, and it is not the fixed 30 day 10 hour 30 minute month that [proration](../concepts/billing-model.md#prorating-the-opening-tick) uses as its denominator under `MonthBoundary`. And because the anchor is the run's scheduled hour rather than wall clock, every run inside the same hour produces the same three windows.

## Step 3: Separate current from projected

Both figures come from the same fee arithmetic, evaluated over different spans:

| Field | What it holds | What moves it |
| --- | --- | --- |
| `current` | Spend settled inside the window, from `start` up to the run's scheduled hour | A tick boundary crossed inside the window, and consumption measured for a Subscription that bills usage |
| `projected` | The subscription fee for the whole window, `start` to `endExclusive` | Nothing, while the window and the terms stay the same. A deactivation cuts it back to what will actually be charged |

Three consequences are worth having in mind before you quote either number.

`projected` is the fee and only the fee. No usage meter ever contributes to it, because there is no measurement of the future to project from. On a Subscription that bills consumption as well as a fee, `current` can therefore end up larger than `projected`, and that is not an error.

A window that opens before `activatedAt` still counts only ticks after activation. The `day` projection above is 600.00 rather than a full day's 24 ticks, because the Subscription did not exist for the first nine hours of April 1.

The `hour` bucket's fee accumulation is always zero. A tick is charged at the boundary that closes it, and the `hour` window begins at the run's own scheduled hour, so no boundary inside that window has been reached at the moment the numbers are written. On a Subscription that bills usage, the `hour` bucket's `current` is the consumption measured so far in the hour in progress, and nothing else.

## Step 4: Convert micro-currency

Every figure in `status.costs` is an integer in micro-currency, where 1,000,000 micros is 1.00 unit of the active PriceBook's currency. Divide by a million:

| Value in `status.costs` | Divided by 1,000,000 | Reads as |
| --- | --- | --- |
| `40000000` | 40.0 | 40.00 |
| `160000000` | 160.0 | 160.00 |
| `600000000` | 600.0 | 600.00 |
| `28440000000` | 28440.0 | 28,440.00 |

The buckets carry no currency of their own. The unit is the `spec.currency` of the PriceBook the charges were priced against, so a cluster reading `28440000000` reads 28,440.00 of whatever that book declares. [Define pricing with a PriceBook](define-pricing.md) covers the field.

## Step 5: Split a bucket by meter

`breakdown` divides a bucket's totals by meter. Exactly six meter names exist, and no others appear:

| Meter | Kind | What it charges for |
| --- | --- | --- |
| `subscription` | Recurring fee | The Offering's `pricing.subscriptionFee`, one `priceMicros` per tick, computed from the clock alone |
| `cpuHour` | Usage | CPU core-hours consumed |
| `gpuHour` | Usage | GPU-hours consumed |
| `ramGbHour` | Usage | RAM GiB-hours consumed |
| `pvGbHour` | Usage | Persistent volume GiB-hours provisioned |
| `networkGb` | Usage | Total data moved, transfer plus receive, per GiB |

The names ending `Gb` are billed on a binary basis of 1,073,741,824 bytes to a unit, matching how OpenCost converts bytes, so read them as GiB. In a PriceBook the rate that prices `networkGb` is spelled `networkGiB` under `spec.rates`; that spelling is a rate field and never a meter name.

The `subscription` entry is present in every bucket whose fee is non-zero, and it is the only entry a fee-only Subscription ever has. Usage entries appear only where both halves are configured, the Subscription declaring `usageSources` and the Offering declaring `resourcePricing` for that meter, and then only for hours where allocation data actually exists for those sources and carries a rate. A meter with nothing measured produces no charge at all, so it is absent from `breakdown` rather than present and reading zero. [Price resource usage](price-resource-usage.md) covers pairing the two halves, and [collect cost data](collect-cost-data.md) covers the `ResourceCostCollection` job that produces the allocation rows in the first place.

!!! note
    Usage entries carry a `current` and no `projected`, because projection is fee-only. A `breakdown` entry showing a `current` and nothing else is a usage meter behaving normally.

## Step 6: Check the arithmetic

The fee for a window is the number of tick boundaries inside it multiplied by the price, counting boundaries strictly after `activatedAt` and up to and including the window's end:

```text
fee(start, end) = priceMicros × (ticks(end) − ticks(start))
```

With `tickAlignment: ActivatedAt`, `period: 1h` and an activation at `09:00:00Z`, the boundaries fall at `10:00`, `11:00`, `12:00` and so on. Every figure in step 1 follows from that.

**The `hour` projection, 40.00.** `ticks(14:00)` is 5, counting `10:00` through `14:00`. `ticks(13:00)` is 4. The window therefore contains one boundary: `40000000 × 1 = 40000000`.

**The `day` projection, 600.00.** `ticks(2026-04-02T00:00)` is 15, counting `10:00` through midnight. `ticks(2026-04-01T00:00)` is 0, because the window opens before activation and boundaries before `activatedAt` are never counted. That gives `40000000 × 15 = 600000000`, not the 24 ticks a full day would hold.

**The `day` accumulation, 160.00.** The same subtraction, evaluated to the run's scheduled hour instead of the window's end. `ticks(13:00)` is 4, so `40000000 × 4 = 160000000`. Four boundaries have been reached, at `10:00`, `11:00`, `12:00` and `13:00`.

**The `month` projection, 28,440.00.** `2026-04-01T09:00:00Z` to `2026-05-01T00:00:00Z` is 29 days and 15 hours, which is `29 × 24 + 15 = 711` hours and therefore 711 boundaries. That gives `40000000 × 711 = 28440000000`.

A projection recomputed later in the same window returns the same number, because the calculation reads only `activatedAt`, the two window endpoints and the Offering's fee block. [Billing model](../concepts/billing-model.md#what-a-tick-is-worth) has the formula in full, the proration that applies to a prorated opening tick under the boundary alignments, and the clamp that applies after a deactivation.

## Step 7: Know when the numbers move

`status.costs` is rewritten once per run of the `SubscriptionChargeCollection` CostJob and at no other time. Nothing watches the object in between, so a Subscription read halfway through an hour reports what the last run computed.

With `interval: 1h` that CostJob runs on `0 * * * *`, giving one rewrite at the top of each hour. A shorter interval does not give finer fee data: the run's anchor is truncated to the hour, so every run inside one hour rebuilds the same three windows and recomputes the same in-progress hour. Sub-hourly intervals refine usage figures and change nothing else. [Collect cost data](collect-cost-data.md#step-2-create-the-collection-costjob) has the interval-to-schedule table, including which values silently fall through to a daily schedule.

Each rewrite also records where the numbers came from, on the `CostsResolved` condition:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{range .status.conditions[?(@.type=="CostsResolved")]}{.reason}{"  "}{.message}{"\n"}{end}'
```

```text
FromDB  Status.Costs resolved from DBCostSummary
```

`FromDB` means `current` was summed out of the stored charge rows. `FromCalculator` means the database could not serve this Subscription on that run and the fee calculator produced the buckets instead, which makes the reading fee-only: no usage meter appears in `breakdown` on that path, however much consumption was measured. A reading you intend to bill from is worth checking this condition on first.

## Where the same charges are stored

Every run also persists what it computed to the `subscription_charges` table in PostgreSQL, one row per cluster, Subscription, hour window and charge source. Hours that have closed are written finalized, except where a usage-metered Subscription's allocation data has not settled yet, and the hour in progress is rewritten in place on every run with the finalized flag false so later runs can refine it. On the `FromDB` path a bucket's `current` is a sum over exactly those rows.

That table is where a longer history lives. `status.costs` is a rolling summary of three windows around the current run and keeps nothing older, so a report that needs last month reads the table rather than the object. [How charges reach `Subscription.status.costs`](../concepts/architecture.md#how-charges-reach-subscriptionstatuscosts) describes both passes.

## When a bucket or a meter is missing

An empty `status.costs` has four causes worth checking in order:

1. No `SubscriptionChargeCollection` CostJob is scheduled, or none has completed a run yet. Check with `kubectl get costjob -A`; a `SubscriptionChargeCollection` CostJob writes nothing to its own status, so read its Jobs and their pod logs.
1. The Subscription never activated. A Subscription with no `status.activatedAt` is skipped outright by the run, whatever else is true of it.
1. The Offering declares no subscription fee. Buckets are shaped around the fee, so an Offering with only `resourcePricing`, or with `pricing: {}`, produces no buckets at all even while its Subscription's usage charges are being computed and stored. Read those from `subscription_charges`.
1. The Offering could not be read. Every run fetches each Subscription's Offering fresh, and a Subscription whose Offering has been deleted or renamed gets no buckets, because the terms the buckets are shaped from are unavailable.

The `CostsResolved` condition is the marker for all four. It is written on the same status update as the buckets, so a Subscription with no costs and no `CostsResolved` condition was never summarised, and its absence is the signal to look at the run rather than at the numbers.

A bucket that carries only `start` and `endExclusive` is not an error. It means every figure in it was zero and omitted, which is the normal state before the first tick boundary settles.

A usage meter missing from `breakdown` while the fee is present points at the usage half rather than at the job. Either the Subscription declares no `usageSources`, or the Offering declares no `resourcePricing` entry for that meter, or no allocation rows matched those sources for the hour, or the rows that matched carry no rate for that meter because their PriceBook has none set. [Price resource usage](price-resource-usage.md#when-pricing-does-not-resolve) works through the pricing side of that.

## Related guides

- [Collect cost data](collect-cost-data.md) for the CostJob that writes these buckets and the schedule it runs on.
- [Price resource usage](price-resource-usage.md) for adding usage meters to the breakdown.
- [Billing model](../concepts/billing-model.md) for tick counting, proration, and the deactivation clamp behind every figure here.
- [Deactivate a subscription](deactivate-a-subscription.md) for reading the closing figures before the object is removed.
- [`CostBucket`](../reference/api.md#costbucket) and [`CostMetric`](../reference/api.md#costmetric) for the field-level reference.
