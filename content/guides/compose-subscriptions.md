# Compose subscriptions

A Subscription does not have to stand alone. It can hang off another one as an add-on, refuse to start unless a companion Offering is already bound somewhere in the same family, survive the loss of its parent, or track a real workload and end when that workload is deleted. This guide walks the four procedures, each with the manifests and the command that confirms the operator did what you asked. It is for a platform engineer, or the provisioning automation, that already creates single Subscriptions and now needs them to relate to one another.

The model behind all four, the family tree and the coverage rule it is searched with, is on [compatibility and hierarchy](../concepts/compatibility-and-hierarchy.md). This page is the procedure.

## Prerequisites

- The FinOps Operator is [installed](../getting-started/installation/kubernetes.md) and its controller pod is running.
- You can create a plain Subscription and read its status. [Subscribe to an offering](subscribe-to-offering.md) covers that, and its step 5 is the status-reading habit every verification here relies on.
- `kubectl` edit permission on the Offerings and Subscriptions involved. Everything below lives in `finops-operator-system`.
- Every reference sets `namespace` explicitly. `offeringRef`, `parent.subscriptionRef`, and each `requiredOfferings` entry all require it, and none of them is ever defaulted from the object that carries it.

!!! warning
    `spec.parent` is immutable including its presence, so a Subscription cannot grow a parent later and cannot have one removed. Decide before the first apply whether a Subscription belongs under another one. `spec.lifecycle` is the one composition field that stays editable.

## Attach an add-on to a base Subscription

`spec.parent.subscriptionRef` names the Subscription this one hangs off. A disk that belongs to a VM, a backup plan that belongs to a database, an add-on tier that belongs to a platform bundle: the reference is what lets a bill be read as a structure rather than a flat list, and it is also a gate, because the parent must exist, must not be deactivated, and must be ready before the child activates.

Two Offerings first, since a Subscription cannot pass its first gate without a ready Offering to bind to. Neither declares `resourcePricing`, so neither needs a PriceBook to resolve, and both become ready on their first reconcile:

```yaml
# offerings-vm.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: vm-standard
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 30000000
---
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: vm-disk
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 2000000
```

```yaml
# family-vm.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-vm
  namespace: finops-operator-system
spec:
  offeringRef:
    name: vm-standard
    namespace: finops-operator-system
---
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-vm-disk
  namespace: finops-operator-system
spec:
  offeringRef:
    name: vm-disk
    namespace: finops-operator-system
  parent:
    subscriptionRef:
      name: acme-vm
      namespace: finops-operator-system
```

```sh
kubectl apply -f offerings-vm.yaml
kubectl get offerings vm-standard vm-disk -n finops-operator-system
```

```text
NAME          READY
vm-disk       True
vm-standard   True
```

```sh
kubectl apply -f family-vm.yaml
```

Wait for both Offerings to read `READY True` before applying the Subscriptions. Nothing breaks if you do not: a Subscription whose Offering is missing or not ready is admitted and held at `Ready=False` with `OfferingNotFound` or `OfferingNotReady`, and it activates on its own once the Offering resolves.

The same is true of the parent reference, so the order of the two Subscriptions does not matter either. A child applied before its parent exists is held under `ParentSubscriptionNotFound`, and under `ParentSubscriptionNotReady` while the parent exists but has not activated yet.

```sh
kubectl get subscriptions acme-vm acme-vm-disk -n finops-operator-system
```

```text
NAME           READY
acme-vm        True
acme-vm-disk   True
```

To see which gate a child is waiting on, and to confirm the two ended up in one family, read the conditions and the stamped root:

```sh
kubectl get subscription acme-vm-disk -n finops-operator-system \
  -o jsonpath='{.status.compatibilityRoot}{"\n"}{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

`status.compatibilityRoot` holds the `metadata.uid` of the root ancestor, and every member of a family carries the same value. On `acme-vm-disk` it should match `acme-vm`'s own UID, since a Subscription with no parent is its own root. The reconciler stamps it once, after the parent gate and before the coverage check, so an unstamped child is a child whose ancestor chain is not fully present yet.

Neither Subscription here says anything about what the child should do if `acme-vm` goes away, so it takes the default and deactivates with it. Choosing otherwise is the third procedure below.

## Require a companion Offering

`compatibility.requiredOfferings` on an Offering states that it may only be sold alongside others. The operator turns that into a gate on every Subscription bound to the Offering: each requirement must be covered by an active Subscription somewhere in the same family, excluding the Subscription itself and everything beneath it.

Here monitoring is only sold on top of a VM. The requirement goes on the `monitoring` Offering, and what satisfies it is a sibling Subscription that binds `vm-standard`. Because coverage is searched across the family excluding the requiring Subscription and its own descendants, a Subscription with no parent has no candidates at all, so this needs a bundle at the top with both the VM and the monitoring Subscription hanging off it.

Three Offerings. `platform-core` prices the bundle at the root, `vm-standard` is carried over from the first procedure, and `monitoring` is the one that declares the requirement:

```yaml
# offerings-bundle.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: platform-core
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 10000000
---
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: monitoring
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 5000000
  compatibility:
    requiredOfferings:
      - name: vm-standard
        namespace: finops-operator-system
```

The requiring Offering has its own, separate check to pass first. `monitoring` stays `READY False` while `vm-standard` is absent or not ready, reporting `RequiredOfferingNotFound` or `RequiredOfferingNotReady` on its own conditions, and a Subscription bound to a not-ready Offering never gets past its first gate. So apply `vm-standard` from the first procedure before this file, and confirm all three Offerings are ready before going on:

```sh
kubectl apply -f offerings-vm.yaml
kubectl apply -f offerings-bundle.yaml
kubectl get offerings vm-standard platform-core monitoring -n finops-operator-system
```

```text
NAME            READY
monitoring      True
platform-core   True
vm-standard     True
```

Order matters more here than it did with the Subscriptions. The Offering reconciler has no watch on other Offerings, so a `monitoring` applied before `vm-standard` is ready recovers only on its own retry, and those retries space out as they fail. If it is still `READY False`, check that `vm-standard` reads `True` first, then wait.

### Start with the requirement unmet

Apply the root and the requiring Subscription, and deliberately leave the covering sibling out:

```yaml
# family-bundle.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-bundle
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-core
    namespace: finops-operator-system
---
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-monitor
  namespace: finops-operator-system
spec:
  offeringRef:
    name: monitoring
    namespace: finops-operator-system
  parent:
    subscriptionRef:
      name: acme-bundle
      namespace: finops-operator-system
```

```sh
kubectl apply -f family-bundle.yaml

kubectl get subscription acme-monitor -n finops-operator-system \
  -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

```text
Ready    False   CompatibilityRequirementNotMet
```

That is the coverage gap and nothing else, which is why the Offerings had to be ready first: had `monitoring` still been `READY False`, `acme-monitor` would have failed the earlier Offering gate and reported `OfferingNotReady` instead, never reaching the coverage check at all. The family here is `acme-bundle` and `acme-monitor`; the search drops `acme-monitor` and its descendants, leaving only `acme-bundle`, which is active but binds `platform-core` rather than the required `vm-standard`.

It waits rather than failing outright, and activates by itself once a provider appears.

### Add the covering sibling

```yaml
# subscription-acme-bundle-vm.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-bundle-vm
  namespace: finops-operator-system
spec:
  offeringRef:
    name: vm-standard
    namespace: finops-operator-system
  parent:
    subscriptionRef:
      name: acme-bundle
      namespace: finops-operator-system
```

```sh
kubectl apply -f subscription-acme-bundle-vm.yaml
kubectl get subscriptions acme-bundle acme-bundle-vm acme-monitor -n finops-operator-system
```

```text
NAME             READY
acme-bundle      True
acme-bundle-vm   True
acme-monitor     True
```

`acme-monitor` activates without being touched. A member starting or stopping being active re-enqueues every member of its family, so `acme-bundle-vm` activating is what triggers `acme-monitor` to re-evaluate its own coverage and find it satisfied. Note that `acme-bundle-vm` names its parent from the start, which is the only option: `parent` is immutable including its presence, so a family cannot gain a root or a member's parent after the fact.

Losing coverage later is not symmetrical with never having had it. Coverage is re-checked on every reconcile, and an active Subscription that loses it is deactivated, which is terminal: deleting `acme-bundle-vm` now would end `acme-monitor` for good, and re-creating the sibling would not bring it back. In that case the reason moves off the `Ready` condition, which is set `False` with the uninformative reason `ValidationSucceeded`, and onto `Active=False`, where `CompatibilityRequirementNotMet` names the cause. Always read `Active` when you want to know why a Subscription ended.

Coverage also spans further than the one hop this example uses. An ancestor, a sibling, an uncle, or a cousin can all provide it, however deep in the family they sit, but a Subscription's own children and their descendants never can. "Active" for a provider means it has an `activatedAt` and no `deactivatedAt`; its own readiness is not consulted, so a provider whose Offering has gone not ready still covers what it covers. [Who can cover a requirement](../concepts/compatibility-and-hierarchy.md#who-can-cover-a-requirement) works through a tree that shows both the relatives that count and the one that does not.

## Keep a child alive when its parent ends

`lifecycle.onParentDeactivate` decides what an already-active child does when its parent deactivates or disappears. `Deactivate`, the default, ends the child too. `Orphan` keeps it active and keeps the `parent` reference for traceability, which is what you want for an add-on that has become a standalone service in its own right.

The value is taken from the Subscription's own `spec.lifecycle` when that block is present, otherwise from the bound Offering's `lifecycle.onParentDeactivate`, otherwise `Deactivate`. Set it on the Offering to make it the policy for everything bound to that Offering.

This procedure uses its own database and backup pair rather than continuing the VM family above, because an Offering's spec is immutable and `vm-disk` was created without a `lifecycle` block, so it can never grow one:

```yaml
# offerings-db.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: db-standard
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 60000000
---
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: db-backup
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 4000000
  lifecycle:
    onParentDeactivate: Orphan
```

```yaml
# family-db.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-db
  namespace: finops-operator-system
spec:
  offeringRef:
    name: db-standard
    namespace: finops-operator-system
---
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-db-backup
  namespace: finops-operator-system
spec:
  offeringRef:
    name: db-backup
    namespace: finops-operator-system
  parent:
    subscriptionRef:
      name: acme-db
      namespace: finops-operator-system
  lifecycle:
    onParentDeactivate: Orphan
```

Both halves set the policy on purpose. The Offering's value is the default for everything bound to it, and the Subscription repeats it so the manifest says what it does without a reader having to fetch the Offering. Neither Offering declares `requiredOfferings`, which matters for the second warning below.

```sh
kubectl apply -f offerings-db.yaml
kubectl apply -f family-db.yaml
kubectl get subscriptions acme-db acme-db-backup -n finops-operator-system
```

```text
NAME             READY
acme-db          True
acme-db-backup   True
```

Both must read `True` before the next step. Orphaning only applies to a child that is already active: the policy is consulted on the branch the reconciler takes when an active Subscription's parent gate fails, so a child that never activated is simply held at `ParentSubscriptionNotFound` when its parent disappears, and there is nothing to orphan.

!!! warning
    An Offering cannot stop a Subscription from choosing its own policy. `lifecycle.allowOverride` exists on the Offering's API and nothing reads it, so setting `allowOverride: false` blocks nothing. Any Subscription carrying a `spec.lifecycle` block supplies its own `onParentDeactivate`, and because that field defaults to `Deactivate`, a Subscription that sets only `lifecycle.targetRef` silently reverts an Offering's `Orphan` policy to `Deactivate`. Whenever you set anything under `spec.lifecycle`, set `onParentDeactivate` explicitly too.

Delete the parent and watch the child stay up:

```sh
kubectl delete subscription acme-db -n finops-operator-system --wait=false

kubectl get subscription acme-db-backup -n finops-operator-system \
  -o jsonpath='{.status.ready}{"\n"}{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

```text
True
Ready    True    Orphaned
Active   True    Orphaned
```

`Orphaned` in place of `ActivationSucceeded` is the marker of a Subscription that outlived its parent. `--wait=false` matters because the parent keeps its finalizer until the collection job settles its charges, so `kubectl delete` would otherwise block; the child is re-evaluated as soon as the parent's deactivation is recorded, not when the object finally disappears.

!!! warning
    `Orphan` detaches the lifecycle link and nothing else. It is not an exemption from `compatibility.requiredOfferings`. That is why `db-backup` above declares none: had it required `db-standard`, the deleted parent would have been its only active provider, and the orphan would be deactivated on that same reconcile for the coverage gap, reporting `Active=False` with reason `CompatibilityRequirementNotMet` rather than staying up. To keep an orphan alive, its requirements have to be covered by a relative that is still active.

Under the default `Deactivate` policy the same command shows `False` with `Active=False` and reason `ParentDeactivated`, and `status.deactivatedAt` set. That cascade works at any depth, because deactivating one Subscription re-enqueues its whole family and each member then resolves its own policy.

## Tie a Subscription to a workload

`lifecycle.targetRef` couples a Subscription to some other Kubernetes object by `apiVersion`, `kind`, `name`, and `namespace`. It is how a Subscription stops being a standalone accounting record and starts tracking something real: it will not activate while the target is absent, and it deactivates when the target is deleted.

```yaml
# subscription-acme-api.yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-api
  namespace: finops-operator-system
spec:
  offeringRef:
    name: platform-base
    namespace: finops-operator-system
  lifecycle:
    onParentDeactivate: Deactivate
    targetRef:
      apiVersion: apps/v1
      kind: Deployment
      name: acme-api
      namespace: acme-prod
```

`platform-base` is the calendar-aligned Offering from [define an offering](define-offering.md); apply it first, or point `offeringRef` at any ready Offering you already have. The target may live in any namespace, and needs no relation to the Subscription's own; leave `namespace` out only for a cluster-scoped target. `onParentDeactivate` is spelled out for the reason in the warning above, even though this Subscription has no parent, so that the block cannot be misread as leaving the policy unset.

```sh
kubectl apply -f subscription-acme-api.yaml

kubectl get subscription acme-api -n finops-operator-system \
  -o jsonpath='{.status.ready}{"\n"}{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

With the Deployment present, `READY` is `True`. Without it, the Subscription is admitted and held:

```text
False
Ready    False   TargetNotFound
```

!!! warning
    The gate is existence, not readiness. The field's own description says the Subscription waits for the target's status to be `Ready`, but the check performed is a plain fetch of the named object and no condition on it is read. A Deployment that exists with zero available replicas satisfies the gate, so `READY True` on a target-bound Subscription means the target exists, not that it is healthy.

Delete the target and the coupling shows itself:

```sh
kubectl delete deployment acme-api -n acme-prod

kubectl get subscription acme-api -n finops-operator-system \
  -o jsonpath='{.status.deactivatedAt}{"\n"}{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

```text
2026-08-12T09:41:07Z
Ready    False   ValidationSucceeded
Active   False   TargetNotFound
```

`Active=False` with reason `TargetNotFound` is the real verdict; the `Ready` condition's `ValidationSucceeded` is what every deactivation writes and carries no information. Deactivation is terminal here as everywhere, so recreating the Deployment does not revive the Subscription. Only a target that is genuinely missing ends it: a read that fails for any other reason is retried and leaves the Subscription active.

One shape is refused outright. A Subscription whose `targetRef` names the Subscription itself, matching on name, namespace, `kind: Subscription`, and this API version, is rejected by the validating webhook on create with reason `TargetIsSelfReference`. Because `spec.lifecycle` stays editable and the webhook is registered for create only, the same shape introduced by a later edit is caught by the reconciler instead, which repeats the check on every pass and reports the same reason.

## Related guides

- [Subscribe to an offering](subscribe-to-offering.md) for the single Subscription these compose from, and for reading `READY False` correctly.
- [Define an offering](define-offering.md) for the Offerings referenced here, and [deactivate a subscription](deactivate-a-subscription.md) for taking a family apart.
- [Compatibility and hierarchy](../concepts/compatibility-and-hierarchy.md) for the family model, the coverage search, and cycles in both graphs.
- [`SubscriptionParent`](../reference/api.md#subscriptionparent), [`SubscriptionLifecycle`](../reference/api.md#subscriptionlifecycle), and [`Compatibility`](../reference/api.md#compatibility) for the field-level reference.
