# Billing model

An Offering's `pricing.subscriptionFee` is the one charge the operator works out entirely on its own: no measurement, no allocation rows, just a price and a clock. This page is that clock. It covers where a billing period starts and ends, what the opening and closing periods cost, and why recomputing a window always produces the same number. Metered charges are priced from allocation rows instead, and [price resource usage](../guides/price-resource-usage.md) covers those.

## What a tick is worth

A tick is one complete billing period, and each tick adds `priceMicros` to the total. Charges are computed for a window rather than for a moment, and the fee for a window is the number of tick boundaries inside it multiplied by the price:

```text
ticks(t)        = tick boundaries in (activatedAt, t]
fee(start, end) = priceMicros × (ticks(end) − ticks(start))
```

A boundary at `activatedAt` is excluded and a boundary at `t` is included. That half-open convention is what stops a boundary being counted twice: a boundary landing exactly on a window's end instant belongs to that window, and the next window, which starts at the same instant, does not see it again. The collection job charges hour by hour, so the hourly windows it walks partition a Subscription's life with no gaps and no overlaps.

The formula reads nothing but `activatedAt`, the two endpoints, and the Offering's fee block. Nothing in it depends on when the calculation runs, so a window recomputed an hour later, a day later, or after an operator restart yields the same figure, and a job that processes the same hour twice writes the same number twice rather than charging twice. The `projected` figure in each of `status.costs`'s buckets comes from the same call, evaluated over the whole bucket instead of the elapsed part of it.

All monetary values are integers in micro-currency: 1,000,000 micros is 1.00 unit of the PriceBook's currency, so `priceMicros: 40000000` is 40.00 per tick.

## Where boundaries fall

`tickAlignment` decides the grid the boundaries sit on, and it also fixes the format of `period`. A CEL rule on `subscriptionFee` couples the two:

```text
self.tickAlignment == 'ActivatedAt' ? self.period.matches('^[0-9]+[hms]$') : self.period.matches('^[0-9]+$')
```

A mismatch is refused with `period must be a Go duration (e.g. '1h') for ActivatedAt alignment, or a plain integer for boundary alignments`. The accepted form under `ActivatedAt` is narrower than Go's full duration syntax: `1h`, `90m` and `3600s` all pass, `1h30m` does not.

`ActivatedAt` puts boundaries at `activatedAt + N × period`. The grid belongs to that one Subscription, so two Subscriptions activated a minute apart tick a minute apart for the rest of their lives.

`HourBoundary` reads `period` as a count of hours and puts boundaries on a fixed grid of that many hours, the same grid for every Subscription in the cluster. `1` gives every clock hour, `2` gives even-numbered hours UTC, `6` gives 00:00, 06:00, 12:00 and 18:00 UTC. A `period` that does not divide 24 evenly is still valid, but its grid stops landing at the same clock time each day.

`DayBoundary` puts the first boundary at the midnight UTC following activation, then steps `period × 24 hours` from there. With `period: "1"` that is a shared daily grid. With anything larger the grid is anchored to the activation date, so `7` means every seventh day counted from that first midnight rather than a calendar week.

`MonthBoundary` puts boundaries on the 1st of a month at 00:00 UTC. The first one is the 1st of the month `period` months after the activation month, and each later one steps `period` months from there. `1` is therefore a shared monthly grid, while `3` is a quarter anchored to the activation month rather than to the calendar year.

## Prorating the opening tick

Under the three boundary alignments the opening tick is almost always short, because activation lands mid-period and the first boundary arrives early. That tick is charged in proportion to the part of a period it covered:

```text
first_tick = priceMicros × seconds(activatedAt → first boundary) / seconds(full period)
```

The reduction is applied once, to whichever window contains that first boundary, and it is arithmetic on whole seconds with integer division, so the result is rounded down to whole micros and sub-second precision in `activatedAt` is discarded. `ActivatedAt` alignment never prorates: its first tick is a full `period` by construction, so there is nothing to reduce.

The denominator is not the length of the short tick's own span. It is the alignment's nominal period:

| Alignment | Full-period denominator |
| --- | --- |
| `HourBoundary` | `period` hours |
| `DayBoundary` | `period` × 24 hours |
| `MonthBoundary` | `period` × 30 days 10 hours 30 minutes, a fixed 365.25 ÷ 12 = 30.4375 days |

The fixed month is what makes month-to-month charges comparable. A subscriber who joins on the 20th of a 31 day month and one who joins on the 20th of a 28 day month are measured against the same denominator, so the same fraction of a month costs the same either way.

!!! note
    Under `DayBoundary` the first boundary is the next midnight whatever `period` says, while the denominator is the full `period × 24 hours`. With `period: "7"` a Subscription activated at 22:00 has an opening tick of two hours measured against 168, charging about 1.2 percent of a period, and the first full week then runs from that midnight. The same applies to `MonthBoundary` with `period` above `1`.

**Worked example, hourly.** An Offering with `tickAlignment: HourBoundary`, `period: "1"` and `priceMicros: 40000000`, subscribed by a Subscription that activates at `09:15:00Z`:

- The first boundary is `10:00:00Z`, so the opening tick covers 45 minutes, 2,700 seconds.
- A full period is 1 hour, 3,600 seconds.
- The opening tick charges `40000000 × 2700 / 3600 = 30000000`, that is 30.00, and it lands in the `09:00`–`10:00` window.
- Every later tick charges the full `40000000`.

**Worked example, monthly.** An Offering with `tickAlignment: MonthBoundary`, `period: "1"` and `priceMicros: 300000000`, subscribed by a Subscription that activates at `2026-08-12T09:15:00Z`:

- The first boundary is `2026-09-01T00:00:00Z`, so the opening tick covers 19 days 14 hours 45 minutes, 1,694,700 seconds.
- The denominator is the fixed month, 2,629,800 seconds.
- The opening tick charges `300000000 × 1694700 / 2629800 = 193326488`, that is 193.326488, about 64 percent of a month.
- It lands in the charge row for the hour `2026-08-31T23:00:00Z`, the window that ends on the boundary, rather than in the first hour of September.

## Charging the final tick

`status.deactivatedAt` records the instant the reconciler ended the Subscription, unrounded. The fee calculation does not bill to that instant: it snaps the value forward to the next tick boundary for the Subscription's alignment and clamps both ends of every window to the snapped time. The final tick is therefore always charged in full, and windows that begin after the snapped time contribute nothing.

The snapped time exists only inside that calculation. It is never written back, so `status.deactivatedAt` keeps the raw instant and the snap has to be applied mentally when reconciling a status timestamp against a charge row. A deactivation that already sits exactly on a boundary is not pushed forward to the next one.

A `HourBoundary` Subscription with `period: "1"` deactivated at `09:40:00Z` snaps to `10:00:00Z` and is charged a full tick for the `09:00`–`10:00` hour. The gap can be much wider than that: an `ActivatedAt` Subscription with `period: 24h` activated at `09:15` and deactivated three days later at `12:00` snaps to `09:15` on the fourth day, so it pays for a tick that ran for under three hours. The longer the period, the more a late deactivation costs.

## Choosing an alignment

| Alignment | `period` format | Where boundaries fall | Opening tick | Typical use |
| --- | --- | --- | --- | --- |
| `ActivatedAt` | Integer with `h`, `m` or `s`: `1h`, `90m`, `3600s` | `activatedAt` plus multiples of `period`, per Subscription | Full period, never prorated | Add-ons and per-subscriber cycles that should start when the subscriber does |
| `HourBoundary` | Integer hours: `1`, `2`, `6` | A cluster-wide grid of `period` hours | Prorated against `period` hours | Hourly reporting where every Subscription should tick together |
| `DayBoundary` | Integer days: `1`, `7`, `30` | Midnight UTC after activation, then every `period` days | Prorated against `period` × 24 hours | Daily budgets and dashboards that reset at midnight UTC |
| `MonthBoundary` | Integer months: `1`, `3`, `12` | The 1st of a month, every `period` months from the activation month | Prorated against the fixed 30.4375 day month | Monthly, quarterly and annual commercial terms |

`ActivatedAt` is the choice when a subscriber's cycle should be their own and proration would be a surprise on an invoice. The three boundary alignments are the choice when Subscriptions should line up with each other and with reporting periods, and their cost is that short-lived Subscriptions pay a fraction of an opening tick and a whole closing one.

## Holding a deleted Subscription

`minPeriods` on an Offering's `subscriptionFee` is a cleanup guard, not a commitment. It names a number of full ticks that must have elapsed since `activatedAt` before the `SubscriptionChargeCollection` job will take the finalizer off a deleted Subscription. Nothing about the fee changes while the guard is waiting: billing carries on tick by tick, and no shortfall is added for the ticks that never ran when a Subscription is deleted early.

A second gate sits beside it, and both must be satisfied. Charges have to be finalized through the Subscription's last billable hour before the finalizer comes off, so the object survives long enough for its closing hours to reach `subscription_charges`. The tick count is evaluated with the same counter the fee uses, so `minPeriods: 24` against `HourBoundary` and `period: "1"` means 24 hourly boundaries, not 24 hours of wall clock from the delete. [Deactivate a subscription](../guides/deactivate-a-subscription.md) walks through what that looks like.

## Related

- [Offering](offering.md) for the fee block itself, and [Subscription](subscription.md) for the `activatedAt` and `deactivatedAt` timestamps the formula reads.
- [How charges reach `Subscription.status.costs`](architecture.md#how-charges-reach-subscriptionstatuscosts) for the job that applies these rules hour by hour.
- [Read subscription costs](../guides/read-subscription-costs.md) for interpreting the buckets the numbers land in.
- [`SubscriptionFee`](../reference/api.md#subscriptionfee) and [`TickAlignment`](../reference/api.md#tickalignment) for the field-level reference.
