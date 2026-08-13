# Collect cost data

Allocation data is what turns measured consumption into money. This guide declares the `FinOpsProvider` that records where the cluster runs, then creates the `ResourceCostCollection` CostJob whose generated CronJob pulls hourly allocation rows from OpenCost into PostgreSQL, and checks that a run actually happened. It is for whoever installed the operator and has cluster-scoped create permission plus edit rights in the operator's namespace.

## Prerequisites

- The FinOps Operator is [installed](../getting-started/installation/kubernetes.md) and its controller pod is running.
- OpenCost is reachable, and `OPENCOST_CONNECTION_STRING` is set on the controller. The value is passed through to each collection pod.
- PostgreSQL is reachable with the connection string the controller was installed with.
- A PriceBook exists in the namespace the CostJob will live in. [Define pricing with a PriceBook](define-pricing.md) covers writing one.

## Step 1: Declare the FinOpsProvider

`FinOpsProvider` is cluster-scoped and there is exactly one of it. Three CEL validation rules on the type, not a webhook, are what enforce that: the object has to be named `default`, and it has to carry exactly one of the four provider option blocks. The API server checks them on every create and update, so they hold whether or not the controller is running and `kubectl apply --dry-run=server` reports a bad object before you apply it. [Rules the API server enforces](../concepts/finops-provider.md#rules-the-api-server-enforces) quotes each rejection message.

On owned hardware there is no cloud bill to reconcile against, so `onpremoptions` carries only `pricingModelSource`:

```yaml
# finopsprovider.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  onpremoptions:
    pricingModelSource: Pricebook
```

On AWS, name the Secret that holds your cloud billing credentials. The operator moves the value into OpenCost's own cloud integration setting and never reads the credentials behind it:

```yaml
# finopsprovider.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  awsoptions:
    cloudIntegrationSecret: aws-cloud-integration
    pricingModelSource: Pricebook
```

GCP and Azure take the same two fields under `gcpoptions` and `azureoptions`. On all three cloud blocks the secret has to be non-empty to have any effect: each cloud branch in the reconciler requires the block to be present *and* the secret set, so an `awsoptions` block with no secret matches nothing and the reconcile logs `No valid provider option configured` and returns. If you run on a cloud but price everything from a PriceBook, either set the secret or declare `onpremoptions` instead.

```sh
kubectl apply -f finopsprovider.yaml
kubectl get finopsprovider default
```

!!! note
    Outside Multi Tenant Operator bundled mode, applying this object changes nothing about OpenCost. The pricing ConfigMap and the OpenCost restart are written by the PriceBook reconciler, and the provider path deliberately skips them so one change does not restart OpenCost twice. This reconciler also writes no status at all, so `lastSyncTime` and the conditions stay empty even on success; the controller log is where an applied provider shows up. Collection itself does not read the object, so the steps below work regardless. [FinOpsProvider](../concepts/finops-provider.md) covers what changes in MTO-bundled mode.

## Step 2: Create the collection CostJob

A `CostJob` declares a schedule rather than a job. The reconciler turns it into a Kubernetes CronJob it owns, and the collection work happens in the short-lived pods that CronJob fires.

`spec.interval` is a duration, but it is not translated arithmetically. Only `1h`, `6h`, `12h`, `24h`, `1m`, and `5m` map to distinct schedules, and the match is on the parsed duration, so `60m` behaves exactly like `1h`. Anything else, `2h` and `30m` included, is accepted at admission and then silently falls through to the daily `0 0 * * *`, with nothing on the CostJob to say the value was ignored, which is why step 4 reads the schedule back off the generated CronJob. Of those six, `1m` and `5m` are for debugging rather than finer data: a run's unit of work is a whole hour, so a sub-hourly interval just recomputes the current hour repeatedly. [From interval to schedule](../concepts/costjob.md#from-interval-to-schedule) gives the cron expression each value produces.

An hourly job matches the granularity the data has:

```yaml
# costjob-resource.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: resource-cost-collection
  namespace: finops-operator-system
spec:
  type: ResourceCostCollection
  interval: 1h
```

```sh
kubectl apply -f costjob-resource.yaml
```

The namespace matters more than it looks. Each run resolves its rates by listing PriceBooks in its own CostJob's namespace, copies that book's rates into the `pricebooks` table, and stamps the row's id onto every allocation it writes. A namespace with no PriceBook makes the run stamp an id of `0`, which matches no rate row, so those allocations carry no rate and are dropped when charges are computed; a PriceBook with no `rates` block at all fails the run outright. Keep one PriceBook, with rates, in the namespace that collects.

## Step 3: Raise a timeout if a run outgrows it

Six optional duration fields bound the phases of a run, and each has a default set on the type, so an omitted field is not unbounded. On a large cluster the two worth raising first are `openCostFetchTimeout`, which bounds each hour's fetch-and-stream, and `databaseInsertTimeout`:

```yaml
spec:
  type: ResourceCostCollection
  interval: 1h
  openCostFetchTimeout: 5m
  databaseInsertTimeout: 10m
```

Only the `ResourceCostCollection` run reads these, so setting them on a `SubscriptionChargeCollection` CostJob has no effect. [CostJob](../concepts/costjob.md#timeouts) lists all six with their defaults and what each one bounds, along with a seventh field that is retained for compatibility and does nothing.

## Step 4: Verify that a run happened

The generated CronJob is named after the CostJob, with `-cronjob` appended, and lives in the CostJob's namespace:

```sh
kubectl get cronjob resource-cost-collection-cronjob -n finops-operator-system \
  -o jsonpath='{.spec.schedule}{"\n"}'
```

That prints `0 * * * *` for the manifest above. If it prints `0 0 * * *` when you asked for something else, the interval was not one of the six recognised values and fell through to the daily default.

The CronJob is owned by the CostJob, so deleting the CostJob takes it with it, and each reconcile overwrites the CronJob's `spec` and labels; edit the CostJob rather than the CronJob. Alongside it the operator creates a Secret named `resource-cost-collection-costjob-secret`, also owned by the CostJob, which is how the PostgreSQL connection string reaches the pod.

Nothing is on the CostJob's status until the first run finishes, which for an hourly schedule means the top of the next hour. Once it has:

```sh
kubectl get costjob resource-cost-collection -n finops-operator-system \
  -o jsonpath='{.status.lastExecutionStatus}{"  "}{.status.lastSuccessfulExecutionTime}{"\n"}'
```

```text
Success  2026-04-20T11:00:00Z
```

`status.lastExecutionStatus` tracks the most recent run whatever it said, and `status.lastSuccessfulExecutionTime` only moves on a success, so comparing the second value against `status.lastExecutionTime` is the quickest way to spot a job that is running on schedule and failing every time. `kubectl get costjob` prints the interval and the last status as columns for a faster look, and `status.executionHistory` keeps the last ten records, newest first, with the error text on each failure. `Success` and `Failed` are the only values written; `Error` and `Pending` are in the schema and nothing sets them.

Only a `ResourceCostCollection` run writes any of this. A `SubscriptionChargeCollection` CostJob leaves its status empty, so watch its Jobs and pod logs instead.

## Related guides

- [Define pricing with a PriceBook](define-pricing.md) for the rates a collection run stamps onto its allocation rows.
- [Price resource usage](price-resource-usage.md) to charge a Subscription for the consumption collected here.
- [CostJob](../concepts/costjob.md) for the second job type, the generated CronJob's pod, and the full timeout list.
- [Troubleshooting](../troubleshooting.md) when a run reports `Failed`.
