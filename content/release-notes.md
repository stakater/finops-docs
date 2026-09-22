# Changelog

Releases of the FinOps Operator, newest first. Each entry summarises what changed for someone running or configuring the operator; the chart and the operator image share a version.

## v0.1.x

### v0.1.7

_**September 14, 2026**_

Ships FinOps Gateway v0.1.6. No operator change.

### v0.1.6

_**September 14, 2026**_

#### Enhancements

- The `CostJob` and `SubscriptionChargeCollection` intervals now default to `1h` rather than `1m`, which is a realistic cadence for collection rather than one meant for a demo.
- The chart exposes `costJob.resources` and `costJob.sharding`.

### v0.1.5

_**September 2, 2026**_

#### Features

- `CostJob.spec.sharding` splits the hourly allocation query into namespace-filtered batches run in parallel, which is intended for clusters where the single cluster-wide request times out. It is opt-in, and leaving it unset preserves the existing behaviour. See [CostJob](concepts/costjob.md#sharding-the-allocation-query).
- `CostJob.spec.resources` sets the collection container's requests and limits, which previously lived only in the operator image and so could not be changed without rebuilding it. It replaces the defaults rather than merging with them, so a requests-only spec leaves the container without a memory limit.
- `Offering.status.resolvedPricing.subscriptionFee.period` now always carries an explicit unit suffix, so a reader no longer has to fetch `tickAlignment` to learn whether `1` means an hour, a day or a month. The spec accepts both the bare and the suffixed form, since Offering specs are immutable and existing ones cannot be migrated, and a suffix belonging to a different alignment is rejected at admission rather than misread.

#### Bug Fixes

- Fixed the collection job discarding the environment variables declared in its own job template. The one that mattered is `SCHEDULED_TIMESTAMP`, which the operator cannot supply any other way, and without it a retried run collected the current window instead of the window it was retrying. `HOURS_LOOKBACK`, `CLUSTER_ID` and the OpenCost tuning values were falling back to built-in defaults for the same reason.

#### Enhancements

- Seed data tooling gained subscription-aware backfill, with pre-flight checks and a verification runbook.

### v0.1.4

_**August 10, 2026**_

#### Enhancements

- Collection runs no longer maintain the `mv_provider_allocations_summary` materialised view. It had no readers left and was rebuilt on every tick, which meant a full re-scan and re-aggregate of `provider_allocations` growing with retained history. Nothing read from it, so no report changes.
- Dependency and security updates, including the PostgreSQL driver `pgx` at v5.9.2.

#### Changes to behaviour

- `CostJob.spec.databaseViewsRefreshTimeout` now bounds nothing. It is kept on the type so existing objects still apply, and setting it is accepted and changes no behaviour.

### v0.1.3

_**July 13, 2026**_

The release that made the cost data durable and the pricing metered.

#### Features

- Offerings and Subscriptions are mirrored into PostgreSQL as versioned rows, so a spec that existed when a charge was written can still be read back afterwards.
- Hourly subscription charges are persisted rather than only computed, and `Subscription.status.costs` is loaded from those stored rows instead of being recalculated on every run. The `CostsResolved` condition records which of the two paths produced the figures.
- Metered pricing, through `usageSources` on a Subscription paired with `resourcePricing` on its Offering, with resolved per-meter pricing published on the Offering's status. Meters for CPU, GPU, RAM, persistent volume, and network transfer ship with it, so a Subscription can bill measured consumption as well as a recurring fee.

### v0.1.2

_**April 23, 2026**_

#### Features

- An Offering now publishes its resolved pricing on `status.resolvedPricing`, so what a subscriber will be charged is readable from the object rather than inferred from the spec and the active PriceBook together.

#### Bug Fixes

- The `Ready` and `PricingResolved` conditions on an Offering now agree with each other.

### v0.1.1

_**April 13, 2026**_

#### Features

- Offerings and Subscriptions each gained a reconciler and a validating admission webhook, which is the point at which a Subscription starts activating against an Offering, and cycles in a requirement graph are refused at admission.
- The first `SubscriptionChargeCollection` implementation, populating each Subscription's status from the charges it computed.
- Database schema for subscriptions, offerings, and subscription costs.

### v0.1.0

_**February 23, 2026**_

The first release. It shipped enough to collect allocation data from OpenCost and price it, but not yet to bill a subscriber.

#### Features

- Three kinds: `CostJob`, `PriceBook`, and `FinOpsProvider`.
- A `CostJob` takes a configurable interval, and the chart can create a default `PriceBook` for a cluster to start from.
- PostgreSQL, Prometheus, and OpenCost each read their credentials from their own Secret rather than sharing one.
- Collection runs handle interruption. A run that is cut off does not lose the hours it had already written, and the next run resumes from where the last one stopped rather than starting over.

## Related

- [Uninstalling](getting-started/uninstalling.md) for the order to remove a release in, which matters more than the version you are removing.
- [Configuration reference](reference/configuration.md) for the chart values and environment variables each version reads.
