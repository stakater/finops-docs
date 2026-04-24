# Deactivation and cleanup

This guide explains what happens when a Subscription is deactivated by user action. It covers the deactivation sequence, the snap-forward mechanism, the `minPeriods` cleanup guard, and how to monitor cleanup progress.

**Prerequisites:**

- One or more active Subscriptions. See [Subscribe to an offering](./subscribe-to-offering.md).
- A `CostJob` of type `SubscriptionChargeCollection` running. See [Collect cost data](./collect-cost-data.md).

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
kubectl get subscription acme-platform-base -n finops-operator-system -o yaml
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

## Verify cleanup completed

After `minPeriods` ticks have elapsed and the CostJob has run, the Subscription object will be gone:

```bash
kubectl get subscription acme-platform-base -n finops-operator-system
```

Expected output:

```text
Error from server (NotFound): subscriptions.finops.stakater.com "acme-platform-base" not found
```

## Troubleshooting

If the Subscription will not delete and stays in `WaitingForCollectionJob`, the most likely cause is that `minPeriods` has not yet elapsed. Check `status.activatedAt` and count the full ticks. Remember that `minPeriods` on the Offering is immutable — you cannot lower it on an existing Offering. If you need a different cleanup guard for future Subscriptions, create a new Offering.

See [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md) for further guidance.

## Related

- [Subscribe to an offering](./subscribe-to-offering.md) — create a Subscription.
- [Read subscription costs](./read-subscription-costs.md) — understand the final cost snapshot before cleanup.
- [Uninstall](./uninstall.md) — how to handle outstanding Subscriptions before removing the operator.
- [Subscription CRD reference](../reference/crds/subscription.md)
