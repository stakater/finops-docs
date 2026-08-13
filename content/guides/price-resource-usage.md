# Price resource usage

`pricing.resourcePricing` is how an Offering bills what a workload actually consumed. It carries no rates of its own: each entry names a meter, and the per-unit price comes from the active PriceBook with the entry's margin applied on top. This guide picks the meters, sets the margin that turns a cost rate into a sell rate, and reads the effective prices back off the Offering's status. It is for whoever sets the markup, working alongside whoever owns the PriceBook.

## Prerequisites

- A PriceBook that is both active and `valuationMode: currency`, carrying a rate for every meter you intend to price. [Define pricing with a PriceBook](define-pricing.md) authors one.
- A [`ResourceCostCollection` CostJob](collect-cost-data.md) collecting allocations, and a `SubscriptionChargeCollection` one turning them into charges.
- `kubectl` edit permission in the namespace the Offering lives in, which is `finops-operator-system` throughout this guide.
- The markup you intend to apply, as either a fixed addition or a multiplier.

## Step 1: Pick the meters

Six names are admitted, and five of them bill something. Each reads its own signal out of the allocation rows the collector wrote and integrates it over the part of the hour the Subscription was active:

| Meter | Priced per | Quantity billed |
| --- | --- | --- |
| `cpuHour` | Core-hour | Average cores used across the row, integrated over the billable span |
| `gpuHour` | GPU-hour | Average number of GPUs actively used, integrated the same way |
| `ramGbHour` | GiB-hour | Average memory in use, converted from bytes at 2^30 per GiB |
| `pvGbHour` | GiB-hour | Persistent volume capacity attached, from the byte-hours integral rather than a capacity snapshot |
| `networkGb` | GiB | Data transferred plus data received, summed across both directions |

`networkGb` is the one with no time dimension, which is why its name has no `Hour` in it. The rate is per GiB moved, so a Subscription that shifts a fixed amount of data pays the same whether it took a minute or a day. The activation and deactivation instants still trim its first and last hour, because the collector clamps every row to the Subscription's active interval, but there is no per-hour multiplier.

`cpuHour` and `gpuHour` are billed on utilization rather than on what a pod requested, so a workload that reserves eight GPUs and drives two is charged for two. `gpuHour` reads zero where GPU profiling is not measuring anything, which makes an unmonitored GPU node look free.

!!! note
    The schema also accepts `subscription` as a meter name, but no usage calculator is registered for it. An entry named `subscription` resolves to a unit price and then never produces a charge; the recurring fee belongs in `subscriptionFee`, which [define an offering](define-offering.md) covers.

## Step 2: Set the margin per meter

`margins` on an entry adjusts the PriceBook rate for that one meter. It has two fields and they are two different modes:

| Field | Unit | Effect on the rate |
| --- | --- | --- |
| `absoluteMicros` | Micro-currency, 1,000,000 to 1.00 of the PriceBook's currency | Adds a fixed amount per unit |
| `factorMilli` | Milli-units, `1000` being 1.000x | Multiplies, so `1150` is a 15 percent markup and `980` a 2 percent discount |

Three CEL rules on `margins` police the pair, all evaluated at admission:

| Rule | Message on rejection |
| --- | --- |
| Only one mode per meter | `absoluteMicros and factorMilli are mutually exclusive — set only one` |
| No negative addition | `absoluteMicros must be >= 0` |
| No negative factor | `factorMilli must be >= 0` |

The non-negativity is not arbitrary. A usage meter never credits, so a per-unit price driven below zero has no meaning and is clamped to zero if it ever arrives. That makes `factorMilli` the only way to express a discount: `980` charges 98 percent of the PriceBook rate, and there is no negative `absoluteMicros` that would do the same job.

Against the `0.031` per core-hour and `1.80` per GPU-hour of the PriceBook in [define pricing](define-pricing.md), the four cases work out as:

| Entry | PriceBook rate in micros | Effective unit price |
| --- | --- | --- |
| `cpuHour` with no `margins` | `31000` | `31000` |
| `cpuHour` with `absoluteMicros: 200` | `31000` | `31200` |
| `cpuHour` with `factorMilli: 1150` | `31000` | `35650` |
| `gpuHour` with `factorMilli: 1200` | `1800000` | `2160000` |

Omitting `margins` altogether is valid and resolves the PriceBook rate unchanged, which is the shape to use when the Offering is meant to pass cost through at cost.

Two details matter when you reconcile a charge against these numbers. The margin is applied to each allocation row's own rate before that rate is multiplied by the row's units, not to the summed charge afterwards. And the meter's rate is taken from the PriceBook recorded against the allocation row, so a row that carries no rate for a meter is dropped from that meter's charge rather than being billed at the margin alone.

## Step 3: Apply the Offering

Both pricing blocks are optional, so an Offering can price usage with no recurring fee at all:

```yaml
# offering-gpu-workload.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: gpu-workload
  namespace: finops-operator-system
spec:
  pricing:
    resourcePricing:
      - name: gpuHour
        margins:
          factorMilli: 1200
      - name: cpuHour
        margins:
          absoluteMicros: 200
```

```sh
kubectl apply -f offering-gpu-workload.yaml
```

List each meter once. The spec's list is a plain array, so nothing at admission stops two entries naming the same meter, while the resolved list the operator writes back to `status` is keyed on `name`. As with any Offering the spec is immutable after this apply, which means a margin change is a new Offering under a new name.

## Step 4: Declare usage sources on the Subscription

Declaring meters is only half of what it takes to bill them. The collector builds usage calculators only for a Subscription that has activated and declares at least one `spec.usageSources` entry, so a Subscription with none is charged its Offering's subscription fee and nothing else, however much `resourcePricing` the Offering carries. Nothing reports this as an error, which makes it an easy gap to miss.

```yaml
# subscription-acme-gpu.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-gpu
  namespace: finops-operator-system
spec:
  offeringRef:
    name: gpu-workload
    namespace: finops-operator-system
  usageSources:
    - namespace: acme-training
```

```sh
kubectl apply -f subscription-acme-gpu.yaml
```

`offeringRef.namespace` is required and is never filled in from the Subscription's own namespace, so it has to be written out even when the two match. [Declaring usage sources](../concepts/subscription.md#declaring-usage-sources) covers how the entries select allocation rows, and [subscribe to an offering](subscribe-to-offering.md) covers the rest of the Subscription.

## Step 5: Read the effective unit prices

`status.resolvedPricing.meters` is where the arithmetic from step 2 surfaces, one entry per meter the Offering declares:

```sh
kubectl get offering gpu-workload -n finops-operator-system -o yaml
```

```yaml
status:
  ready: "True"
  resolvedPricing:
    resolvedAt: "2026-08-12T09:15:04Z"
    meters:
      - name: gpuHour
        unitPriceMicros: 2160000
      - name: cpuHour
        unitPriceMicros: 31200
```

`unitPriceMicros` is the price a subscriber pays for one unit of that meter: the active PriceBook's rate with the entry's margin already applied. Divide by 1,000,000 to read it in currency, so `2160000` is 2.16 per GPU-hour. Checking these two numbers against what you intended is the quickest way to catch a `factorMilli` that was meant to be a percentage, or micros entered as currency.

The list is resolved once and then left alone, because the spec cannot change. Editing the PriceBook afterwards does not move an already-resolved `unitPriceMicros`, while a usage charge takes its rate from the PriceBook recorded with the allocation row, so the two can disagree after a rate change. [Changing rates later](../concepts/pricebook.md#changing-rates-later) covers the consequences and [switch the active PriceBook](switch-active-pricebook.md) the procedure.

!!! note
    `includedUsage`, an allowance of free usage per subscriber, is not available. The field is commented out in the API types, so it cannot be set on a meter, and the matching `status.resolvedPricing.meters[].includedUsage` is never populated. Model an allowance somewhere other than the Offering until it lands.

## When pricing does not resolve

An Offering that declares `resourcePricing` needs an active PriceBook whose `valuationMode` is `currency`. Without one it stays not ready, with `PricingResolved=False` and reason `NoActivePricebook`:

```sh
kubectl describe offering gpu-workload -n finops-operator-system
```

```text
Type              Status  Reason              Message
Ready             False   NoActivePricebook   offering finops-operator-system/gpu-workload: no active pricebook to resolve metered pricing
PricingResolved   False   NoActivePricebook   offering finops-operator-system/gpu-workload: no active pricebook to resolve metered pricing
```

The operator refuses rather than publishing something. With no rates to read, every meter's base would be zero, and a resolved price would then be the margin on its own: an Offering with `absoluteMicros: 200` would publish 200 micros per core-hour, which is the internal markup masquerading as the sell price. Staying not ready keeps that out of `status.resolvedPricing`, and out of the hands of any Subscription reading it. Reconciliation keeps retrying, so activating a PriceBook is enough to clear the condition with no edit to the Offering.

Reason `PricebookParseFailed` means a book was found but one of the rates the Offering needs could not be read; its message names the meter and the offending value. Fix the rate on the PriceBook. An Offering with no `resourcePricing` at all needs no PriceBook and resolves either way.

## Related guides

- [Define an offering](define-offering.md) for the recurring fee, immutability, and the versioning pattern.
- [Define pricing with a PriceBook](define-pricing.md) for the rates these margins are applied to.
- [Collect cost data](collect-cost-data.md) for the allocation collection that produces the usage in the first place.
- [Read subscription costs](read-subscription-costs.md) for the charges these prices produce.
