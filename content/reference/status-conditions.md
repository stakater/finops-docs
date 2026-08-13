# Status conditions

A condition is a signal the operator writes onto a resource to say what it decided and why. Read them with `kubectl describe <kind> <name>`, or pull the whole set at once:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{range .status.conditions[*]}{.type}{"  "}{.status}{"  "}{.reason}{"\n"}{end}'
```

Five condition types exist across the five kinds, and no kind carries all five. Every condition the operator writes records the `metadata.generation` it was written for, so an `observedGeneration` behind the object's current generation means the reconciler has not caught up with your last edit yet.

## Condition types

| Type | Written on | Meaning |
| --- | --- | --- |
| `Ready` | PriceBook, Offering, Subscription | The resource is usable. On an Offering and a PriceBook it is mirrored into the `status.ready` field, which is what `kubectl get` shows in its `READY` column. |
| `Active` | PriceBook, Subscription | Which PriceBook holds the active slot, and whether a Subscription's billing relationship is open. |
| `Deleting` | Offering, Subscription | Present once the object has a deletion timestamp. `True` means cleanup may proceed, `False` means something is holding it. |
| `PricingResolved` | Offering | Whether `status.resolvedPricing` was produced from the spec and the active PriceBook. |
| `CostsResolved` | Subscription | Written by the charge collection job when it refreshes `status.costs`, recording where the figures came from. |

On a Subscription, read `Active` rather than `Ready` when you want to know why something ended. Deactivation writes `Ready=False` with reason `ValidationSucceeded`, which describes nothing, and puts the real cause on `Active`.

## FinOpsProvider

A FinOpsProvider carries no conditions, and its reconciler writes no status at all. The reconciler reads the provider option you set, patches the OpenCost configuration to match, and returns; a provider with no valid option configured is logged and skipped without any status write.

So there is nothing to read back on the object itself. To confirm a FinOpsProvider took effect, check the OpenCost side: the pricing ConfigMap in the operator's namespace, or the OpenCost custom resource when the Multi Tenant Operator path is enabled. [How the active PriceBook reaches OpenCost](../concepts/architecture.md#how-the-active-pricebook-reaches-opencost) describes both paths.

## PriceBook

Readiness is per-object and independent of selection. Each reconcile parses that one book's rates; selection then picks a winner across the whole cluster without consulting readiness.

| Type | Status | Reason | Meaning | What to do |
| --- | --- | --- | --- | --- |
| `Ready` | `True` | `ValidationSucceeded` | Every rate on the book parsed as a currency value. A book whose `valuationMode` is not `currency` is ready trivially, having no rates to parse. | Nothing. |
| `Ready` | `False` | `PricebookParseFailed` | A rate could not be parsed. The message names the first field that failed and the value it held. | Fix that field. Malformed shapes are refused at admission, so what reaches this check is usually a value too large to express in micro-units. |
| `Active` | `True` | `Activated` | This book holds the active slot and its rates were rendered into OpenCost's pricing document. | Nothing. |
| `Active` | `False` | `Demoted` | Another book holds the slot. The operator also clears this book's `status.activePricing`, because it no longer describes what OpenCost is using. | Nothing, unless you expected this book to win. [Choosing the active PriceBook](../concepts/pricebook.md#choosing-the-active-pricebook) covers the three selection tiers. |

The `Active` condition is written only when the flag changes, so it appears on the transition rather than on every reconcile. A book can hold `Active=True` and `Ready=False` at the same time: selection ignores readiness on purpose, so a typo produces a visible failure instead of a silent switch to different prices.

## CostJob

A CostJob carries no conditions either. A `ResourceCostCollection` run reports itself through `status.executionHistory`, `status.lastExecutionTime`, `status.lastExecutionStatus`, and `status.lastSuccessfulExecutionTime` instead.

Only two status values are ever written, `Success` and `Failed`. The schema also permits `Error` on an execution record and `Pending` on `status.lastExecutionStatus`, and nothing writes either, so treat `Failed` as the only failure value you will see. A `SubscriptionChargeCollection` CostJob writes none of this and its status stays empty; watch its Jobs and pod logs, and the `CostsResolved` condition on the Subscriptions it prices. [Reading a run's outcome](../concepts/costjob.md#reading-a-runs-outcome) covers the fields.

## Offering

`Ready` and `PricingResolved` are always written together and always agree, because the reconciler validates the requirement list and resolves pricing in one pass. A reason on one is the same reason on the other.

| Type | Status | Reason | Meaning | What to do |
| --- | --- | --- | --- | --- |
| `Ready` / `PricingResolved` | `True` | `ValidationSucceeded` / `PricingResolved` | Requirements resolved and `status.resolvedPricing` was published. The `Ready` condition carries `ValidationSucceeded`; the `PricingResolved` condition carries `PricingResolved`. | Nothing. The Offering can be subscribed to. |
| `Ready` / `PricingResolved` | `False` | `RequiredOfferingNotFound` | A `compatibility.requiredOfferings` entry does not resolve. The message names it. | Create the missing Offering, or correct the entry. Remember `namespace` is required on every reference and is never defaulted. |
| `Ready` / `PricingResolved` | `False` | `RequiredOfferingNotReady` | A required Offering exists but is not itself ready. | Fix that Offering's own conditions. This one recovers on its own afterwards. |
| `Ready` / `PricingResolved` | `False` | `CircularDependencyDetected` | The requirement graph contains a loop, or the Offering requires itself. The message gives the path. | Break the loop. Because an Offering's spec is immutable, that means replacing one of the Offerings in the cycle. |
| `Ready` / `PricingResolved` | `False` | `NoActivePricebook` | The Offering declares `resourcePricing` but no active PriceBook with `valuationMode: currency` exists to resolve the rates. | Create or annotate a currency PriceBook. The operator refuses to publish margins applied to a missing rate, which would expose the margin as the price. |
| `Ready` / `PricingResolved` | `False` | `PricebookParseFailed` | The active PriceBook holds a rate the Offering's meters cannot resolve against. | Fix the rate on the PriceBook. Its own `Ready` condition names the field. |
| `Ready` / `PricingResolved` | `False` | `ValidationError` | A lookup failed for some other reason, typically an API error while reading a required Offering. | Read the message. This one is transient, and the reconcile is retried on a lengthening delay. |

None of these is terminal. Every one is re-evaluated on the next reconcile, and pricing resolves once the cause clears. Pricing is resolved once and then kept, so an Offering that has already published `status.resolvedPricing` does not re-resolve when the PriceBook changes.

| Type | Status | Reason | Meaning | What to do |
| --- | --- | --- | --- | --- |
| `Deleting` | `False` | `DependentSubscriptionsExist` | A Subscription still references this Offering through `offeringRef`. The finalizer stays on. | Delete or migrate those Subscriptions. |
| `Deleting` | `False` | `DependentOfferingsExist` | Another Offering still lists this one in `compatibility.requiredOfferings`. | Delete that Offering first, or replace it with one that does not require this. |
| `Deleting` | `False` | `ValidationError` | The dependency lookup itself failed. | Read the message and retry. |
| `Deleting` | `True` | `DeletionAllowed` | Nothing references the Offering. The reconciler drops the finalizer in the same pass, so the object usually disappears immediately. | Nothing. |

!!! warning
    Both dependency checks select on `status.ready` being `True`, which narrows them. A Subscription that is not ready, including one that has already deactivated or is winding down, does not block the delete, and deleting the Offering out from under it strands that Subscription's finalizer. [Uninstalling](../getting-started/uninstalling.md) gives a safe teardown order.

## Subscription

A Subscription carries the largest vocabulary, because four gates are re-checked on every reconcile and each names itself. The gates run in a fixed order and the first failure wins, so only one reason is on the condition at a time. [The four activation gates](../concepts/subscription.md#the-four-activation-gates) sets out what each one tests.

### Ready

These are the holding states. `Ready=False` with one of these reasons means the Subscription has not activated, or is active and billing while a gate fails transiently. It does not mean the Subscription ended.

| Type | Status | Reason | Gate | Meaning and what to do |
| --- | --- | --- | --- | --- |
| `Ready` | `False` | `OfferingNotFound` | Offering | `offeringRef` does not resolve. Create the Offering, or correct the reference including its `namespace`. |
| `Ready` | `False` | `OfferingNotReady` | Offering | The Offering exists but is not ready. Fix its conditions; this Subscription activates on its own afterwards. |
| `Ready` | `False` | `ParentSubscriptionNotFound` | Parent | `spec.parent.subscriptionRef` does not resolve. Create the parent. `spec.parent` is immutable including its presence, so the reference cannot be corrected on an existing object. |
| `Ready` | `False` | `ParentSubscriptionNotReady` | Parent | The parent exists but has not activated. Transient; it clears when the parent activates. |
| `Ready` | `False` | `ParentSubscriptionDeactivated` | Parent | The parent has ended. On a Subscription that never activated this never clears, because deactivation is one-way. Replace the family rather than waiting. |
| `Ready` | `False` | `CircularDependencyDetected` | Offering | `spec.parent.subscriptionRef` names this Subscription. Rejected at admission on create, and reported here if it arrives another way. |
| `Ready` | `False` | `CompatibilityRequirementNotMet` | Compatibility | A `requiredOfferings` entry of the bound Offering is not covered by an active Subscription elsewhere in the family, excluding this Subscription and its own descendants. Subscribe a relative to the missing Offering. |
| `Ready` | `False` | `TargetNotFound` | Target | The object named by `lifecycle.targetRef` does not exist. Create it, or drop the `targetRef`. |
| `Ready` | `False` | `TargetIsSelfReference` | Offering or Target | `lifecycle.targetRef` names this Subscription, matching on name, namespace, kind, and API version. Rejected at admission on create; reported here when a later edit introduces it. |
| `Ready` | `False` | `ValidationError` | Any | A read failed for some other reason. Transient, and the reconcile is retried on a lengthening delay. Read the message for the gate it hit. |
| `Ready` | `True` | `ActivationSucceeded` | — | All four gates passed. `Active=True` carries the same reason and `status.activatedAt` is written once. |
| `Ready` | `True` | `Orphaned` | — | All four gates passed, and this Subscription stayed active through the loss of its parent under an `Orphan` policy. `Active=True` carries the same reason. |
| `Ready` | `False` | `ValidationSucceeded` | — | Not a validation result. This is what every deactivation writes. Read the `Active` condition for the cause. |

A gate failure does not stop the billing. `status.activatedAt` stands, and the charge collection job selects Subscriptions on that timestamp rather than on readiness, so a Subscription whose Offering has gone not ready keeps accruing charges while it reports `Ready=False`.

### Active

`Active=False` is terminal in every case. A deactivated Subscription is never re-validated and never reactivates, so resuming billing for the same subscriber means a new Subscription with a new `activatedAt`.

| Type | Status | Reason | Terminal | Meaning and what to do |
| --- | --- | --- | --- | --- |
| `Active` | `True` | `ActivationSucceeded` | No | Billing is open. |
| `Active` | `True` | `Orphaned` | No | Billing is open, and the parent is gone. The Subscription's own requirements still have to be covered by a relative that is active. |
| `Active` | `False` | `ParentDeactivated` | Yes | The parent ended or disappeared while the effective policy was `Deactivate`. Nothing to do; the cascade is intended. |
| `Active` | `False` | `CompatibilityRequirementNotMet` | Yes | Coverage the Subscription depended on went away, usually because a sibling was deleted. Restoring the sibling does not revive this Subscription. |
| `Active` | `False` | `TargetNotFound` | Yes | The object named by `lifecycle.targetRef` was deleted. Only a genuinely missing target ends a Subscription; a read that fails any other way is retried. |
| `Active` | `False` | `MarkedForDeletion` | Yes | A `kubectl delete` started the wind-down. Expected. [Deactivate a subscription](../guides/deactivate-a-subscription.md) walks through the stages. |

Every one of these `Active=False` writes is paired with `Ready=False` and reason `ValidationSucceeded` on the `Ready` condition, which is why `Ready` alone cannot tell you what happened.

### Deleting

| Type | Status | Reason | Meaning | What to do |
| --- | --- | --- | --- | --- |
| `Deleting` | `False` | `WaitingForCollectionJob` | The finalizer is still on and a `SubscriptionChargeCollection` run has not yet agreed to release it. This is the only reason the condition ever carries, and the condition is never written `True`. | Expected while the wind-down runs. If it persists, check that a `SubscriptionChargeCollection` CostJob exists and is succeeding. [When the finalizer will not release](../guides/deactivate-a-subscription.md#when-the-finalizer-will-not-release) lists the causes. |

`Deleting=False` is the blocked signal in itself; the reason names what is holding it. Unlike an Offering, a Subscription never gets a `Deleting=True` condition, because the collection job removes the finalizer directly and the object is gone before anything could be written to it.

### CostsResolved

The charge collection job writes this each time it refreshes `status.costs`, and only when the run produced at least one bucket for that Subscription. It is never written `False`.

| Type | Status | Reason | Meaning | What to do |
| --- | --- | --- | --- | --- |
| `CostsResolved` | `True` | `FromDB` | The buckets were aggregated from the charge rows in PostgreSQL. This is the normal case. | Nothing. |
| `CostsResolved` | `True` | `FromCalculator` | The database query failed and the run fell back to an in-memory calculation for this tick. The figures are the projection rather than the recorded charges. | Check the collection job's pod log and the database connection. Repeated `FromCalculator` means the charge rows are not being read. |

A Subscription with no `CostsResolved` condition has not been priced yet: either no `SubscriptionChargeCollection` CostJob is running, or the Subscription never activated, or the run produced no buckets for it. [Read subscription costs](../guides/read-subscription-costs.md) covers what the buckets mean and the case where a usage-only Offering produces none.

## Related

- [Troubleshooting](../troubleshooting.md) for the remediation workflows these reasons point at.
- [Subscription](../concepts/subscription.md) and [Offering](../concepts/offering.md) for the mechanisms behind each gate.
- [Configuration reference](configuration.md) for the settings that decide which of these conditions can be written at all.
