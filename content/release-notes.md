# Release notes

Releases of the FinOps Operator, newest first. Each entry summarises what changed for someone running or configuring the operator; the chart and the operator image share a version.

!!! note
    This documentation describes the operator as it currently stands in development, which is ahead of v0.1.7 in a couple of places that are visible in a manifest. The whole-family compatibility model and its `status.compatibilityRoot`, and the `namespace` field being required on every reference rather than defaulted from the referrer, are neither of them in a tagged release yet. Where a page describes one of those, read it as the behaviour you will get on the next release rather than on v0.1.7.

## v0.1.7 (14 September 2026)

Ships FinOps Gateway v0.1.6. No operator change.

## v0.1.6 (14 September 2026)

Revised chart defaults. The `CostJob` and `SubscriptionChargeCollection` intervals now default to `1h` rather than `1m`, which is a realistic cadence for collection rather than one meant for a demo, and the chart exposes `costJob.resources` and `costJob.sharding`.

## v0.1.5 (2 September 2026)

### Allocation queries can be sharded

The per-hour allocation query covered the whole cluster in one request, which times out once a cluster is large enough. `CostJob.spec.sharding` splits each hour into namespace-filtered batches run in parallel:

```yaml
spec:
  sharding:
    namespacesPerShard: 25
    concurrency: 4
```

Shard keys come from OpenCost's own namespace list rather than from Kubernetes, so namespaces deleted mid-window and OpenCost's pseudo-namespaces are still covered and sharding cannot quietly drop rows that a single unfiltered query would have returned. Concurrency is capped, and the first shard failure aborts the rest, so a partial hour is rolled back rather than committed.

It is opt-in. Left unset, the job issues the same single unfiltered query as before. Apply the regenerated CRD before setting it, or the field is pruned.

### Configurable job resources

`CostJob.spec.resources` sets the collection container's requests and limits, which previously lived only in the operator image and so could not be changed without rebuilding it. It replaces the defaults rather than merging with them, so a requests-only spec leaves the container without a memory limit.

### Pricing periods carry their unit

`Offering.status.resolvedPricing.subscriptionFee.period` now always carries an explicit unit suffix, so a reader no longer has to fetch `tickAlignment` to learn whether `1` means an hour, a day or a month. The spec accepts both the bare and the suffixed form, since Offering specs are immutable and existing ones cannot be migrated, and a suffix belonging to a different alignment is rejected at admission rather than misread.

### Fixes

The collection job was discarding the environment variables declared in its own job template. The one that mattered is `SCHEDULED_TIMESTAMP`, a field reference the operator cannot supply any other way, without which a retried run collected the current window instead of the window it was retrying. `HOURS_LOOKBACK`, `CLUSTER_ID` and the OpenCost tuning values were falling back to built-in defaults for the same reason.

Seed data tooling also gained subscription-aware backfill, with pre-flight checks and a verification runbook.

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
