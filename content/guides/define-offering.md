# Define an offering

An `Offering` is the priced thing a Subscription binds to, and its spec is frozen the moment you apply it. This guide authors one that charges a recurring subscription fee: choosing the price and the billing cadence, deciding whether deleted Subscriptions should be held for a while, applying the manifest, and confirming the operator resolved the pricing. It is for a platform engineer with edit rights in the namespace the Offering will live in.

## Prerequisites

- The FinOps Operator is [installed](../getting-started/installation/kubernetes.md) and its controller pod is running.
- `kubectl` edit permission in the namespace you are creating the Offering in, which is `finops-operator-system` throughout this guide.
- The price and the billing cadence agreed, because neither can be edited afterwards.
- A [`SubscriptionChargeCollection` CostJob](collect-cost-data.md) scheduled, if you want the fee to actually accrue into charge rows rather than only to be declared.

An Offering that charges a fee only needs no PriceBook. If you also want to bill measured consumption, read [price resource usage](price-resource-usage.md), which covers the `resourcePricing` half and the active PriceBook it depends on.

## Step 1: Settle every field before the first apply

The Offering's `spec` carries one CEL rule, `self == oldSelf`, so every update is refused with `offering spec is immutable`. That covers omissions as much as changes: an Offering created without a `compatibility` block can never grow one, and a fee of 40.00 stays 40.00 for as long as the object exists. [Offering](../concepts/offering.md#the-spec-cannot-change) explains why billing attribution requires that.

Two habits follow from it. Name the object for the terms it carries rather than for the service alone, so a later revision has an obvious name to take:

```text
managed-postgres-v1   # original terms; existing Subscriptions stay on this
managed-postgres-v2   # revised terms; new Subscriptions point here
```

And check the manifest against the API server before you commit to it, which catches a period format or an out-of-range price without creating anything:

```sh
kubectl apply -f offering.yaml --dry-run=server
```

When terms do need to change later, the move is to create a second Offering and migrate new Subscriptions onto it; existing Subscriptions cannot be re-pointed, because `offeringRef` is immutable too. [Replacing an Offering](../concepts/offering.md#replacing-an-offering) sets out that sequence.

## Step 2: Write the subscription fee

`spec.pricing` is required and both blocks inside it are optional. `pricing.subscriptionFee` is the one that accrues purely from a Subscription being active, with no reference to any workload:

| Field | Required | What it sets |
| --- | --- | --- |
| `priceMicros` | yes | The price of one tick in micro-currency, minimum `1`. 1,000,000 micros is 1.00 of the active PriceBook's currency, so `40000000` is 40.00. |
| `period` | yes | The tick length. Its format depends on `tickAlignment`, per step 3. |
| `tickAlignment` | yes | Where tick boundaries fall: `ActivatedAt`, `HourBoundary`, `DayBoundary`, or `MonthBoundary`. |
| `minPeriods` | no | Ticks that must elapse after activation before a deleted Subscription is released, minimum `1`. See step 4. |

Leaving `subscriptionFee` out entirely is valid. An Offering that declares only `resourcePricing` bills consumption and nothing else, and an Offering with an empty `pricing: {}` is admitted, becomes ready, and charges nothing at all.

## Step 3: Choose the tick alignment

`tickAlignment` picks the grid the tick boundaries sit on, and a second CEL rule ties the format of `period` to it. A mismatch is rejected at admission with `period must be a Go duration (e.g. '1h') for ActivatedAt alignment, or a plain integer for boundary alignments`.

| `tickAlignment` | `period` format | Examples | Where boundaries fall | Opening tick |
| --- | --- | --- | --- | --- |
| `ActivatedAt` | An integer with the suffix `h`, `m`, or `s` | `1h`, `30m`, `90s` | `activatedAt` plus multiples of `period`, a grid private to each Subscription | A full period, never prorated |
| `HourBoundary` | An integer count of hours | `"1"`, `"2"`, `"6"` | A cluster-wide grid of `period` hours, `1` giving every clock hour | Prorated against `period` hours |
| `DayBoundary` | An integer count of days | `"1"`, `"7"`, `"30"` | The midnight UTC after activation, then every `period` days from there | Prorated against `period` × 24 hours |
| `MonthBoundary` | An integer count of months | `"1"`, `"3"`, `"12"` | The 1st of a month at 00:00 UTC, `period` months on from the activation month | Prorated against a fixed 30 day 10 hour 30 minute month |

The accepted form under `ActivatedAt` is narrower than Go's duration syntax: `1h`, `90m`, and `3600s` all pass, `1h30m` does not. `period` is a string field in the schema, so quote it under the three boundary alignments, where an unquoted `1` is a YAML integer and the API server rejects it on type.

The choice is mostly about whether subscribers should tick together. `ActivatedAt` gives each Subscription its own cycle and never prorates, which keeps a per-subscriber invoice free of fractional opening charges. The boundary alignments line every Subscription in the cluster up with the same reporting windows, at the cost of a prorated opening tick and a closing tick that is always charged in full. [Billing model](../concepts/billing-model.md) has the tick arithmetic, the proration formula, and worked examples of both.

## Step 4: Decide whether to hold deleted Subscriptions

`minPeriods` is a cleanup guard and nothing else. It names a number of full ticks that must have elapsed since the Subscription's `activatedAt` before the `SubscriptionChargeCollection` job will take the finalizer off a Subscription that has been deleted. Until then the Kubernetes object stays visible with a deletion timestamp on it.

!!! warning
    `minPeriods` is not a minimum commitment and adds no charge. Nothing about the fee changes while the guard is waiting: billing carries on tick by tick under the ordinary rules, and a Subscription deleted before the count is reached is never charged for the ticks that did not run. If you need a floor on revenue, that has to come from the price and the period you choose, not from this field.

Two conditions gate the finalizer, and both must hold. The tick count is one. The other is that charges have been finalized through the Subscription's last billable hour, so a deleted Subscription always survives long enough for its closing hours to reach the charge table. Both are evaluated by the collection job, which means a cluster with no `SubscriptionChargeCollection` CostJob scheduled never releases a deleted Subscription at all.

The count is measured with the same tick counter the fee uses, so it inherits the alignment. `minPeriods: 24` against `HourBoundary` with `period: "1"` waits for 24 hourly boundaries after activation, which is a wait measured from activation rather than from the delete. A Subscription that had already been running for a month is released as soon as its closing charges settle.

## Step 5: Apply the Offering

A fee that starts when the subscriber does, charging 40.00 an hour with no proration, and holding a deleted Subscription until two hourly ticks have passed:

```yaml
# offering-managed-postgres.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: managed-postgres-v1
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 40000000
      minPeriods: 2
```

A fee aligned to the calendar instead, charging 500.00 a month on the 1st, with the opening tick prorated from the activation date:

```yaml
# offering-platform-base.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: platform-base
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: "1"
      tickAlignment: MonthBoundary
      priceMicros: 500000000
```

```sh
kubectl apply -f offering-managed-postgres.yaml -f offering-platform-base.yaml
```

## Step 6: Verify readiness and resolved pricing

```sh
kubectl get offerings -n finops-operator-system
```

```text
NAME                  READY
managed-postgres-v1   True
platform-base         True
```

`READY` is `status.ready`, and for a fee-only Offering it turns `True` as soon as the requirement check passes and pricing resolves. The `Ready` condition then carries reason `ValidationSucceeded`, and a `PricingResolved` condition sits alongside it with reason `PricingResolved`.

The confirmation worth reading is `status.resolvedPricing`, which is what the Offering publishes to every Subscription bound to it:

```sh
kubectl get offering managed-postgres-v1 -n finops-operator-system -o yaml
```

```yaml
status:
  ready: "True"
  resolvedPricing:
    resolvedAt: "2026-08-12T09:15:04Z"
    meters: []
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 40000000
      minPeriods: 2
```

`resolvedPricing.subscriptionFee` is the spec's block copied through verbatim, so seeing it there confirms the fee the operator will bill on rather than only the fee you asked for. `meters` is an empty list because this Offering prices no usage; [price resource usage](price-resource-usage.md) covers reading it when it is not.

Because the spec is immutable, this is computed once and then left alone. A `resolvedAt` that never moves is the expected state, not a stalled reconcile.

An Offering that stays `READY False` reports why on its conditions:

```sh
kubectl describe offering managed-postgres-v1 -n finops-operator-system
```

Reasons `RequiredOfferingNotFound` and `RequiredOfferingNotReady` point at a `compatibility.requiredOfferings` entry that does not resolve, and `CircularDependencyDetected` at a requirement loop. `NoActivePricebook` and `PricebookParseFailed` can only appear on an Offering that declares `resourcePricing`. [Status conditions](../reference/status-conditions.md) lists the full vocabulary.

## Related guides

- [Price resource usage](price-resource-usage.md) to add metered charges on top of the fee, or to bill usage without one.
- [Subscribe to an offering](subscribe-to-offering.md) to create the Subscription that accrues against these terms.
- [Billing model](../concepts/billing-model.md) for tick counting, proration, and the deactivation snap.
- [Offering](../concepts/offering.md) for immutability, the finalizer, and the replacement pattern in full.
