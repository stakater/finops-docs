# Switch the active PriceBook

Exactly one PriceBook drives pricing at a time, and which one it is comes down to a single annotation you control. Keeping a second book around is how a new rate card gets reviewed as an ordinary manifest before it takes effect, and how you get back to the old rates if the new ones turn out wrong. This guide moves the active marker from one book to another.

## Prerequisites

- Two PriceBooks exist, and the one you are switching to already has the rates you want. [Define pricing with a PriceBook](define-pricing.md) covers authoring it.
- `kubectl` edit permission on both objects. Selection runs cluster-wide, but the objects are namespace-scoped, so pass `-n` on every command below.

## Step 1: Find out which book is active now

```sh
kubectl get pricebooks --all-namespaces
```

The book with `ACTIVE` set to `true` is the incumbent. Note its name and namespace; you need both in step 2.

## Step 2: Move the annotation

Set the marker on the target first. That one change is enough to switch: an annotated book wins outright, and the incumbent is demoted in the same reconcile. Taking the marker off the old book afterwards is cleanup, but it is not optional: leaving both annotated makes the next switch ambiguous, as the section below explains.

```sh
kubectl annotate pricebook onprem-2026h2 \
  -n finops-operator-system finops.stakater.com/active=true --overwrite

kubectl annotate pricebook onprem-standard \
  -n finops-operator-system finops.stakater.com/active-
```

The trailing `-` on the second command is how `kubectl` removes an annotation; `--overwrite` on the first matters only if the target already carries the annotation with some other value.

Each command triggers a reconcile, and on each one the operator lists every PriceBook in the cluster and picks a winner. It patches the winner `status.active: true` with an `Active` condition whose reason is `Activated`, and patches every other book `status.active: false` with reason `Demoted`. A demoted book also has its `status.activePricing` cleared, because it no longer describes what OpenCost is using.

Only the winner then touches OpenCost. It renders its rates into the `finops-operator-custom-pricing-configs` ConfigMap, and if the rendered document differs from what was already there, the operator patches the OpenCost Deployment's pod template to force a rolling restart, since OpenCost reads its pricing document only at startup. The document records the book it came from in its `description` field, so a switch to a differently named book changes the content and restarts OpenCost even when the two books carry identical rates.

## Step 3: Verify the switch

```sh
kubectl get pricebooks --all-namespaces
```

```text
NAMESPACE                 NAME             ACTIVE   READY
finops-operator-system    onprem-2026h2    true     True
finops-operator-system    onprem-standard  false    True
```

`ACTIVE` should have moved and `READY` on the new book should be `True`. Selection deliberately ignores readiness, so `ACTIVE true` with `READY False` means the switch took but the new rates did not parse: the book stays active, its `Ready` condition carries reason `PricebookParseFailed` naming the offending field, and the operator leaves the previous pricing document in place rather than pushing rates it could not read. Nothing is lost either way, so fix the rate on the new book or move the annotation back.

To confirm what OpenCost is now costing with, read `status.activePricing` on the new book. It is populated only on the active, ready book and mirrors the document the operator applied.

## If more than one book carries the annotation

Nothing stops you annotating two books, and the outcome is not "the one I annotated last". Annotations carry no timestamp, so among several annotated books the operator falls back to the newest `creationTimestamp`, tie-broken on namespace then name ascending. The rest are demoted as though they had never been annotated. Removing the marker from the outgoing book is what keeps the choice unambiguous, which is why step 2 has two commands rather than one.

## Rate changes are not retroactive

Switching books changes what gets priced from now on. It does not reprice what is already billed, and the difference shows up in three places:

- Every charge row records the unit price it was written with, and the collector resumes from each Subscription's last finalized hour, so billed hours keep the prices they were billed at. Hours not yet finalized are recomputed from the new rates.
- An Offering resolves `status.resolvedPricing` once and keeps it, because its spec is immutable. An Offering created before the switch goes on publishing the old unit prices, while a usage charge takes its rate from the `pricebooks` table row the collector stamped onto the allocation, so the two can disagree until you create a replacement Offering.
- Where a namespace that runs a `ResourceCostCollection` CostJob holds more than one PriceBook, usage can be priced from a book that is not the active one at all. [PriceBook](../concepts/pricebook.md) explains that path; keeping a single book in any collecting namespace avoids it, which is a reason to hold the outgoing book somewhere else.

!!! warning
    The Helm chart's optional default PriceBook, named `<release>-default-pricing`, does not mark itself active in a way the operator sees. Its template writes `finops.stakater.com/active: "true"` under `metadata.labels`, and the operator reads only the annotation of that name, so the marker has no effect on selection. A chart-provisioned book becomes active only by winning the bootstrap election, which is what happens when it is the only book on a fresh cluster, and it loses the slot to any book you annotate. If you want it chosen explicitly, annotate it yourself with the command in step 2.

## Related guides

- [Define pricing with a PriceBook](define-pricing.md) to author the book you are switching to.
- [PriceBook](../concepts/pricebook.md) for all three selection tiers and the status fields the operator writes.
