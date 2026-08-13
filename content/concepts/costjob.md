# CostJob

A `CostJob` is a schedule, not a job. You declare how often a collection task should run and which task it is, and the reconciler turns that into a Kubernetes `CronJob` it owns; the work itself happens in the short-lived pods that CronJob fires. CostJob is scoped to a namespace, and a typical cluster runs two of them in the operator's namespace, because the two task types are separate objects.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: allocation-collection
  namespace: finops-operator-system
spec:
  type: ResourceCostCollection
  interval: 1h
```

## The two types

`spec.type` decides which of the operator binary's one-shot modes the pod runs in. It defaults to `ResourceCostCollection`.

| `spec.type` | Pod mode | What one run does |
| --- | --- | --- |
| `ResourceCostCollection` | `--mode=cronjob` | Fetches allocation data hour by hour from OpenCost, copies a PriceBook's rates into the `pricebooks` table and stamps that book and its currency onto every row it writes to `provider_allocations`, then reports the outcome back onto the CostJob's status. |
| `SubscriptionChargeCollection` | `--mode=collectionjob` | Prices every activated Subscription hour by hour, writes the charge rows, refreshes each `Subscription.status.costs`, and releases the finalizer of Subscriptions whose charges have settled. |

The second type is the one that bills, and it is also the only component that removes Subscription finalizers. A cluster with no `SubscriptionChargeCollection` CostJob therefore accrues no charges and leaves deleted Subscriptions sitting in deletion for as long as it stays missing; each of them reports `Deleting=False` with reason `WaitingForCollectionJob`, which is the condition to look for when a Subscription will not go away. [How charges reach `Subscription.status.costs`](architecture.md#how-charges-reach-subscriptionstatuscosts) covers what each run computes.

## From interval to schedule

`spec.interval` is a duration, but it is not translated arithmetically. The reconciler matches the parsed duration against a fixed set of values and writes the matching cron expression onto the CronJob.

| `spec.interval` | Schedule written |
| --- | --- |
| `1h` | `0 * * * *` |
| `6h` | `0 */6 * * *` |
| `12h` | `0 */12 * * *` |
| `24h` (the default) | `0 0 * * *` |
| `1m` | `* * * * *` |
| `5m` | `*/5 * * * *` |
| anything else | `0 0 * * *` |

Because the match is on the parsed duration rather than on the string, `60m` behaves exactly like `1h` and `1440m` like `24h`.

!!! warning
    An unrecognised interval is not rejected. `2h`, `30m`, and `8h` are all accepted by the API and then fall through to the daily `0 0 * * *`, with nothing on the CostJob to say the value was ignored. After changing an interval, read the schedule back off the generated CronJob to confirm you got what you meant.

`1m` and `5m` exist for debugging. A run's unit of work is a whole hour, and it works on the hour it starts in, so a sub-hourly interval recomputes the current hour repeatedly rather than producing finer-grained data.

## The CronJob the operator generates

The generated CronJob is named `<costjob-name>-cronjob` and lives in the CostJob's namespace, with the CostJob as its controller owner reference, so deleting the CostJob takes the CronJob with it. Each reconcile overwrites the CronJob's `spec` and labels from the operator's template plus your CostJob's values, so hand edits to the CronJob do not survive the next reconcile; change the CostJob instead. Alongside the labels identifying the CostJob it came from, the operator sets `app.kubernetes.io/managed-by: finops-operator`.

Inside the pod template, the `loader` container gets the operator image, the `--mode` argument derived from `spec.type`, and the run's configuration as environment variables. The PostgreSQL connection string is not one of them: it goes into a Secret named `<costjob-name>-costjob-secret` in the same namespace, also owned by the CostJob, and reaches the container through a `secretKeyRef`.

That environment is merged by name rather than replaced. The reconciler overlays the variables it builds — the CostJob's own name and namespace, the OpenCost URL, the operator image, whichever timeouts are set, and the connection string reference — onto the variables already in the shipped pod template. Where a name appears in both, the entry the reconciler built wins and replaces the variable whole rather than field by field, because a literal value and a `valueFrom` reference cannot coexist. Where a name appears only in the template, it survives the merge and reaches the pod with the template's value. That is how `SCHEDULED_TIMESTAMP`, which the template wires to the CronJob's scheduled-timestamp annotation through a `fieldRef`, and `HOURS_LOOKBACK`, which the template sets to `5`, arrive on the container even though the reconciler never names them.

The merge runs against the operator's embedded template, though, never against the CronJob as it currently stands in the cluster, so a variable you add to the generated CronJob by hand is gone at the next reconcile whether or not the reconciler names it. [The allocation CronJob](../reference/configuration.md#the-allocation-cronjob) lists what ends up on the pod and which layer each value comes from.

## Resources for the run

`spec.resources` is an optional override for the compute resources of the generated CronJob's `loader` container. It takes an ordinary Kubernetes `ResourceRequirements` value, so the shape is the `requests` and `limits` you would write on any container.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: allocation-collection
  namespace: finops-operator-system
spec:
  type: ResourceCostCollection
  interval: 1h
  resources:
    requests:
      cpu: 200m
      memory: 256Mi
    limits:
      cpu: "1"
      memory: 1Gi
```

Unlike the environment, this is not merged. Setting `spec.resources` replaces the container's whole resources block, so a partial value does not inherit the template's defaults for the keys it leaves out: a `spec.resources` naming only `requests` produces a container with requests and no limits at all. Write out every request and limit you want the pod to have. Leaving the field unset is the way to keep the operator's own defaults, which the shipped pod template sets to requests of `50m` CPU and `64Mi` memory against limits of `500m` CPU and `256Mi` memory.

The override applies to either job type, because both generate their CronJob from the same template and the reconciler matches the `loader` container by name. Like the rest of the CronJob's `spec`, it is reapplied on every reconcile, so raising it on the CostJob is the only way to make it stick.

## Timeouts

Six optional fields bound the phases of a run. Each is a duration with a default set on the type, and the reconciler copies whatever is set onto the pod's environment; a field left unset falls back to that default.

| Field | Default | What it bounds |
| --- | --- | --- |
| `databaseInitTimeout` | `2m` | Opening the PostgreSQL connection |
| `kubernetesOperationTimeout` | `1m` | Reading the CostJob back from the API server |
| `openCostFetchTimeout` | `2m` | The OpenCost client, and each hour's fetch-and-stream |
| `databaseInsertTimeout` | `3m` | Finalizing allocation rows left over from earlier runs |
| `statusUpdateTimeout` | `1m` | Writing the execution record back to the CostJob |
| `httpClientTimeout` | `90s` | Nothing today. It is parsed and carried, but no request reads it; OpenCost calls are bounded by `openCostFetchTimeout`. |

These are read by the `ResourceCostCollection` run. The charge collector does not consult them, so raising a timeout on a `SubscriptionChargeCollection` CostJob has no effect.

A seventh field, `databaseViewsRefreshTimeout`, is retained for API compatibility and does nothing. It carries no default, the reconciler writes no variable for it onto the pod, and no code reads it, because the materialized view it used to refresh had no readers and was dropped. The field is still settable and is not pruned, so setting it is accepted and changes nothing. [databaseViewsRefreshTimeout](../reference/configuration.md#databaseviewsrefreshtimeout) covers why it is still there, and distinguishes it from `k8sOperationTimeout`, a chart key that renders a field name the CRD does not have and is therefore pruned outright.

## Reading a run's outcome

A `ResourceCostCollection` run records its outcome as an `ExecutionRecord` on its CostJob: the time it started, `Success` or `Failed`, how long it took, and, on failure, the error. The record goes on the front of `status.executionHistory`, which is capped at ten, so the list reads newest first and the eleventh run pushes the oldest out. The schema also permits `Error` on a record and `Pending` on `status.lastExecutionStatus`; nothing writes either, so treat `Failed` as the only failure value you will see.

`status.lastExecutionTime` and `status.lastExecutionStatus` track the most recent record whatever it says, and `status.lastSuccessfulExecutionTime` only moves on a `Success`. Comparing the two timestamps is the quickest way to spot a job that is running on schedule and failing every time.

The charge collector writes none of this. A `SubscriptionChargeCollection` CostJob's status therefore stays empty; watch its Jobs and pod logs, and the `CostsResolved` condition on the Subscriptions it prices, instead.

## Related

- [Collect cost data](../guides/collect-cost-data.md) walks through creating both CostJobs and checking that they ran.
- [How allocation data reaches PostgreSQL](architecture.md#how-allocation-data-reaches-postgresql) describes what one collection run writes.
- [`CostJobSpec`](../reference/api.md#costjobspec) and [`ExecutionRecord`](../reference/api.md#executionrecord) carry the field-level reference.
