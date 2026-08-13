# PriceBook

A `PriceBook` is one currency and a set of per-unit rates, held as a namespace-scoped resource so a price list is reviewed and rolled out through the same manifests as everything else. Any number of PriceBooks can exist across the cluster; exactly one of them is active, and the active one is the rate source that OpenCost values usage with and that Offering pricing resolves against.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: PriceBook
metadata:
  name: onprem-standard
  namespace: finops-operator-system
  annotations:
    finops.stakater.com/active: "true"
spec:
  currency: USD
  valuationMode: currency
  rates:
    cpuHour: "0.031"
    ramGbHour: "0.004"
    pvGbHour: "0.00012"
    gpuHour: "1.8"
    networkGiB: "0.09"
```

## Rates

Rates are decimal strings rather than numbers, so the value you write is the value the operator parses. Each one is converted to micro-currency before any arithmetic happens, which keeps `"0.031"` exactly 31,000 micros instead of a floating-point approximation of it.

| Field | Rate is per | Example |
| --- | --- | --- |
| `cpuHour` | vCPU-hour | `"0.031"` |
| `spotCPUHour` | vCPU-hour on spot capacity | `"0.011"` |
| `ramGbHour` | GB-hour of memory | `"0.004"` |
| `spotRAMGbHour` | GB-hour of memory on spot capacity | `"0.002"` |
| `pvGbHour` | GB-hour of persistent volume | `"0.00012"` |
| `gpuHour` | GPU-hour | `"1.8"` |
| `networkGiB` | GiB of data transferred | `"0.09"` |

All seven are optional and all share the pattern `^([0-9]+(\.[0-9]+)?)?$`, which admits an empty string and rejects a negative number, an exponent, a thousands separator, and a currency symbol. Empty means unset, not free: an unset rate parses to zero micros, and it is written into OpenCost's pricing document as `"0"` so the document never carries a blank value.

Two of the seven only ever reach OpenCost. `spotCPUHour` and `spotRAMGbHour` are rendered into the `spotCPU` and `spotRAM` fields of the pricing document, and they are parsed and validated along with the rest, but no meter reads them: charges for CPU and memory are priced from `cpuHour` and `ramGbHour` whatever kind of node the workload ran on. `networkGiB` backs the `networkGb` meter and also fills all three of OpenCost's egress fields, so zone, region, and internet egress are priced identically. The `subscription` meter takes nothing from here, since a recurring fee is priced entirely from its Offering.

## Currency and valuation mode

`currency` is required and matched against `^[A-Z]{3}$`, so it takes an ISO 4217 code such as `USD` or `EUR`. It is a label, not a conversion instruction. Nothing in the operator holds an exchange rate. The currency is stamped onto every allocation row the rates price, and every micro-currency figure downstream, including a charge row's unit price, is denominated in it implicitly, so mixing currencies across PriceBooks means mixing them in your reports too.

`valuationMode` is required as well, and the only values it accepts are `currency` and `percent`. Only `currency` has an implementation behind it, and a `percent` book is not inert in the way you might hope: it still competes for the active slot, it is treated as ready without any rate parsing, and if it wins the slot its rates are still rendered into OpenCost's pricing document. What it cannot do is price an Offering, because pricing resolution passes over every book whose mode is not `currency`, so a percent book holding the active slot leaves each metered Offering not ready with `NoActivePricebook`. Keep the mode `currency`.

!!! warning
    `rates` is optional in the schema and nothing rejects a PriceBook that omits it, but the reconcile that renders the active book reads its rate fields unconditionally. Give every PriceBook a `rates` block, even a partial one.

## Choosing the active PriceBook

`status.active` belongs to the operator. The annotation `finops.stakater.com/active: "true"` belongs to you. On every PriceBook event the reconciler lists all books cluster-wide and picks one in three tiers, first match winning:

1. **Annotated.** A book carrying the annotation wins outright. An explicit choice always beats the operator's own.
1. **Sticky incumbent.** Failing that, a book already holding `status.active: true` keeps it. A newly created book never displaces a working one on its own.
1. **Election.** Failing both, the newest book is bootstrapped active. This is what happens on a fresh cluster and after the active book is deleted.

Where several books compete inside one tier, the newest `creationTimestamp` wins, tie-broken on namespace then name ascending. That tie-break is why annotating a second book without removing the annotation from the first does not mean "whichever I annotated last": annotations carry no timestamp, so the operator falls back to creation time and the newer book wins.

The chosen book is patched `status.active: true` with an `Active` condition whose reason is `Activated`. Every other book is patched `status.active: false` with reason `Demoted`, and a demoted book has its `status.activePricing` cleared, because it no longer describes what OpenCost is using. Editing rates on the book that is already active needs no annotation change at all: it stays active and re-prices.

## When the active book is not ready

Readiness is per-object and separate from selection. Each reconcile parses that one book's rates and records `Ready`. A rate that will not parse gives `Ready=False` with reason `PricebookParseFailed` and a message naming the first field that failed and the value it held. The pattern already turns away malformed shapes at admission, so what reaches this check is a value too large to express in micros. A book whose mode is not `currency` is ready trivially, having nothing to parse.

Selection ignores readiness on purpose. A book that wins selection while unready stays active and surfaces its error instead of failing over, so a typo produces a visible failure rather than a silent switch to different prices. While that is the case, the operator leaves the last good pricing document in place rather than pushing rates it could not read, and metered Offerings that try to resolve against the book go not ready with the same `PricebookParseFailed` reason. An Offering with metered resources and no active `currency` book at all goes not ready with `NoActivePricebook`.

## What the operator writes back

| Field | What it holds |
| --- | --- |
| `status.active` | `true` on the one selected book, `false` on the rest. Printed as the `Active` column by `kubectl get pricebooks`. |
| `status.ready` | `True` or `False` from parsing this book's own rates. Printed as the `Ready` column. |
| `status.conditions` | `Ready`, and `Active` with reason `Activated` or `Demoted`. Each condition carries the generation it was written for. |
| `status.activePricing` | A flat map mirroring the `default.json` document this book applied to OpenCost. Populated only on the active, ready book, and cleared on demotion, so it is the field to read when you want to know what OpenCost is actually costing with. |
| `status.observedGeneration` | Declared in the API but not populated at this release. Use the `observedGeneration` on the conditions instead. |

## Changing rates later

An edit re-renders the pricing document and, when the content genuinely changed, restarts OpenCost so it reads the new one. What an edit does not do is re-price history, and the reasons are worth keeping straight:

- Every charge row records the unit price it was written with, and the collector resumes from each Subscription's last finalized hour, so hours already billed keep the prices they were billed at.
- An Offering resolves `status.resolvedPricing` once and then keeps it, since its spec is immutable. A rate change does not update the unit prices an already-resolved Offering publishes; an Offering created afterwards picks the new rates up.
- Hours not yet finalized are recomputed from the new rates, and a usage charge takes its rate from the `pricebooks` table rather than from `status.resolvedPricing`. After an edit an old Offering can therefore publish one unit price while new charges are computed from another.

!!! warning
    One path does not consult `status.active`. An allocation-collecting run resolves its rates by listing PriceBooks in its own CostJob's namespace and taking the first one the API server returns, copying that book's rates into the `pricebooks` table and stamping the row's id onto every allocation it writes. Usage charges later read their per-unit rate through that stamp, so where several books share a namespace with a `ResourceCostCollection` CostJob, usage can be priced from a book that is not the active one. Keep a single PriceBook in any namespace that runs one. Two related edges: a book with no `rates` block at all fails the run outright, and a namespace with no PriceBook at all makes the run stamp an id of `0`, which matches no rate row, so its allocations carry no rate and are dropped when charges are computed.

## Related

- [Switch the active PriceBook](../guides/switch-active-pricebook.md) for moving the annotation, and [define pricing](../guides/define-pricing.md) for authoring the first book.
- [How the active PriceBook reaches OpenCost](architecture.md#how-the-active-pricebook-reaches-opencost) for the ConfigMap and restart mechanics.
- [`PriceRates`](../reference/api.md#pricerates) and [`PriceBookStatus`](../reference/api.md#pricebookstatus) for the field-level reference.
