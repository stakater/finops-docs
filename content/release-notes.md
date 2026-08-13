# Release notes

Releases of the FinOps Operator, newest first. Each entry summarises what changed for someone running or configuring the operator; the chart and the operator image share a version.

!!! note
    This documentation describes the operator as it currently stands in development, which is ahead of v0.1.4 in a few places that are visible in a manifest. The whole-family compatibility model and its `status.compatibilityRoot`, the `namespace` field being required on every reference rather than defaulted from the referrer, `CostJob.spec.resources`, and the generated CronJob keeping the environment variables from the operator's own pod template are none of them in a tagged release yet. Where a page describes one of those, read it as the behaviour you will get on the next release rather than on v0.1.4.

## v0.1.4 (10 August 2026)

Collection runs no longer maintain a database view. The `mv_provider_allocations_summary` materialised view had no readers left and was rebuilt on every tick, which meant a full re-scan and re-aggregate of `provider_allocations` growing with retained history; it is dropped, and the refresh step went with it. Nothing reads from it, so no report changes.

`CostJob.spec.databaseViewsRefreshTimeout` is the one user-visible consequence. It is kept on the type so existing objects still apply, and it now bounds nothing. Setting it is accepted and changes no behaviour.

The release also carries dependency and security updates, including the PostgreSQL driver `pgx` at v5.9.2.

## v0.1.3 (13 July 2026)

The release that made the cost data durable and the pricing metered.

Offerings and Subscriptions are mirrored into PostgreSQL as versioned rows, so a spec that existed when a charge was written can still be read back afterwards. Hourly subscription charges are persisted rather than only computed, and `Subscription.status.costs` is loaded from those stored rows instead of being recalculated on every run, with the `CostsResolved` condition recording which of the two paths produced the figures.

Metered pricing arrived alongside it: `usageSources` on a Subscription paired with `resourcePricing` on its Offering, resolved per-meter pricing published on the Offering's status, and working meters for CPU, GPU, RAM, persistent volume, and network transfer. A Subscription can from here bill measured consumption as well as a recurring fee.

## v0.1.2 (23 April 2026)

An Offering now publishes its resolved pricing on `status.resolvedPricing`, so what a subscriber will be charged is readable from the object rather than inferred from the spec and the active PriceBook together.

Status handling across the reconcilers was reworked into one path, which is what makes the `Ready` and `PricingResolved` conditions on an Offering agree with each other.

## v0.1.1 (13 April 2026)

Offerings and Subscriptions became real. Both kinds gained a reconciler and a validating admission webhook, which is the point at which a Subscription starts activating against an Offering and cycles in a requirement graph are refused at admission.

The first `SubscriptionChargeCollection` implementation landed with them, populating each Subscription's status from the charges it computed, on the database schema for subscriptions, offerings, and subscription costs added in the same release. Several Helm chart fixes came with it.

## v0.1.0 (23 February 2026)

The first release. It shipped three kinds, `CostJob`, `PriceBook`, and `FinOpsProvider`, which is enough to collect allocation data from OpenCost and price it, but not yet to bill a subscriber.

A `CostJob` took a configurable interval, and the chart could create a default `PriceBook` for a cluster to start from. The three dependencies each read their credentials from their own Secret, for PostgreSQL, Prometheus, and OpenCost, rather than sharing one. Collection runs handled interruption from the start: a run that is cut off does not lose the hours it had already written, and the next run resumes from where the last one stopped rather than starting over.

## Related

- [Uninstalling](getting-started/uninstalling.md) for the order to remove a release in, which matters more than the version you are removing.
- [Configuration reference](reference/configuration.md) for the chart values and environment variables each version reads.
