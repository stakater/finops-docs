# Collect cost data

This guide shows you how to configure a `FinOpsProvider` to tell the operator about your cloud environment, and how to create a `CostJob` of type `ResourceCostCollection` to schedule regular pulls of allocation data from OpenCost. After completing this guide, the operator will periodically fetch workload cost data and store it for Subscription charge computation.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- OpenCost deployed and reachable in the cluster (`OPENCOST_CONNECTION_STRING` configured on the manager).
- `kubectl` access to the operator namespace (typically `finops-operator-system`).
- A `PriceBook` in place if you want custom pricing applied to allocation data. See [Define pricing](./define-pricing.md).

## Steps

### 1. Create a FinOpsProvider

The `FinOpsProvider` is a cluster-scoped singleton. It must be named exactly `default`. Exactly one of the four provider options (`awsoptions`, `gcpoptions`, `azureoptions`, `onpremoptions`) must be set; any other combination is rejected at admission.

**On-premises** clusters do not use a cloud billing integration secret. Set only `pricingModelSource`:

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  onpremoptions:
    pricingModelSource: Pricebook
```

**AWS** clusters can additionally reference a Secret that holds cloud billing credentials:

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  awsoptions:
    cloudIntegrationSecret: aws-cloud-integration
    pricingModelSource: Pricebook
```

**GCP** and **Azure** follow the same pattern as AWS, using `gcpoptions` or `azureoptions` respectively, each accepting the same `cloudIntegrationSecret` and `pricingModelSource` fields.

Setting `pricingModelSource: Pricebook` tells the operator to enable OpenCost's custom-pricing path so that your `PriceBook`-derived ConfigMap is used for cost calculations.

Apply the appropriate provider:

```bash
kubectl apply -f finops-provider.yaml
```

### 2. Verify the FinOpsProvider

```bash
kubectl get finopsprovider default -o yaml
```

Look for:

```yaml
status:
  conditions:
    - type: Ready
      status: "True"
  lastSyncTime: "2026-04-20T10:00:00Z"
```

### 3. Create a CostJob for resource cost collection

A `CostJob` of type `ResourceCostCollection` instructs the operator to create a Kubernetes `CronJob` in the operator's namespace. That `CronJob` runs on the configured schedule and pulls allocation data from OpenCost.

The `interval` field controls how often the job runs. The following values are recognized and produce exact cron expressions:

| `interval` | Generated schedule | Meaning |
|---|---|---|
| `1m` | `* * * * *` | Every minute |
| `5m` | `*/5 * * * *` | Every 5 minutes |
| `1h` | `0 * * * *` | Top of every hour |
| `6h` | `0 */6 * * *` | Every 6 hours |
| `12h` | `0 */12 * * *` | Every 12 hours |
| `24h` | `0 0 * * *` | Daily at 00:00 UTC |

Any value not in this list falls back to the daily schedule `0 0 * * *`. Use one of the recognized values.

A `1h` interval is a good default for most environments:

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

Apply it:

```bash
kubectl apply -f resource-cost-collection.yaml
```

### 4. Understand the timeout fields

Each `CostJob` exposes timeout fields that control how long individual phases of the job are allowed to run. You can set these to tune the job for your environment; the defaults are listed below.

| Field | Default | What it controls |
|---|---|---|
| `databaseInitTimeout` | `2m` | Time allowed for the job to connect to and initialize the PostgreSQL database. |
| `kubernetesOperationTimeout` | `1m` | Time allowed for Kubernetes API calls made during the job run. |
| `openCostFetchTimeout` | `2m` | Time allowed to fetch allocation data from OpenCost. |
| `databaseInsertTimeout` | `3m` | Time allowed to write fetched data into the database. |
| `databaseViewsRefreshTimeout` | `5m` | Time allowed to refresh materialized views after insert. |
| `statusUpdateTimeout` | `1m` | Time allowed to write the execution result back to the `CostJob` status. |
| `httpClientTimeout` | `90s` | HTTP client timeout for outbound requests (OpenCost, cloud APIs). |

For most clusters the defaults are sufficient. Increase `openCostFetchTimeout` or `databaseInsertTimeout` if you see frequent `Error` or `Failed` statuses on the `CostJob` in large clusters.

A fully annotated example with custom timeouts:

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: CostJob
metadata:
  name: resource-cost-collection
  namespace: finops-operator-system
spec:
  type: ResourceCostCollection
  interval: 1h
  openCostFetchTimeout: 5m
  databaseInsertTimeout: 10m
  databaseViewsRefreshTimeout: 10m
```

## Verify it worked

Check the `CostJob` status:

```bash
kubectl get costjob resource-cost-collection -n finops-operator-system -o yaml
```

After the first scheduled run, the status should show:

```yaml
status:
  lastExecutionStatus: Success
  lastSuccessfulExecutionTime: "2026-04-20T11:00:00Z"
  lastExecutionTime: "2026-04-20T11:00:00Z"
```

Confirm the operator created a `CronJob` in the operator's namespace:

```bash
kubectl get cronjobs -n finops-operator-system
```

You should see an entry named after or associated with `resource-cost-collection`. The operator manages this `CronJob` — do not delete or edit it manually.

## Troubleshooting

If `lastExecutionStatus` stays `Pending` or shows `Failed`, see [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md). Common causes include an unreachable OpenCost URL, incorrect PostgreSQL credentials, or an unrecognized `interval` value.

## Related

- [Define pricing](./define-pricing.md) — create the `PriceBook` that OpenCost uses for custom rates.
- [Define an offering](./define-offering.md) — create a pricing contract backed by the rates collected here.
- [Read subscription costs](./read-subscription-costs.md) — understand how the `SubscriptionChargeCollection` job turns raw allocation data into per-Subscription costs.
- [CostJob CRD reference](../reference/crds/costjob.md)
- [FinOpsProvider CRD reference](../reference/crds/finopsprovider.md)
