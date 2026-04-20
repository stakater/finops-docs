# FinOpsProvider

## What it is

FinOpsProvider is the cluster-scoped configuration object that tells the operator which cloud environment the cluster runs in and how pricing data reaches OpenCost. It is the starting point for every other resource in the system: without a FinOpsProvider, the operator does not know whether it is running on AWS, GCP, Azure, or on-premises infrastructure, and it cannot configure the pricing path that PriceBook and CostJob depend on.

The object specifies exactly one cloud option block — either `awsoptions`, `gcpoptions`, `azureoptions`, or `onpremoptions`. It also controls whether OpenCost uses cloud-provider billing integration (via a credentials secret) or PriceBook-driven custom pricing (via `pricingModelSource: Pricebook`).

## When to use it

Every cluster running the FinOps Operator needs exactly one FinOpsProvider. Platform engineers create it once during initial setup and rarely touch it after that. You reach for it again when you need to change the cloud environment declaration, rotate the cloud-billing credentials secret, or switch the pricing model source between cloud-native rates and a PriceBook.

## How it fits

FinOpsProvider sits at the root of the configuration graph. In MTO-bundled mode, it drives changes to the OpenCost custom resource managed by the Multi-Dependency Operator. In BYO-OpenCost mode, it declares intent but pricing changes are applied to OpenCost by the [PriceBook](./pricebook.md) instead.

When `pricingModelSource: Pricebook` is set, the operator enables OpenCost's custom-pricing path. This means the rates defined in your [PriceBook](./pricebook.md) will be used when [CostJob](./costjob.md) pulls allocation data. Without this setting, OpenCost uses cloud-provider list prices, and PriceBook has no effect.

## Key things to know

- There is exactly one FinOpsProvider per cluster. The object must be named `default`; any other name is rejected at admission.
- Exactly one cloud option block must be present. Setting none or more than one is rejected.
- `pricingModelSource: Pricebook` is the only value that changes behavior today. It enables OpenCost's custom-pricing path so that PriceBook-derived rates are used.
- In MTO-bundled mode, creating or updating a FinOpsProvider patches the OpenCost CR and triggers an OpenCost restart after MDO has reconciled.
- In BYO-OpenCost mode, FinOpsProvider changes have no direct effect on OpenCost. Pricing changes are applied by the PriceBook instead.
- On-Prem does not accept a `cloudIntegrationSecret`; the only valid field inside `onpremoptions` is `pricingModelSource`.
- The status field `lastSyncTime` records when the operator last synced the OpenCost configuration.

## Learn more

- [FinOpsProvider reference](../reference/crds/finopsprovider.md) — full field specification.
- [Define pricing](../guides/define-pricing.md) — guide that walks through creating a FinOpsProvider alongside a PriceBook.
- [Operating modes](./operating-modes.md) — explains the difference between MTO-bundled and BYO-OpenCost modes in detail.
