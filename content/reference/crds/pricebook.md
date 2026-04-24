# PriceBook (reference)

## Purpose

`PriceBook` defines the per-resource pricing rates used when the FinOps Operator computes infrastructure costs in custom-pricing mode. Use this resource when your environment requires pricing that differs from the default cloud provider rates — for example, on-premises clusters, chargeback scenarios, or negotiated cloud pricing. When a `PriceBook` is applied, the operator writes the rates into a ConfigMap that OpenCost reads on startup.

## Scope and name constraints

`PriceBook` is `namespaced`. Multiple `PriceBook` objects may exist across namespaces, but only the one the operator is configured to use becomes active (reflected by `status.active: true`).

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `currency` | string | yes | — | ISO 4217 three-letter currency code (e.g. `USD`, `EUR`). Must be uppercase. |
| `valuationMode` | string | yes | — | How rates are expressed. Use `currency`. The value `percent` is accepted by the API but has no effect today. |
| `rates` | object | required in practice | — | Per-resource rate definitions. All sub-fields are optional individually, but omitting all rates produces a pricing model with zero costs. |

### rates

All fields are strings representing decimal numbers in the configured currency. All fields are optional.

| Field | Unit | Example value |
|---|---|---|
| `cpuHour` | Currency per vCPU-hour | `"0.031"` |
| `spotCPUHour` | Currency per spot vCPU-hour | `"0.012"` |
| `ramGbHour` | Currency per GB-hour of RAM | `"0.004"` |
| `spotRAMGbHour` | Currency per GB-hour of spot RAM | `"0.002"` |
| `pvGbHour` | Currency per GB-hour of persistent volume | `"0.00012"` |
| `gpuHour` | Currency per GPU-hour | `"1.80"` |
| `networkGiB` | Currency per GiB transferred (zone, region, and internet egress) | `"0.09"` |

## Status

| Field | Type | Description |
|---|---|---|
| `active` | boolean | Set to `true` by the operator when this `PriceBook` is the one currently feeding OpenCost's pricing ConfigMap. |
| `conditions` | list | Standard Kubernetes conditions. |

## Validation rules

- `currency` must be a three-uppercase-letter ISO 4217 code.
- `valuationMode` must be either `currency` or `percent`. Use `currency`; `percent` is accepted by the API but has no effect today.
- All `rates` sub-fields must be valid decimal number strings when present.

## Lifecycle notes

When a `PriceBook` is created or updated, the operator rewrites the `finops-operator-custom-pricing-configs` ConfigMap (in the namespace where OpenCost is deployed, typically `finops-operator-system`). If the ConfigMap content changes, the operator restarts the OpenCost deployment so the new rates take effect. If the content is unchanged, no restart occurs.

The ConfigMap key `default.json` contains all pricing fields that OpenCost reads, including CPU, GPU, RAM, spot variants, storage, and network egress categories.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

## Examples

The following example defines a baseline on-premises pricing model with equal unit rates across all resource types.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: PriceBook
metadata:
  name: onprem-pricing
  namespace: finops-operator-system
spec:
  currency: USD
  valuationMode: currency
  rates:
    cpuHour: "1.0"
    ramGbHour: "1.0"
    pvGbHour: "1.0"
    gpuHour: "1.0"
    networkGiB: "1.0"
```

The following example defines a more differentiated pricing model with separate rates for spot and on-demand workloads.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: PriceBook
metadata:
  name: cloud-negotiated-pricing
  namespace: finops-operator-system
spec:
  currency: EUR
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

## Related guides

- [Define pricing](../../guides/define-pricing.md) — walk through creating a PriceBook and understanding the OpenCost restart side effect.
