# Billing model

## Ticks

Subscription charges accrue in discrete **ticks**. A tick is one complete billing period. Each tick adds `priceMicros` to the total charge. The fee for any time bucket is:

```
fee = priceMicros × ticks_in_bucket
```

Where `ticks_in_bucket` is the number of tick boundaries that fall within the bucket's time range. This formula is idempotent — the same time range always produces the same count, regardless of when the calculation runs.

All values are expressed in micro-currency: `1,000,000` micros equals `1.00` of the configured currency. A `priceMicros` value of `40000000` represents $40.00 per tick.

## Tick alignments

The `tickAlignment` field on an Offering's `subscriptionFee` controls where tick boundaries fall. Each alignment has its own `period` format and proration behavior.

### ActivatedAt

Tick boundaries fall at `activatedAt + N × period` for N = 1, 2, 3, and so on. The `period` field is a Go-style duration built from integer hours, minutes, or seconds: `1h`, `30m`, `24h`, `90s`.

There is no proration. Every tick is a full `period`. The first tick starts at activation and ends exactly one `period` later.

Best for per-Subscription cycles where each subscriber's billing period is independent of wall-clock time, such as add-ons billed from the moment of activation.

### HourBoundary

Tick boundaries fall at wall-clock hour boundaries (`HH:00:00 UTC`). The `period` field is a plain integer number of hours (for example, `"1"`).

The first tick after activation is **prorated**: the charge for that first tick is proportional to the time from `activatedAt` to the first hour boundary, divided by the full period length.

Best for synchronized hourly reporting where all Subscriptions tick at the same wall-clock times, making cross-Subscription comparisons straightforward.

### DayBoundary

Tick boundaries fall at `00:00:00 UTC` of each day. The `period` field is a plain integer number of days: `"1"` for daily, `"7"` for weekly, `"30"` for a 30-day period.

The first tick is prorated using `period × 24 hours` as the full-period denominator.

Best for daily cost reporting and budgets that reset at midnight UTC.

### MonthBoundary

Tick boundaries fall at `00:00:00 UTC` on the 1st of each month. The `period` field is a plain integer number of months: `"1"` for monthly, `"3"` for quarterly, `"12"` for yearly.

The first tick is prorated using a fixed denominator of 30 days 10 hours 30 minutes per month (365.25 ÷ 12 = 30.4375 days). This fixed denominator keeps month-to-month charges comparable regardless of whether a calendar month has 28, 29, 30, or 31 days.

Best for SaaS-style monthly billing where teams expect a consistent charge each month.

## First-tick proration

For alignments that prorate the first tick (`HourBoundary`, `DayBoundary`, `MonthBoundary`), the first-tick charge is:

```
first_tick_charge = priceMicros × (seconds from activatedAt to first boundary)
                                / (seconds in the full period)
```

**Worked example.** A Subscription with `tickAlignment: HourBoundary`, `priceMicros: 40000000` ($40.00 per hour), activated at `09:15:00Z`:

- First tick boundary: `10:00:00Z`.
- Time from activation to boundary: 45 minutes = 2,700 seconds.
- Full period: 1 hour = 3,600 seconds.
- First-tick charge: `40000000 × 2700 / 3600 = 30000000` ($30.00).
- All subsequent ticks are each a full $40.00.

## Deactivation snap

When a Subscription deactivates, its `deactivatedAt` timestamp is snapped forward to the next tick boundary for its alignment. The Subscription is charged for the full final tick — there is never a partial final tick. This snapped time is what appears in `status.deactivatedAt`.

For example, a Subscription with `HourBoundary` alignment that is deactivated at `09:40:00Z` will have `deactivatedAt` snapped to `10:00:00Z` and will be charged a full tick for the `09:00–10:00` hour.

## minPeriods as a cleanup guard

The `minPeriods` field on an Offering's `subscriptionFee` sets a minimum number of full ticks that must elapse after activation before the operator releases a deleted Subscription for garbage collection. Billing continues normally during this time — `minPeriods` does not change the fee formula, it only controls when the Kubernetes object is removed.

This guard exists so that the `SubscriptionChargeCollection` job has enough time to compute and record all charges that accrued before deletion. Once `minPeriods` full ticks have elapsed since `activatedAt`, the operator removes the finalizer and Kubernetes removes the object.

## Comparison

| Alignment | Period format | Tick boundary | First tick prorated? | Typical use |
|---|---|---|---|---|
| `ActivatedAt` | Go-style duration (`1h`, `30m`, `24h`, `90s`) | activation time + N × period | No — every tick is a full period | Per-subscription cycles and add-ons |
| `HourBoundary` | Integer hours | Wall-clock hour (`HH:00:00`) | Yes — partial first hour is prorated | Synchronized hourly reporting across many subscriptions |
| `DayBoundary` | Integer days | 00:00 UTC each day | Yes — using `period × 24h` as the denominator | Daily reporting |
| `MonthBoundary` | Integer months | 00:00 UTC on the 1st of each month | Yes — using a fixed 30d 10h 30m denominator | Month-aligned reporting |

## When to pick which

- **`ActivatedAt`** if you want predictable per-Subscription cycles that start when the Subscription does, with no proration surprises.
- **`HourBoundary`** if many Subscriptions should line up on the same hourly boundary for easy cross-reporting, and short-lived Subscriptions getting a fractional first hour is acceptable.
- **`DayBoundary`** if the natural billing unit is a day or a week, and daily reporting dashboards are the consumer.
- **`MonthBoundary`** if the offering maps to calendar-month commercial terms (monthly subscription, quarterly contract, annual plan). The fixed 30 d 10 h 30 m first-tick denominator keeps month-to-month charges comparable regardless of calendar length.

Charges are idempotent: the same bucket, queried at the same time, always yields the same number. This is a property of the tick-counting formula, not a guarantee about when the scheduled jobs run.

## Learn more

- [Offering reference](../reference/crds/offering.md) — full field specification for `priceMicros`, `period`, `tickAlignment`, and `minPeriods`.
- [Subscription reference](../reference/crds/subscription.md) — status fields including `activatedAt`, `deactivatedAt`, and `costs`.
- [Read subscription costs](../guides/read-subscription-costs.md) — guide for interpreting the cost buckets in Subscription status.
