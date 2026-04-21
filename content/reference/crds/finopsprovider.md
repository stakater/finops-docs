# FinOpsProvider (reference)

## Purpose

`FinOpsProvider` is the cluster-wide configuration anchor for the FinOps Operator. It tells the operator which cloud (or on-premises) environment it is running in, where to find cloud billing credentials, and how pricing data is sourced. Create or update this resource when you want to change the cloud provider configuration or switch the pricing model between default cloud rates and a custom `PriceBook`.

## Scope and name constraints

`FinOpsProvider` is cluster-scoped. Exactly one instance may exist, and it must be named `default`. Any object submitted with a different name is rejected at admission.

## Spec

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `awsoptions` | object | one-of | — | AWS-specific options. Mutually exclusive with `gcpoptions`, `azureoptions`, and `onpremoptions`. |
| `gcpoptions` | object | one-of | — | GCP-specific options. Mutually exclusive with the other provider option blocks. |
| `azureoptions` | object | one-of | — | Azure-specific options. Mutually exclusive with the other provider option blocks. |
| `onpremoptions` | object | one-of | — | On-premises options. Mutually exclusive with the other provider option blocks. |

Exactly one of the four option blocks must be set. Providing none or more than one is rejected at admission.

### `awsoptions` / `gcpoptions` / `azureoptions`

These three blocks share the same fields.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `cloudIntegrationSecret` | string | optional | — | Name of the Kubernetes Secret that holds cloud billing credentials for OpenCost. |
| `pricingModelSource` | string | optional | — | How pricing is sourced. Set to `Pricebook` to route pricing through the `PriceBook`-derived ConfigMap. Any other value or omission uses the cloud provider's default pricing. |

### `onpremoptions`

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `pricingModelSource` | string | optional | — | Same semantics as above. `Pricebook` enables custom pricing via a `PriceBook` resource. On-premises deployments do not use `cloudIntegrationSecret`. |

## Status

| Field | Type | Description |
|---|---|---|
| `lastSyncTime` | timestamp | When the operator last synced the OpenCost configuration. |
| `conditions` | list | Standard Kubernetes conditions reflecting operator health. |

## Validation rules

- The object must be named `default`. Any other name is rejected.
- Exactly one of `awsoptions`, `gcpoptions`, `azureoptions`, or `onpremoptions` must be present. Zero or two-or-more is rejected.
- `onpremoptions` does not accept `cloudIntegrationSecret`.

## Lifecycle notes

Behavior depends on the operating mode the operator is running in. See [Operating modes](../../concepts/operating-modes.md) for the distinction between MTO-bundled and BYO-OpenCost modes.

- **MTO-bundled mode:** creating or updating `FinOpsProvider` patches the OpenCost custom resource, enabling `cloudCost` (and, when `pricingModelSource: Pricebook`, `customPricing`). The operator then triggers an OpenCost restart after the managed deployment has reconciled.
- **BYO-OpenCost mode:** changes to `FinOpsProvider` do not directly affect OpenCost. Pricing changes are applied when the active PriceBook is updated.

See [Status conditions](../status-conditions.md) for the full list of reasons this resource emits.

## Examples

The following example configures the operator for an on-premises environment using a custom `PriceBook` for pricing.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  onpremoptions:
    pricingModelSource: Pricebook
```

The following example configures the operator for AWS with a cloud billing integration secret and `PriceBook`-based pricing.

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

## Related guides

- [Collect cost data](../../guides/collect-cost-data.md) — create a FinOpsProvider for your cloud and schedule allocation collection.
