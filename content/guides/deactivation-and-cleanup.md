# Deactivation and cleanup

This guide explains what happens when a Subscription is deactivated — whether by user action, by a parent Subscription deactivating, or by a target resource disappearing. It covers the deactivation sequence, the snap-forward mechanism, the `minPeriods` cleanup guard, and how children are handled.

**Prerequisites:**

- One or more active Subscriptions. See [Subscribe to an offering](./subscribe-to-offering.md).
- A `CostJob` of type `SubscriptionChargeCollection` running. See [Collect cost data](./collect-cost-data.md).
- Familiarity with [Parent-child subscriptions](./parent-child-subscriptions.md) if you have linked Subscriptions.

## What happens when you delete a Subscription

Deleting a Subscription does not immediately remove the Kubernetes object. The operator places a **finalizer** on every Subscription at creation time. A finalizer is a marker that prevents the Kubernetes API from deleting an object until the operator explicitly releases it. This gives the operator time to complete billing for any outstanding periods.

The sequence on user-initiated delete is:

1. **Deactivation**: the operator marks the Subscription deactivated and sets a `Deleting` condition with reason `MarkedForDeletion`.
1. **Snap-forward**: `status.deactivatedAt` is set to the **next tick boundary** after the moment of deletion, not the moment of deletion itself. This means the Subscription is charged for the full final tick — there is never a partial final tick on deactivation. For example, if a `MonthBoundary` Subscription is deleted on April 15, `deactivatedAt` is set to May 1 (the next month boundary), and the full April charge accrues.
1. **WaitingForCollectionJob**: the `Deleting` condition reason changes to `WaitingForCollectionJob`. The object remains visible in Kubernetes. The `SubscriptionChargeCollection` CostJob is the component that checks whether cleanup is allowed.
1. **Finalizer removal**: once at least `minPeriods` full ticks have elapsed since `activatedAt`, the CostJob removes the finalizer. Kubernetes then garbage-collects the object.

If the Offering did not set `minPeriods`, the finalizer is removed after the next CostJob run following deactivation.

### Checking the cleanup state

```bash
kubectl get subscription acme-postgres -n finops-operator-system -o yaml
```

While waiting for cleanup, you will see:

```yaml
status:
  ready: "False"
  deactivatedAt: "2026-05-01T00:00:00Z"
  conditions:
    - type: Deleting
      status: "True"
      reason: WaitingForCollectionJob
```

Once the finalizer is removed, `kubectl get` will no longer return the object.

## What happens to children

When a parent Subscription deactivates, the operator applies the effective `onParentDeactivate` policy to each child:

| Effective policy | Result for the child |
|---|---|
| `Deactivate` (default) | The child Subscription is deactivated. The `Ready` condition reason becomes `ParentDeactivated`. The child then follows its own deactivation sequence (snap-forward, `WaitingForCollectionJob`, finalizer removal). |
| `Orphan` | The child Subscription stays active. The `Ready` condition reason becomes `Orphaned`. The child continues accruing charges independently. |

The effective policy is resolved in this order: the child Subscription's own `spec.lifecycle.onParentDeactivate`, then the child Offering's `lifecycle.onParentDeactivate`, then `Deactivate` if neither is set. See [Parent-child subscriptions](./parent-child-subscriptions.md) for the full precedence explanation.

## What happens when a targetRef disappears

If a Subscription has `spec.lifecycle.targetRef` set and the target resource is deleted, the Subscription deactivates automatically. The sequence is the same as a user-initiated delete: snap-forward, `WaitingForCollectionJob`, finalizer removal after `minPeriods`.

The condition on the Subscription will show `Ready: False` with reason `TargetNotFound` during the window between the target's disappearance and the deactivation being processed.

```bash
kubectl describe subscription acme-postgres -n finops-operator-system
```

```text
Conditions:
  Type:    Ready
  Status:  False
  Reason:  TargetNotFound
```

After deactivation is recorded:

```text
Conditions:
  Type:    Deleting
  Status:  True
  Reason:  WaitingForCollectionJob
```

## Verify cleanup completed

After `minPeriods` ticks have elapsed and the CostJob has run, the Subscription object will be gone:

```bash
kubectl get subscription acme-postgres -n finops-operator-system
```

Expected output:

```text
Error from server (NotFound): subscriptions.finops.stakater.com "acme-postgres" not found
```

## Troubleshooting

If the Subscription will not delete and stays in `WaitingForCollectionJob`, the most likely cause is that `minPeriods` has not yet elapsed. Check `status.activatedAt` and count the full ticks. Remember that `minPeriods` on the Offering is immutable — you cannot lower it on an existing Offering. If you need a different cleanup guard for future Subscriptions, create a new Offering.

See [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md) for further guidance.

## Related

- [Subscribe to an offering](./subscribe-to-offering.md) — create a Subscription.
- [Parent-child subscriptions](./parent-child-subscriptions.md) — cascading deactivation through parent-child links.
- [Read subscription costs](./read-subscription-costs.md) — understand the final cost snapshot before cleanup.
- [Uninstall](./uninstall.md) — how to handle outstanding Subscriptions before removing the operator.
- [Subscription CRD reference](../reference/crds/subscription.md)
