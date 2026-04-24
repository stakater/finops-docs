# Subscription

## What it is

A Subscription is an active binding to an [Offering](./offering.md). While it is active, it accrues the recurring fee defined in that Offering. The charges are reported in the Subscription's status across three rolling time buckets — hour, day, and month — so you can see both the charges accumulated so far and a projected total for each period.

## When to use it

Platform engineers or automation create a Subscription whenever a tenant or workload starts using a service that an Offering represents. Subscriptions are how individual billing relationships are expressed. You create one Subscription per tenant-service binding.

## How it fits

Subscription is the leaf in the resource graph. It references an Offering and inherits the Offering's pricing terms. The [CostJob](./costjob.md) SubscriptionChargeCollection job visits every active Subscription on each run, computes the charges that have accrued since the last tick, and updates `status.costs`.

The operator maintains a finalizer on every Subscription, which controls the cleanup behavior described below.

## Key things to know

- Subscription is `namespaced`. The referenced Offering defaults to the same namespace unless `offeringRef.namespace` is specified.
- A Subscription becomes active (`ready: True`) when its Offering is `Ready: True`. If the Offering is not ready, the Subscription stays `Ready: False`.
- Charges accrue per tick. The tick formula, alignment, and proration rules are defined by the Offering's `subscriptionFee`. See [Billing model](./billing-model.md).
- `status.costs` contains exactly three rolling buckets: `hour`, `day`, and `month`. Each has `current` (accrued so far in completed ticks) and `projected` (projected for the full bucket) values in micro-currency.
- When a Subscription is deleted, the operator does not immediately remove the object. It marks the Subscription as deactivating and keeps the finalizer in place. The `SubscriptionChargeCollection` job removes the finalizer once at least `minPeriods` full ticks have elapsed since `activatedAt`.
- `deactivatedAt` in status is snapped forward to the next tick boundary for the Offering's alignment. There is never a partial final tick — the Subscription is charged for the full final period.

## Learn more

- [Subscription reference](../reference/crds/subscription.md) — full field specification and status fields.
- [Subscribe to offering](../guides/subscribe-to-offering.md) — guide that walks through creating and verifying a Subscription.
- [Read subscription costs](../guides/read-subscription-costs.md) — guide for interpreting `status.costs`.
- [Billing model](./billing-model.md) — explains tick alignment, proration, and the `minPeriods` cleanup guard.
