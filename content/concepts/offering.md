# Offering

## What it is

An Offering is a named, immutable pricing contract for something that costs money. It defines the recurring fee that a Subscription accrues while active, the tick alignment that governs when billing periods start and end, and optional compatibility rules that constrain which Subscriptions can use it. Examples include a managed database tier, a GPU workload slot, or a platform base fee that every tenant must carry.

Because an Offering's `spec` is immutable after creation, it acts as a stable contract. Changing pricing or compatibility rules requires creating a new Offering. This immutability gives you a clear audit trail: a Subscription's charges are always traceable to the exact Offering spec that was in effect when the Subscription was created.

## When to use it

Platform engineers create Offerings to represent the distinct services or cost categories they want to charge for. You define an Offering once, then many Subscriptions can bind to it. If you offer several tiers of a service (for example, small, medium, and large database plans), each tier is its own Offering.

Use `compatibility.requiredOfferings` when a service depends on another being present — for example, a database add-on that requires a platform base Offering to already be active on the parent Subscription.

## How it fits

Offering sits between the billing model and individual subscribers. [Subscriptions](./subscription.md) reference an Offering by name and namespace. The Offering's `priceMicros`, `period`, and `tickAlignment` determine the charge formula that the [CostJob](./costjob.md) SubscriptionChargeCollection job applies when computing costs.

An Offering can reference other Offerings via `compatibility.requiredOfferings`. The operator validates the dependency graph at admission and at reconciliation time, marking an Offering `Ready: False` if any required Offering is missing or not yet ready. The operator also maintains a finalizer on every Offering so that deletion is blocked while any Subscription or other Offering still references it.

The lifecycle policy (`onParentDeactivate`) on an Offering sets the default behavior for child Subscriptions when their parent deactivates. Individual Subscriptions can override this policy.

## Key things to know

- Offering is namespaced. Subscriptions and other Offerings reference it by name and optional namespace.
- `spec` is immutable after creation. To change pricing or compatibility, create a new Offering and migrate Subscriptions to it.
- `priceMicros` is expressed in micro-currency: `1,000,000` equals 1.00 of the configured currency. The minimum value is `1`.
- An Offering with a self-reference or a cycle in `requiredOfferings` is rejected at admission.
- Deleting an Offering is rejected at admission while any Subscription or any other Offering references it. The operator maintains a finalizer for this purpose.
- An Offering whose required Offerings are missing or not yet ready is marked `Ready: False`. This is expected during reconciliation; it returns to `Ready: True` once the referenced Offerings become ready.
- The `lifecycle.allowOverride` field is accepted by the API but is not currently enforced: Subscriptions may set their own `lifecycle.onParentDeactivate` and it takes precedence regardless of this field.
- The lifecycle policy cascades to child Subscriptions unless the child Subscription overrides it with its own policy.

## Learn more

- [Offering reference](../reference/crds/offering.md) — full field specification including `period` format rules per tick alignment.
- [Define an offering](../guides/define-offering.md) — guide that walks through creating Offerings including required Offerings.
- [Required offerings](../guides/required-offerings.md) — guide for composing Offerings with dependencies.
- [Billing model](./billing-model.md) — explains how `priceMicros`, `period`, and `tickAlignment` determine the charge formula.
