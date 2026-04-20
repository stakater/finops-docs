# Operating modes

The same operator image runs in two modes, selected at startup by the `MTO_ENABLED` environment variable on the manager container. The mode determines how the operator interacts with OpenCost — specifically, how pricing configuration reaches the OpenCost deployment.

## MTO-bundled mode

In MTO-bundled mode (`MTO_ENABLED=true`), the cluster uses Stakater's Multi-Dependency Operator (MDO) to manage the OpenCost installation. The FinOps Operator works alongside MDO rather than directly managing the OpenCost deployment.

When you create or update a [FinOpsProvider](./finops-provider.md), the operator patches the OpenCost custom resource that MDO manages — setting `cloudIntegrationSecret`, enabling cloud cost integration, and, if `pricingModelSource: Pricebook` is set, enabling OpenCost's custom-pricing path. After MDO reconciles the OpenCost CR, the operator triggers an OpenCost restart to load the updated configuration.

## BYO-OpenCost mode

In BYO-OpenCost mode (the default, active when `MTO_ENABLED` is unset or any value other than the literal string `"true"`), the operator manages OpenCost configuration directly without MDO involvement.

The operator maintains a ConfigMap named `finops-operator-custom-pricing-configs` in the OpenCost deployment's namespace. When a [PriceBook](./pricebook.md) changes, the operator rewrites this ConfigMap with the new pricing JSON. If the ConfigMap content actually changed, the operator restarts the OpenCost deployment so that OpenCost picks up the new rates. If the rates are identical to what is already in the ConfigMap, no restart occurs.

In this mode, changes to the FinOpsProvider do not directly affect OpenCost. Pricing changes flow through the PriceBook instead.

## How to choose

Use MTO-bundled mode if your cluster already uses Stakater's MDO to manage OpenCost. The operator integrates with MDO's reconciliation loop rather than competing with it.

Use BYO-OpenCost mode (the default) if you installed OpenCost yourself or through any mechanism other than MDO. This mode does not require any additional operators and is the correct choice for most standalone installations.

If you are unsure, start with BYO-OpenCost mode. You can switch modes later by changing the `MTO_ENABLED` value and restarting the operator.

## How it's selected

The mode is controlled by the `MTO_ENABLED` environment variable on the manager container. Set it to the literal string `"true"` to enable MTO-bundled mode; leave it unset or set it to any other value for BYO-OpenCost mode.

When installing via Helm, the corresponding value is `controllerManager.manager.env.mtoEnabled`. See the [configuration reference](../reference/configuration.md) for the full list of environment variables and Helm values.

## Learn more

- [FinOpsProvider](../reference/crds/finopsprovider.md) — how the cloud option block and `pricingModelSource` drive OpenCost configuration.
- [PriceBook](../reference/crds/pricebook.md) — how rate changes update the pricing ConfigMap and trigger OpenCost restarts.
- [Configuration reference](../reference/configuration.md) — all environment variables and Helm values for the operator.
