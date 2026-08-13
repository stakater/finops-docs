# Subscribe to an offering

A `Subscription` binds a subscriber to an [Offering](define-offering.md) and starts the billing clock. This guide creates the simplest useful one, a Subscription with nothing but an `offeringRef`, then confirms it activated and reads the state it left behind. It is for a platform engineer, or the automation that provisions a tenant, with edit rights in the namespace the Subscription will live in.

## Prerequisites

- The FinOps Operator is [installed](../getting-started/installation/kubernetes.md) and its controller pod is running.
- An `Offering` whose `READY` column reads `True`. [Define an offering](define-offering.md) authors one.
- A [`SubscriptionChargeCollection` CostJob](collect-cost-data.md) scheduled, if the fee is to accrue into charge rows rather than only be declared. A cluster without one also never finishes deleting a Subscription.
- `kubectl` edit permission in the namespace you are creating the Subscription in, which is `finops-operator-system` throughout this guide.

For a Subscription that hangs off another one, or whose activation depends on a sibling or a workload, read [compose subscriptions](compose-subscriptions.md) after this page.

## Step 1: Reference the Offering

`spec.offeringRef` is the only required field on the spec, and it takes two values, both required:

```yaml
spec:
  offeringRef:
    name: platform-base
    namespace: finops-operator-system
```

`namespace` carries `+required` and a minimum length of one character, and it is never filled in from the Subscription's own namespace. Omitting it is rejected by the API server, not defaulted, even when the Offering sits in the same namespace as the Subscription. That is deliberate: a reference means the same object wherever the manifest is applied, so the same file cannot silently bind to a different Offering in a different namespace.

The whole reference is immutable, held by a CEL rule on `spec` that rejects any change with `offeringRef is immutable; create a new Subscription instead`. Check the manifest against the API server before you commit to it:

```sh
kubectl apply -f subscription.yaml --dry-run=server
```

Moving a subscriber onto different terms later means creating a second Subscription against a second Offering, which is the sequence in [replacing an Offering](../concepts/offering.md#replacing-an-offering).

## Step 2: Know what has to be true before it activates

Activation is not one condition but four, checked in a fixed order on every reconcile: the Offering, then the parent, then compatibility coverage, then the target. All four must pass. They are continuous checks rather than admission checks, so a Subscription that fails one is still admitted, held at `Ready=False`, and activates on its own once the condition clears. [The four activation gates](../concepts/subscription.md#the-four-activation-gates) sets out what each one tests and which of them can also end an already-active Subscription.

What a guide needs from that is the reason vocabulary, because the failing gate names itself on the `Ready` condition. The Offering gate reports `OfferingNotFound` or `OfferingNotReady`. Where a `spec.parent` is set, the parent gate reports `ParentSubscriptionNotFound`, `ParentSubscriptionDeactivated`, or `ParentSubscriptionNotReady`. Where the bound Offering declares `requiredOfferings`, the compatibility gate reports `CompatibilityRequirementNotMet`. Where a `lifecycle.targetRef` is set, the target gate reports `TargetNotFound`, or `TargetIsSelfReference` if the Subscription named itself. A read that fails for some other reason surfaces as `ValidationError` at whichever gate hit it.

The Subscription in step 3 sets neither a `parent` nor a `targetRef` and binds an Offering that requires nothing, so gates two to four pass trivially and only the first two reasons are reachable. Opting into any of the other three makes it a live dependency for the rest of the Subscription's life, which is what [compose subscriptions](compose-subscriptions.md) covers, one procedure per gate.

## Step 3: Apply the Subscription

```yaml
# subscription-acme-platform-base.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-platform-base
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-base
    namespace: finops-operator-system
```

```sh
kubectl apply -f subscription-acme-platform-base.yaml
```

To bill measured consumption as well as the fee, add `usageSources` here; [price resource usage](price-resource-usage.md) covers pairing them with the Offering's `resourcePricing`. Unlike `offeringRef`, `usageSources` stays editable afterwards.

## Step 4: Verify activation

```sh
kubectl get subscriptions -n finops-operator-system
```

```text
NAME                 READY
acme-platform-base   True
```

`READY` is the `status.ready` print column. `True` means every gate passed and the billing epoch has opened. The two status fields worth reading next are the timestamp the epoch opened at and the conditions that recorded it:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{.status.activatedAt}{"\n"}'
```

```sh
kubectl describe subscription acme-platform-base -n finops-operator-system
```

On a Subscription that just activated, `describe` shows a `Ready` condition and an `Active` condition, both `True` and both carrying reason `ActivationSucceeded`. `status.activatedAt` is written once and never moved, and everything downstream keys off it: charges are computed from it, `minPeriods` is counted from it, and a Subscription that never activated is skipped outright by the collection job.

If `READY` reads `False`, `describe` names the gate that is holding it, using the reason vocabulary in step 2. [Status conditions](../reference/status-conditions.md) lists the full set.

## Step 5: Tell a waiting Subscription from a finished one

`READY False` is not one state. It covers a Subscription that has not activated yet, one that has ended for good, and one that is active and billing while a gate is transiently failing. The `Ready` condition alone does not separate them, because deactivation writes `Ready=False` with reason `ValidationSucceeded`, which describes nothing about the cause. Read the `Active` condition and `status.deactivatedAt` instead:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{.status.ready}{"  "}{.status.deactivatedAt}{"\n"}{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

| What you see | What it means |
| --- | --- |
| `READY True` | Active. `Active=True` with reason `ActivationSucceeded`, or `Orphaned` if it outlived its parent. |
| `READY False` and no `Active` condition at all | It has never activated. The `Ready` condition's reason names the failing gate. |
| `READY False` with `Active=True` | It is still active and still accruing charges; a gate is failing without ending it, such as an Offering that has gone not ready. `status.deactivatedAt` is absent. |
| `READY False` with `Active=False` | It has ended, and terminally. The `Active` condition's reason carries the real cause: `ParentDeactivated`, `CompatibilityRequirementNotMet`, `TargetNotFound`, or `MarkedForDeletion`. `status.deactivatedAt` is set. |

The absent-`Active`-condition row is the reliable discriminator for a Subscription that never got going, because the not-ready path writes only the `Ready` condition and never touches `Active`. `status.deactivatedAt` is the reliable one for a Subscription that ended: it is written once, never cleared, and a Subscription carrying it is not re-validated on any later reconcile, so it will not come back if the Offering recovers. [What status tells you](../concepts/subscription.md#what-status-tells-you) sets out the rest of the fields.

## Step 6: Confirm charges are accruing

`status.costs` is written by the `SubscriptionChargeCollection` CostJob on its own schedule, not by the reconciler, so it appears on the first run after activation rather than at activation:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{.status.costs[*].granularity}{"\n"}'
```

```text
hour day month
```

Three rolling buckets, in micro-currency, where 1,000,000 micros is 1.00 of the active PriceBook's currency. An empty result after a collection run has fired means the Subscription had not activated when the run started, or that no `SubscriptionChargeCollection` CostJob is scheduled at all. [Read subscription costs](read-subscription-costs.md) interprets the values and the per-meter breakdown.

## Related guides

- [Compose subscriptions](compose-subscriptions.md) for parents, required Offerings, orphaning, and target references.
- [Define an offering](define-offering.md) for the terms this Subscription accrues against.
- [Deactivate a subscription](deactivate-a-subscription.md) for ending one and what holds its finalizer.
- [Subscription](../concepts/subscription.md) for the gates, the status fields, and why deactivation is terminal.
