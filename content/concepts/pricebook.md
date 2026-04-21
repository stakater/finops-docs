# PriceBook

## What it is

PriceBook defines the per-resource rates the operator feeds to OpenCost — CPU-hour, spot CPU-hour, RAM GB-hour, spot RAM GB-hour, persistent-volume GB-hour, GPU-hour, and network GiB. All rates are expressed in a single ISO 4217 currency. When OpenCost computes allocation costs for your workloads, it uses these rates rather than cloud-provider list prices.

The only valuation mode that has effect today is `currency`. Setting rates in a PriceBook in currency mode causes the operator to write those values into a ConfigMap that OpenCost reads. If the ConfigMap content changes, the operator restarts OpenCost to pick up the new rates.

## When to use it

Use a PriceBook when you want to cost workloads at internal transfer prices, negotiated contract rates, or on-premises cost allocations rather than public cloud pricing. Platform engineers typically create one PriceBook per cluster and update it when rate agreements change. It is particularly useful in on-premises environments where OpenCost has no built-in pricing data to fall back on.

To take effect, a PriceBook requires `pricingModelSource: Pricebook` in the [FinOpsProvider](./finops-provider.md). Without that setting, the PriceBook is stored but OpenCost ignores it.

## How it fits

PriceBook feeds pricing into OpenCost, which is then consumed by [CostJob](./costjob.md) when it pulls allocation data. Subscription charges reported in [Subscription](./subscription.md) status reflect these rates indirectly — the `cpuHour`, `ramGbHour`, and other resource meters in `status.costs.breakdown` are populated from allocation data costed at PriceBook rates.

In BYO-OpenCost mode, the PriceBook is the primary mechanism by which pricing reaches OpenCost. In MTO-bundled mode, the [FinOpsProvider](./finops-provider.md) drives the OpenCost configuration and pricing changes come from the PriceBook ConfigMap update path. See [Operating modes](./operating-modes.md) for details.

## Key things to know

- PriceBook is `namespaced`. It typically lives in the same namespace as the operator (`finops-operator-system`).
- Only `valuationMode: currency` has effect today. The `percent` mode is accepted by the API but not acted on.
- At most one PriceBook is active at a time. The status field `active: true` marks which PriceBook is currently feeding OpenCost.
- When a PriceBook changes, the operator rewrites the `finops-operator-custom-pricing-configs` ConfigMap. If the ConfigMap content actually changed, the operator restarts the OpenCost deployment. If the rates are identical, no restart occurs.
- All rate values are strings representing decimal numbers in the configured currency (for example, `"0.031"` for $0.031 per vCPU-hour).
- The currency field must be a valid three-letter ISO 4217 code (for example, `USD`, `EUR`).
- Changing a PriceBook affects future allocation cost computations. Historical data already stored is not retroactively re-priced.

## Learn more

- [PriceBook reference](../reference/crds/pricebook.md) — full field specification including all rate fields.
- [Define pricing](../guides/define-pricing.md) — guide that creates a PriceBook alongside a FinOpsProvider.
- [Operating modes](./operating-modes.md) — explains how the PriceBook ConfigMap update path differs between modes.
