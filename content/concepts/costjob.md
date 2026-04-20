# CostJob

## What it is

CostJob is a schedule. It tells the operator how often to run a particular collection task, and the operator responds by creating a Kubernetes CronJob that executes that task on the specified interval. There are two types of collection task: one that pulls raw allocation data from OpenCost, and one that computes subscription charges and handles Subscription cleanup.

Without at least one CostJob of each type, the operator does not pull cost data from OpenCost and Subscription status costs are never updated. CostJob is the heartbeat of the cost-accounting system.

## When to use it

Platform engineers create CostJobs during initial setup, alongside the FinOpsProvider and PriceBook. You typically create two: one `ResourceCostCollection` CostJob to pull allocation data from OpenCost, and one `SubscriptionChargeCollection` CostJob to compute charges and update Subscription status. Both usually run on the same interval — `1h` is a common choice for production clusters.

You adjust a CostJob's interval if you need finer or coarser cost granularity, or to reduce load on OpenCost during peak periods.

## How it fits

CostJob depends on [FinOpsProvider](./finops-provider.md) and [PriceBook](./pricebook.md) being in place first: the `ResourceCostCollection` job pulls allocation data from OpenCost, which must already be configured with the correct pricing. The `SubscriptionChargeCollection` job reads that allocation data and applies it to active [Subscriptions](./subscription.md), updating `status.costs` on each one.

CostJob does not directly reference Offerings or Subscriptions in its spec — it processes all active Subscriptions in scope on each run.

## Key things to know

- There are two types: `ResourceCostCollection` pulls allocation data from OpenCost and stores it; `SubscriptionChargeCollection` computes per-Subscription charges, updates `status.costs`, and removes the finalizer from deleted Subscriptions whose `minPeriods` has elapsed.
- The operator creates a Kubernetes CronJob from each CostJob. The CostJob spec drives the CronJob's schedule.
- Only a specific set of interval values map cleanly to cron expressions: `1h`, `6h`, `12h`, `24h`, `1m`, and `5m`. Any other value falls back to the daily schedule `0 0 * * *`. Use one of these recognized values.
- The default interval is `24h` and the default type is `ResourceCostCollection`.
- CostJob status tracks `lastExecutionTime`, `lastSuccessfulExecutionTime`, `lastExecutionStatus`, and up to 10 entries in `executionHistory`.
- Changing a CostJob's interval updates the underlying CronJob schedule on the next reconciliation.
- The `SubscriptionChargeCollection` job also finalizes and removes deleted Subscriptions once `minPeriods` has elapsed — it is a cleanup component as well as a billing one.

## Learn more

- [CostJob reference](../reference/crds/costjob.md) — full field specification including all timeout fields.
- [Collect cost data](../guides/collect-cost-data.md) — guide that walks through creating and verifying a CostJob.
- [Subscription](./subscription.md) — explains how `minPeriods` interacts with the SubscriptionChargeCollection job.
