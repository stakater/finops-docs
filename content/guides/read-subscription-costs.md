# Read subscription costs

This guide explains how to interpret the `status.costs` field on a `Subscription`. After your `SubscriptionChargeCollection` CostJob has run at least once, each active Subscription reports three rolling cost buckets. You will learn what each bucket and each field means, how to convert micro-currency values to human-readable amounts, and how often the data updates.

**Prerequisites:**

- An active `Subscription` (see [Subscribe to an offering](./subscribe-to-offering.md)).
- A `CostJob` of type `SubscriptionChargeCollection` scheduled and running. See [Collect cost data](./collect-cost-data.md).
- `kubectl` access to the namespace containing your Subscriptions.

## The three cost buckets

`status.costs` always contains exactly three entries once populated, one per granularity:

| `granularity` | What it covers |
|---|---|
| `hour` | The current calendar hour (UTC). |
| `day` | The current calendar day (UTC, midnight to midnight). |
| `month` | The current calendar month (UTC, 1st to 1st). |

Each bucket is an independent window. The `hour` bucket does not roll up into `day`; all three buckets are computed independently by the `SubscriptionChargeCollection` job.

## current vs projected

Each bucket has two cost figures:

| Field | Meaning |
|---|---|
| `current` | Accumulated spend from completed ticks in the bucket. Increases only when a tick boundary is crossed. |
| `projected` | Estimated spend for the full bucket duration, based on the number of tick boundaries remaining until the bucket ends. |

`current` increases only at tick boundaries — within a tick, it stays at its last settled value. `projected` gives you an estimate of where you will end the period if the Subscription stays active.

## The breakdown meters

Each bucket optionally contains a `breakdown` list. Each entry names a meter and reports `current` and `projected` for that meter alone.

| Meter name | What it measures |
|---|---|
| `subscription` | The Offering's recurring subscription fee. This is the primary meter and is always present when the Subscription is active. |
| `cpuHour` | CPU consumption (vCPU-hours) costed against the `PriceBook` `cpuHour` rate. |
| `gpuHour` | GPU consumption (GPU-hours) costed against the `gpuHour` rate. |
| `ramGbHour` | RAM consumption (GB-hours) costed against the `ramGbHour` rate. |
| `pvcGbHour` | Persistent volume consumption (GB-hours) costed against the `pvGbHour` rate. |
| `networkIngressGbHour` | Network ingress (GiB) costed against the `networkGiB` rate. |
| `networkEgressGbHour` | Network egress (GiB) costed against the `networkGiB` rate. |

The `subscription` meter reflects the `priceMicros` charges defined in the Offering. The resource meters (`cpuHour`, `ramGbHour`, etc.) reflect costs computed from allocation data collected by the `ResourceCostCollection` CostJob. Whether resource meters are populated depends on whether the collection job has run and whether the Subscription's workload has allocation data in OpenCost.

## Micro-currency conversion

All values in `status.costs` are integers in micro-currency. Divide by `1,000,000` to get the amount in your configured currency:

| Raw value | Divided by 1,000,000 | Human-readable |
|---|---|---|
| `20000000` | 20.0 | $20.00 |
| `40000000` | 40.0 | $40.00 |
| `500000000` | 500.0 | $500.00 |
| `28800000000` | 28800.0 | $28,800.00 |

## Illustrative status.costs output

The following example shows a Subscription activated at `09:00:00Z` on `2026-04-01`, with an Offering charging `$40.00` per hour (`priceMicros: 40000000`, `tickAlignment: ActivatedAt`, `period: 1h`). The collection job ran at `09:30:00Z` — 30 minutes into the first hour. With `ActivatedAt` alignment the first tick boundary is at `10:00:00Z`, so no ticks have completed yet.

```yaml
status:
  ready: "True"
  activatedAt: "2026-04-01T09:00:00Z"
  costs:
    - granularity: hour
      start: "2026-04-01T09:00:00Z"
      endExclusive: "2026-04-01T10:00:00Z"
      current: 0              # no ticks settled yet — first tick ends at 10:00:00Z
      projected: 40000000     # $40.00 projected for the full hour
      breakdown:
        - name: subscription
          current: 0
          projected: 40000000
    - granularity: day
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-04-02T00:00:00Z"
      current: 0              # no ticks settled yet
      projected: 560000000    # 14 full ticks until day-end × $40.00 = $560.00
      breakdown:
        - name: subscription
          current: 0
          projected: 560000000
    - granularity: month
      start: "2026-04-01T00:00:00Z"
      endExclusive: "2026-05-01T00:00:00Z"
      current: 0              # no ticks settled yet
      projected: 28400000000  # 710 full ticks until month-end × $40.00 = $28,400.00
      breakdown:
        - name: subscription
          current: 0
          projected: 28400000000
```

Reading the hour bucket: at `09:30:00Z`, the first tick has not yet completed (it will settle at `10:00:00Z`), so `current: 0`. `projected: 40000000` ($40.00) is the projected charge for the one full tick that fits in this hour bucket.

Reading the day bucket: from `09:30:00Z` to midnight there are 14 full hour boundaries (`10:00`, `11:00`, ..., `23:00`), so `projected: 560000000` ($560.00).

Reading the month bucket: from `09:30:00Z` on April 1 to May 1 `00:00:00Z` is approximately 710.5 hours, so 710 full tick boundaries fit, giving `projected: 28400000000` ($28,400.00).

## How frequently status.costs updates

`status.costs` is updated each time the `SubscriptionChargeCollection` CostJob runs. If your CostJob has `interval: 1h`, costs update at the top of each hour. If you need more frequent updates, set a shorter interval such as `5m`, but be aware that shorter intervals increase load on the database.

Check your `SubscriptionChargeCollection` CostJob to confirm its schedule:

```bash
kubectl get costjob -n finops-operator-system
```

If `status.costs` is empty, either the collection job has not run yet, or the Subscription is not active. Verify that `status.ready` is `"True"` and that the CostJob's `lastExecutionStatus` is `Success`.

## Troubleshooting

If `status.costs` is empty or not updating, see [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Subscribe to an offering](./subscribe-to-offering.md) — create a Subscription and activate it.
- [Collect cost data](./collect-cost-data.md) — configure the `SubscriptionChargeCollection` CostJob.
- [Deactivation and cleanup](./deactivation-and-cleanup.md) — understand what happens to `status.costs` when a Subscription is deactivated.
- [Subscription CRD reference](../reference/crds/subscription.md)
