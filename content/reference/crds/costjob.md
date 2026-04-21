# CostJob (reference)

## Purpose

`CostJob` defines a scheduled recurring job that the FinOps Operator manages as a Kubernetes `CronJob`. Two job types are available: one that collects raw resource allocation data from OpenCost, and one that computes per-Subscription charges and handles Subscription cleanup. Create one `CostJob` of each type to drive the core FinOps data pipeline.

## Scope and name constraints

`CostJob` is `namespaced`. There are no naming requirements, but each namespace typically contains at most one object of each `type`.

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `type` | `enum` | no | `ResourceCostCollection` | What the scheduled job does. One of `ResourceCostCollection` or `SubscriptionChargeCollection`. |
| `interval` | duration string | no | `24h` | How often the job runs. See the recognized values table below. |
| `databaseInitTimeout` | duration string | no | `2m` | Maximum time to wait for the database to initialize. |
| `kubernetesOperationTimeout` | duration string | no | `1m` | Maximum time for Kubernetes API operations. |
| `openCostFetchTimeout` | duration string | no | `2m` | Maximum time to wait for an OpenCost response. |
| `databaseInsertTimeout` | duration string | no | `3m` | Maximum time for a database write operation. |
| `databaseViewsRefreshTimeout` | duration string | no | `5m` | Maximum time allowed for the scheduled data-refresh operation. |
| `statusUpdateTimeout` | duration string | no | `1m` | Maximum time for writing status back to the Kubernetes API. |
| `httpClientTimeout` | duration string | no | `90s` | Maximum time for outbound `HTTP` requests. |

Each timeout field has a corresponding environment variable on the job pod. See [Configuration](../configuration.md) for the full mapping.

### Type semantics

- `ResourceCostCollection` — the job pulls allocation data from OpenCost and stores it for later querying. This is the data-collection half of the pipeline.
- `SubscriptionChargeCollection` — the job computes per-Subscription charges and writes results to each active Subscription's `status.costs`. It also removes the finalizer from Subscriptions whose `minPeriods` guard has elapsed, releasing them for deletion.

### Recognized interval values

The operator maps `interval` to a Kubernetes `CronJob` schedule expression. Use one of the following recognized values. Any other value falls back to the daily schedule (`0 0 * * *`).

| `interval` value | Generated cron schedule | Meaning |
|---|---|---|
| `1m` | `* * * * *` | Every minute |
| `5m` | `*/5 * * * *` | Every 5 minutes |
| `1h` | `0 * * * *` | Top of every hour |
| `6h` | `0 */6 * * *` | Every 6 hours |
| `12h` | `0 */12 * * *` | Every 12 hours |
| `24h` | `0 0 * * *` | Daily at 00:00 UTC |

## Status

| Field | Type | Description |
|---|---|---|
| `lastExecutionTime` | timestamp | When the most recent run started. |
| `lastSuccessfulExecutionTime` | timestamp | When the last successful run started. |
| `lastExecutionStatus` | `enum` | Outcome of the most recent run. One of `Success`, `Failed`, `Error`, or `Pending`. |
| `executionHistory` | list | Up to the 10 most recent runs, each with `executionTime`, `status`, `duration`, and `error`. |

## Validation rules

- `type` must be one of `ResourceCostCollection` or `SubscriptionChargeCollection`.
- `interval` should be one of the recognized values listed above. Unrecognized values are accepted but fall back to the daily schedule.
- All timeout fields must be valid duration strings (e.g. `30s`, `2m`, `1h`) when provided.

## Lifecycle notes

The operator creates and manages a Kubernetes `CronJob` for each `CostJob`. When `CostJob` spec changes, the operator updates the corresponding `CronJob`.

The `SubscriptionChargeCollection` job is the component responsible for removing finalizers from deactivated Subscriptions once their `minPeriods` guard has elapsed. Without a running `SubscriptionChargeCollection` job, deactivated Subscriptions will not be cleaned up.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

## Examples

The following example creates a `ResourceCostCollection` job that runs every hour.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: resource-cost-collection
  namespace: finops-operator-system
spec:
  type: ResourceCostCollection
  interval: 1h
```

The following example creates a `SubscriptionChargeCollection` job that runs every hour with a custom fetch timeout.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: subscription-charge-collection
  namespace: finops-operator-system
spec:
  type: SubscriptionChargeCollection
  interval: 1h
  openCostFetchTimeout: 5m
  databaseInsertTimeout: 5m
```

## Related guides

- [Collect cost data](../../guides/collect-cost-data.md) — schedule a ResourceCostCollection CostJob.
- [Read subscription costs](../../guides/read-subscription-costs.md) — tied to the SubscriptionChargeCollection CostJob interval.
