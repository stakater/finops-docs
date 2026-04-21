# Define pricing with a PriceBook

This guide walks you through creating a `PriceBook` resource that sets per-resource rates for your cluster. By the end, OpenCost will use your rates to cost CPU, RAM, GPU, storage, and network usage, and those costs will feed into your Subscription charge breakdowns.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- A `FinOpsProvider` named `default` with `pricingModelSource: Pricebook`. See [Collect cost data](./collect-cost-data.md).
- `kubectl` access to the namespace where the operator is deployed (typically `finops-operator-system`).

## Steps

### 1. Choose your currency

The `currency` field accepts any three-letter ISO 4217 code (`USD`, `EUR`, `GBP`, etc.). All values in `status.costs` are reported in micro-units of this currency: divide any integer by `1,000,000` to get the human-readable amount. For example, `40000000` micros = `$40.00 USD`.

The only supported `valuationMode` today is `currency`. Set it to `currency` and omit any `percent` references.

### 2. Set your rates

The `rates` block holds per-resource rates expressed as decimal strings. All fields are optional; omit any resource type you do not want to track.

| Field | Unit | Realistic example |
|---|---|---|
| `cpuHour` | Currency per vCPU-hour | `"0.031"` — reflects a typical on-prem server amortized cost |
| `spotCPUHour` | Currency per spot vCPU-hour | `"0.012"` — lower rate for spot-capacity nodes |
| `ramGbHour` | Currency per GB-hour of RAM | `"0.004"` — proportional to DRAM cost per server |
| `spotRAMGbHour` | Currency per GB-hour of spot RAM | `"0.002"` — lower rate for spot-capacity nodes |
| `pvGbHour` | Currency per GB-hour of persistent volume | `"0.00012"` — reflects block-storage cost (e.g. SSD at ~$0.10/GB/month) |
| `gpuHour` | Currency per GPU-hour | `"1.80"` — reflects high-end GPU node amortized cost |
| `networkGiB` | Currency per GiB transferred | `"0.09"` — applied to zone, region, and internet egress |

When you apply a `PriceBook`, the operator rewrites the `finops-operator-custom-pricing-configs` ConfigMap in the OpenCost deployment namespace (default `finops-operator-system`) and restarts the OpenCost deployment if the ConfigMap content changed. If the ConfigMap is unchanged, the restart is skipped.

> **Side effect:** Every time a `PriceBook` is created or updated, OpenCost may restart. Schedule `PriceBook` changes during a maintenance window if your environment is sensitive to brief gaps in cost data collection.

### 3. Apply the PriceBook

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: PriceBook
metadata:
  name: acme-pricing
  namespace: finops-operator-system
spec:
  currency: USD
  valuationMode: currency
  rates:
    cpuHour: "0.031"
    spotCPUHour: "0.012"
    ramGbHour: "0.004"
    spotRAMGbHour: "0.002"
    pvGbHour: "0.00012"
    gpuHour: "1.80"
    networkGiB: "0.09"
```

Apply it:

```bash
kubectl apply -f pricebook.yaml
```

## Verify it worked

Check that the `PriceBook` is active:

```bash
kubectl get pricebook acme-pricing -n finops-operator-system -o yaml
```

Expected output includes:

```yaml
status:
  active: true
  conditions:
    - type: Ready
      status: "True"
```

Confirm the OpenCost ConfigMap was updated:

```bash
kubectl get configmap finops-operator-custom-pricing-configs -n finops-operator-system
```

The ConfigMap should have a `default.json` key. If the OpenCost pod restarted, you will see a recent `AGE` on the pod:

```bash
kubectl get pods -n finops-operator-system -l app=opencost
```

## Troubleshooting

If the `PriceBook` does not become `active: true` or OpenCost shows stale prices, see [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Collect cost data](./collect-cost-data.md) — set up a `FinOpsProvider` and a `CostJob` to pull allocation data.
- [Define an offering](./define-offering.md) — create a pricing contract that references the rates you set here.
- [PriceBook CRD reference](../reference/crds/pricebook.md)
