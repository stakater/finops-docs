# Define pricing with a PriceBook

A `PriceBook` is the rate card the operator applies to OpenCost and that a metered Offering resolves its unit prices from. This guide writes the first one, applies it in the namespace the operator runs in, and confirms the operator selected it and pushed it to OpenCost. It is for whoever owns the numbers: a platform or FinOps engineer with edit rights in that namespace.

## Prerequisites

- The FinOps Operator is [installed](../getting-started/installation/kubernetes.md) and its controller pod is running.
- `kubectl` edit permission in the operator's namespace, which is `finops-operator-system` throughout this guide.
- The rates you intend to charge, and the currency to express them in.

## Step 1: Choose the currency and the valuation mode

`spec.currency` is required and matched against `^[A-Z]{3}$`, so it takes an ISO 4217 code such as `USD` or `EUR`. It is a label rather than a conversion instruction: nothing in the operator holds an exchange rate. The code is stamped onto every allocation row these rates price, and every micro-currency figure further downstream is denominated in it implicitly, so a cluster is easiest to read when one currency covers all of it.

`spec.valuationMode` is required too, and the schema admits `currency` and `percent`. Set it to `currency`. A `percent` book is not inert: it competes for the active slot like any other and its rates still reach OpenCost, but pricing resolution passes over it, which leaves every metered Offering not ready with reason `NoActivePricebook`.

## Step 2: Write the rates

`spec.rates` holds seven optional per-unit rates.

| Field | Rate is per |
| --- | --- |
| `cpuHour` | vCPU-hour |
| `spotCPUHour` | vCPU-hour on spot capacity |
| `ramGbHour` | GB-hour of memory |
| `spotRAMGbHour` | GB-hour of memory on spot capacity |
| `pvGbHour` | GB-hour of persistent volume |
| `gpuHour` | GPU-hour |
| `networkGiB` | GiB of data transferred |

Each value is a string matched against `^([0-9]+(\.[0-9]+)?)?$`: digits, at most one decimal point, and nothing else. A sign, an exponent such as `3e-2`, a thousands separator, and a currency symbol are all turned away at admission. The fields are typed `string` in the CRD, so quote the value; an unquoted `0.031` is a YAML number and the API server rejects it on type.

Omitting a rate does not exclude that resource from costing; it prices it at zero. An unset rate parses to zero micros, and the operator writes it into the pricing document as `"0"` rather than as a blank, so the document is explicit about what it is valuing at nothing.

Three of the fields behave differently from how they read, which is worth knowing before you spend time tuning them. `spotCPUHour` and `spotRAMGbHour` are carried into OpenCost's document and validated with the rest, but no meter reads them, so a charge for CPU or memory comes from `cpuHour` and `ramGbHour` whatever kind of node the workload ran on. `networkGiB` fills all three of OpenCost's egress fields at once, which prices zone, region, and internet egress identically. [PriceBook](../concepts/pricebook.md#rates) covers what each rate feeds in full.

## Step 3: Apply the PriceBook

```yaml
# pricebook.yaml
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
    gpuHour: "1.80"
    networkGiB: "0.09"
```

```sh
kubectl apply -f pricebook.yaml
```

The `finops.stakater.com/active: "true"` annotation is how you tell the operator which book drives pricing. On a cluster that holds no other PriceBook the operator would bootstrap this one active without it, but setting it records the decision on the object, and it keeps this book chosen when a second one is added later. [Switch the active PriceBook](switch-active-pricebook.md) covers moving that annotation to a different book.

!!! warning
    Applying or editing the active PriceBook rewrites the `finops-operator-custom-pricing-configs` ConfigMap, and when the rendered document genuinely changed the operator restarts the OpenCost Deployment so it reads the new one. An unchanged document skips the restart. OpenCost only reads its pricing document at startup, so there is no way to change rates without that restart; plan rate changes accordingly if your environment is sensitive to OpenCost bouncing.

## Step 4: Verify the operator selected it

```sh
kubectl get pricebooks -n finops-operator-system
```

`ACTIVE` reads `true` on the one book the operator chose and `READY` reads `True` once that book's own rates parsed. The two are independent, so read both:

```sh
kubectl get pricebook onprem-standard -n finops-operator-system \
  -o jsonpath='{.status.active} {.status.ready}{"\n"}'
```

Then confirm that what OpenCost is costing with is this book, by reading the document the operator applied back off the status:

```sh
kubectl get pricebook onprem-standard -n finops-operator-system -o yaml
```

```yaml
status:
  active: true
  ready: "True"
  activePricing:
    CPU: "0.031"
    GPU: "1.80"
    RAM: "0.004"
    description: 'Pricebook from: onprem-standard'
    internetNetworkEgress: "0.09"
    provider: custom
    regionNetworkEgress: "0.09"
    spotCPU: "0"
    spotRAM: "0"
    storage: "0.00012"
    zoneNetworkEgress: "0.09"
```

`status.activePricing` mirrors the `default.json` document that went into the ConfigMap, and the operator populates it only on the book that is both active and ready, clearing it again on demotion. Its presence is therefore the confirmation you want: the rates in it are the rates that went into the ConfigMap OpenCost reads. The two `"0"` entries are the spot rates this example left unset.

If `READY` is `False`, the `Ready` condition carries reason `PricebookParseFailed` and a message naming the first rate field that failed and the value it held. A book that wins selection while unready stays active and surfaces the error rather than failing over, so the last good pricing document stays in place until you fix the value.

## Related guides

- [Switch the active PriceBook](switch-active-pricebook.md) to move pricing onto a second book.
- [Collect cost data](collect-cost-data.md) to schedule the allocation collection these rates price.
- [Define an offering](define-offering.md) to build a priced offering on top of them.
- [PriceBook](../concepts/pricebook.md) for the selection tiers, the status fields, and what an edit does to history.
