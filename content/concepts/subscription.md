# Subscription

A `Subscription` binds a subscriber to an [Offering](offering.md) and starts the clock. From the moment it activates it accrues charges on that Offering's terms, and it goes on accruing them until it deactivates, which happens exactly once. Platform engineers or the automation that provisions a tenant create one per billing relationship, in whichever namespace makes sense for the thing being billed.

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-platform-base
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-base
    namespace: finops-operator-system
  parent:
    subscriptionRef:
      name: acme-platform-core
      namespace: finops-operator-system
  usageSources:
    - resourceType: Deployment
      name: acme-api
      namespace: acme-prod
  lifecycle:
    onParentDeactivate: Orphan
    targetRef:
      apiVersion: apps/v1
      kind: Deployment
      name: acme-api
      namespace: acme-prod
```

Only `offeringRef` is required. A Subscription that carries nothing else is complete and valid:

```yaml
spec:
  offeringRef:
    name: platform-base
    namespace: finops-operator-system
```

## What it points at, and why that is fixed

`offeringRef.namespace` is required and has a minimum length of one character. It is never filled in from the Subscription's own namespace, so a reference reads the same wherever it was authored and the same manifest cannot silently mean a different Offering in a different namespace. The same applies to `parent.subscriptionRef` and to every entry in an Offering's `requiredOfferings`.

Both references are immutable, enforced by two CEL rules on `spec`:

| Rule | Message on rejection |
| --- | --- |
| `self.offeringRef == oldSelf.offeringRef` | `offeringRef is immutable; create a new Subscription instead` |
| `has(self.parent) == has(oldSelf.parent) && (!has(self.parent) \|\| self.parent == oldSelf.parent)` | `parent is immutable; create a new Subscription instead` |

The second rule covers presence as well as value, so a `parent` block can neither be added to a Subscription that started without one nor removed from one that has it. Both rules live on the CRD and are checked by the API server on every update; the Subscription's validating webhook is registered for `CREATE` only and does one thing, refusing a Subscription that names itself as its own `parent` or as its own `lifecycle.targetRef`.

What is fixed is the billing identity. `offeringRef` decides what the Subscription is charged for and `parent` decides which family provides its compatibility coverage, and activation is a billing epoch that cannot be re-pointed halfway through. Changing either means a new Subscription; `usageSources` and `lifecycle` remain editable.

## The four activation gates

Every reconcile runs the same gates in order, and all four must pass before the Subscription activates. They are continuous checks, not admission checks: a Subscription that fails one is admitted, held at `Ready=False` with the failing reason, and activates on its own once the condition clears.

| Gate | Passes when | Reason when it does not |
| --- | --- | --- |
| Offering | `offeringRef` resolves and that Offering reports `status.ready: "True"` | `OfferingNotFound`, `OfferingNotReady` |
| Parent | `spec.parent` is unset, or the parent exists, is not deactivated, and is ready | `ParentSubscriptionNotFound`, `ParentSubscriptionNotReady`, `ParentSubscriptionDeactivated` |
| Compatibility | The Offering declares no `requiredOfferings`, or every one of them is covered by an active Subscription elsewhere in the family, not counting this Subscription and its own descendants | `CompatibilityRequirementNotMet` |
| Target | `lifecycle.targetRef` is unset, or the object it names exists | `TargetNotFound`, `TargetIsSelfReference` |

With neither `parent` nor `targetRef` set and an Offering that requires nothing, gates two to four pass trivially and activation follows from the Offering being ready. Between the parent gate and the compatibility gate the reconciler stamps `status.compatibilityRoot` once, which is why coverage can only be evaluated after the ancestor chain has been resolved. The coverage rule itself, and the worked tree that shows which relatives can provide coverage and which cannot, are in [compatibility and hierarchy](compatibility-and-hierarchy.md).

Activation writes `status.activatedAt`, sets `Ready=True`, and adds an `Active=True` condition with reason `ActivationSucceeded`. Everything downstream keys off that timestamp: charges are computed from it, and a Subscription that never activated is skipped outright by the collection job.

The gates keep applying afterwards, and three of them can end an already-active Subscription rather than merely holding it: a parent that deactivates or disappears, coverage that goes away, and a target that is deleted. A gate that fails transiently, such as a parent that is briefly not ready, does not.

A failure that does not deactivate does not stop the billing either. It sets `status.ready` false and leaves `status.activatedAt` standing, and the collection job selects Subscriptions on `activatedAt` rather than on readiness, so a Subscription whose Offering has gone not ready keeps accruing charges while it reports `Ready=False`.

## Declaring usage sources

`usageSources` is what makes a Subscription bill for measured consumption. Each entry selects allocation rows, and a Subscription with no entries is charged its Offering's subscription fee and nothing else, however much `resourcePricing` that Offering declares.

| Field | Values |
| --- | --- |
| `resourceType` | `Deployment`, `StatefulSet`, `Pod`, `DaemonSet`, `Job`, `CronJob`, `ReplicaSet` |
| `name` | The name of the controller, or of the pod when `resourceType` is `Pod` |
| `namespace` | The namespace the workload runs in |

All three are optional individually, and a CEL rule on each entry requires at least one of them: an empty entry is rejected with `at least one of resourceType, name, or namespace must be set`. The rule exists because an entry with no fields would match every allocation row in the cluster.

Within one entry the fields are combined, so `resourceType: Deployment` with `name: acme-api` and `namespace: acme-prod` matches that one workload. Across entries the matches add together, so several entries widen the selection. A `namespace` on its own is the broad form, matching everything measured in that namespace. `Pod` is the one `resourceType` that behaves differently: it switches `name` to match a pod name instead of a controller name, and contributes no filter of its own, so `resourceType: Pod` with only a `namespace` selects everything in that namespace rather than only its pods.

Usage is charged only where both sides agree: the Subscription declares sources and the Offering declares `resourcePricing`. [Price resource usage](../guides/price-resource-usage.md) covers the pairing, and [how charges reach `Subscription.status.costs`](architecture.md#how-charges-reach-subscriptionstatuscosts) covers what a collection run does with the rows.

## Tying a Subscription to a target

`lifecycle.targetRef` couples the Subscription to some other Kubernetes object by `apiVersion`, `kind`, `name`, and `namespace`. It is how a Subscription stops being a standalone accounting record and starts tracking a real workload: while the target is absent the Subscription is held not ready, and when the target is deleted the Subscription deactivates.

!!! warning
    The gate is existence, not readiness. The field's own description says the Subscription waits for the target's status to be `Ready`, but the check performed is a plain fetch of the object, and no condition on the target is read. A target that exists and is failing satisfies the gate.

`lifecycle.onParentDeactivate` overrides the Offering's own value for this one Subscription: `Deactivate` ends it with the parent, `Orphan` keeps it active while retaining the parent reference. `Orphan` detaches only the lifecycle link — it does not exempt the Subscription from compatibility, so an orphan whose required Offering was covered only by the parent that just went away is still deactivated for the coverage gap.

!!! note
    Presence of the block is what decides which value applies. As soon as `spec.lifecycle` exists, its `onParentDeactivate` is used, and the field defaults to `Deactivate`, so a Subscription that sets only `targetRef` reverts an Offering's `Orphan` policy to `Deactivate` without saying so. Set `onParentDeactivate` explicitly whenever you set `targetRef`.

## Deactivation is terminal

`status.deactivatedAt` is written once and never cleared, and a Subscription that carries it is not re-validated on any later reconcile. It does not reactivate if the parent comes back, if coverage is restored, or if the target is recreated. The end of a billing relationship is a fact about the past, and reopening it would make the charge history for the same object describe two different lives.

Deactivation happens on deletion, on a parent that deactivated or vanished under a `Deactivate` policy, on lost compatibility coverage, and on a deleted target. Whatever the cause, the effect on billing is the same: the fee stops accruing at the snapped tick boundary described in the [billing model](billing-model.md), and no further usage is charged.

## What status tells you

| Field | What it holds |
| --- | --- |
| `status.ready` | `True` once every gate passes, `False` at any other time, including after deactivation. The `Ready` column of `kubectl get subscriptions`. |
| `status.activatedAt` | When every gate first passed. Absent on a Subscription that has never activated. |
| `status.deactivatedAt` | When it ended. Absent while it is running. |
| `status.compatibilityRoot` | The `metadata.uid` of the root ancestor, stamped once. A Subscription with no parent carries its own UID here. |
| `status.costs` | Three rolling buckets, `hour`, `day`, and `month`, each with an accumulated `current`, a `projected` total, and a per-meter `breakdown`, all in micro-currency. Written by the collection job, not the reconciler. |
| `status.conditions` | `Ready` and `Active` from the reconciler, `Deleting` while cleanup is pending, and `CostsResolved` from the collection job. |

Read the `Active` condition rather than the `Ready` one when you want to know why a Subscription ended. On deactivation `Ready` is set false with the reason `ValidationSucceeded`, which says nothing useful, while `Active=False` carries the real cause: `ParentDeactivated`, `CompatibilityRequirementNotMet`, `TargetNotFound`, or `MarkedForDeletion`. One `Active=True` reason is worth recognising too: `Orphaned` marks a Subscription that stayed active through the loss of its parent. [Read subscription costs](../guides/read-subscription-costs.md) interprets the cost buckets.

## Deletion and the finalizer

The reconciler adds `subscriptions.finops.stakater.com/finalizer` the first time it sees a Subscription, so `kubectl delete` starts a wind-down rather than removing the object. The delete path deactivates the Subscription immediately and records `Deleting=False` with reason `WaitingForCollectionJob`; children are not touched directly, because deactivating this Subscription is itself a coverage change that re-enqueues each of them to resolve its own policy.

Only the `SubscriptionChargeCollection` [CostJob](costjob.md) removes the finalizer, and only when three things hold: the Subscription is deactivated, at least `minPeriods` ticks have elapsed since `activatedAt` where the Offering sets one, and charges are finalized through its last billable hour. Any error recorded against the Subscription during a run also holds the finalizer, so nothing is torn down while its final hours are unaccounted for. A cluster with no such CostJob never completes a Subscription deletion at all. [Deactivate a subscription](../guides/deactivate-a-subscription.md) walks through the sequence.

## Related

- [Subscribe to an offering](../guides/subscribe-to-offering.md) to create one, and [compose subscriptions](../guides/compose-subscriptions.md) for parents and families.
- [Compatibility and hierarchy](compatibility-and-hierarchy.md) for the coverage model behind the third gate.
- [`SubscriptionSpec`](../reference/api.md#subscriptionspec), [`UsageSource`](../reference/api.md#usagesource), [`SubscriptionLifecycle`](../reference/api.md#subscriptionlifecycle), and [`SubscriptionStatus`](../reference/api.md#subscriptionstatus) for the field-level reference.
