# Offering

## What it is

An Offering is a named, immutable pricing contract for something that costs money. It defines the recurring fee that a Subscription accrues while active and the tick alignment that governs when billing periods start and end. Examples include a managed database tier, a GPU workload slot, or a platform base fee.

Because an Offering's `spec` is immutable after creation, it acts as a stable contract. Changing pricing rules requires creating a new Offering. This immutability gives you a clear audit trail: a Subscription's charges are always traceable to the exact Offering spec that was in effect when the Subscription was created.

## When to use it

Platform engineers create Offerings to represent the distinct services or cost categories they want to charge for. You define an Offering once, then many Subscriptions can bind to it. If you offer several tiers of a service (for example, small, medium, and large database plans), each tier is its own Offering.

## How it fits

Offering sits between the billing model and individual subscribers. [Subscriptions](./subscription.md) reference an Offering by name and namespace. The Offering's `priceMicros`, `period`, and `tickAlignment` determine the charge formula that the [CostJob](./costjob.md) SubscriptionChargeCollection job applies when computing costs.

The operator also maintains a finalizer on every Offering so that deletion is blocked while any Subscription still references it.

## Key things to know

- Offering is `namespaced`. Subscriptions reference it by name and optional namespace.
- `spec` is immutable after creation. To change pricing, create a new Offering and migrate Subscriptions to it.
- `priceMicros` is expressed in micro-currency: `1,000,000` equals 1.00 of the configured currency. The minimum value is `1`.
- Deleting an Offering is rejected at admission while any Subscription references it. The operator maintains a finalizer for this purpose.
- The operator publishes resolved per-meter prices on `status.resolvedPricing` once the Offering becomes Ready.

## Learn more

- [Offering reference](../reference/crds/offering.md) — full field specification including `period` format rules per tick alignment.
- [Define an offering](../guides/define-offering.md) — guide that walks through creating Offerings.
- [Billing model](./billing-model.md) — explains how `priceMicros`, `period`, and `tickAlignment` determine the charge formula.
