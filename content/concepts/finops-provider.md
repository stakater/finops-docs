# FinOpsProvider

`FinOpsProvider` records where the cluster runs and how the operator should configure OpenCost for it. It is cluster-scoped, there is exactly one of it, and whoever installs the operator creates it once. It is also the only place in the API where a cloud vendor is named at all: rates come from a [PriceBook](pricebook.md), so no Offering, Subscription, or stored charge changes shape when the provider option changes.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: FinOpsProvider
metadata:
  name: default
spec:
  onpremoptions:
    pricingModelSource: Pricebook
```

## Rules the API server enforces

Three CEL validation rules are attached to the type itself, so the API server checks them on every create and update. No webhook is involved, which means `kubectl apply --dry-run=server` reports them and they hold whether or not the operator is running.

| What is checked | Message on rejection |
| --- | --- |
| `metadata.name` is `default` | `FinOpsProvider must be named 'default' (singleton).` |
| At least one option block is present | `At least one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set` |
| No more than one option block is present | `Exactly one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set` |

The name rule is what makes the resource a singleton. A second object would have to be named `default` as well, and the API server will not hold two cluster-scoped objects under one name. The last two rules overlap deliberately: an empty `spec` fails both, since it carries neither at least one option nor exactly one.

## The four option blocks

| Block | `cloudIntegrationSecret` | `pricingModelSource` |
| --- | --- | --- |
| `awsoptions` | yes | yes |
| `gcpoptions` | yes | yes |
| `azureoptions` | yes | yes |
| `onpremoptions` | field does not exist | yes |

`cloudIntegrationSecret` is passed straight through to OpenCost's own cloud integration setting; the operator moves the value and never reads the credentials behind it. `onpremoptions` has no such field, because on owned hardware there is no cloud bill to reconcile against.

Leaving `cloudIntegrationSecret` empty on a cloud block is not equivalent to choosing `onpremoptions`. Each cloud branch in the reconciler requires the block to be present *and* the secret to be non-empty, so an `awsoptions` block with no secret matches no branch: the reconcile logs `No valid provider option configured` and returns without touching OpenCost. If you run on a cloud but price everything from a PriceBook, either set the secret or declare `onpremoptions`.

## What `pricingModelSource` switches on

`Pricebook` is the only value the operator compares against. Any other string, including the empty default, leaves OpenCost's custom pricing switch alone. Under `onpremoptions` custom pricing is treated as enabled either way, because the on-prem branch turns it on before it looks at the field.

!!! note
    This field does not gate the pricing document. The PriceBook reconciler writes the active book's rates into the `finops-operator-custom-pricing-configs` ConfigMap regardless of what `pricingModelSource` says. What the field controls is whether the operator also enables OpenCost's `customPricing` for you in MTO-bundled mode, so on a bring-your-own deployment it records intent and changes nothing. See [how the active PriceBook reaches OpenCost](architecture.md#how-the-active-pricebook-reaches-opencost).

## What the reconciler does with it

How the provider is applied depends on whether OpenCost is bundled by Multi Tenant Operator. The operator reads that from the `MTO_ENABLED` environment variable once, while validating its own configuration at startup, and only the exact string `true` turns it on. Left unset, as it is by default, every provider takes the bring-your-own path below.

In MTO-bundled mode the reconciler patches the `OpenCost` custom resource in the `dependencies.tenantoperator.stakater.com` API group. A cloud block with a secret sets `spec.opencost.cloudIntegrationSecret` and turns `spec.opencost.cloudCost.enabled` on; custom pricing sets `spec.opencost.customPricing.enabled`. The patch is diffed against the object that was read, so an unchanged custom resource produces no write at all, and only a genuine change is followed by a restart of OpenCost.

Outside MTO-bundled mode this path deliberately does nothing. A bring-your-own OpenCost has its pricing ConfigMap written and its restart triggered by the PriceBook reconciler, and doing the same work here would restart OpenCost twice for one change. The consequence worth knowing is that on a bring-your-own deployment the FinOpsProvider's own effect is limited to being valid and present; the pricing path runs entirely through PriceBook.

!!! warning
    `status` declares `lastSyncTime`, `observedGeneration`, and `conditions`, but this reconciler writes no status at all, so all three stay empty even after a successful sync. Confirm a provider was applied from the operator logs, or from the `OpenCost` custom resource in MTO-bundled mode, rather than from `status`.

## Related

- [Define pricing](../guides/define-pricing.md) creates a provider and a PriceBook together.
- [`FinOpsProviderSpec`](../reference/api.md#finopsproviderspec) and [`OnPremOptions`](../reference/api.md#onpremoptions) carry the field-level reference.
