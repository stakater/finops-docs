# Uninstall the FinOps Operator

This guide walks you through safely removing the FinOps Operator from your cluster. The process requires careful ordering: active Subscriptions hold finalizers that prevent their immediate deletion, and removing CRDs before those finalizers are released will strand objects in a terminating state that requires manual intervention.

**Prerequisites:**

- `kubectl` and `helm` access to the cluster.
- A list of all Subscriptions, Offerings, PriceBooks, FinOpsProviders, and CostJobs in all namespaces.

## Steps

### 1. Finalize outstanding Subscriptions

Before deleting anything, decide how to handle active Subscriptions. Every Subscription has a finalizer that the `SubscriptionChargeCollection` CostJob removes once at least `minPeriods` full ticks have elapsed since `activatedAt`. You have two options:

**Option A — Wait for `minPeriods` to elapse naturally.** Leave the Subscriptions active until the cleanup guard expires, then delete them. The CostJob removes the finalizer after the next run following expiry. This is the cleanest approach for production environments.

**Option B — Delete the CostJobs first, then delete Subscriptions.** If you delete the `SubscriptionChargeCollection` CostJob, the cleanup job will no longer run and finalizers will not be automatically removed. You will then need to manually patch each Subscription to remove the finalizer. Only use this approach when you do not care about the final billing records.

Check how many ticks have elapsed since each Subscription activated:

```bash
kubectl get subscription -A -o yaml | grep -E "activatedAt|deactivatedAt|minPeriods"
```

### 2. Delete all Subscriptions

Once you are ready to remove Subscriptions:

```bash
kubectl delete subscription --all -n finops-operator-system
```

Repeat for each namespace where Subscriptions exist. Wait until all Subscription objects are fully gone:

```bash
kubectl get subscription -A
```

The output should be empty. If any Subscription is stuck in a terminating state, the `SubscriptionChargeCollection` CostJob has not yet removed its finalizer. Either wait for the next CostJob run or — if you have decided to bypass the cleanup guard — manually remove the finalizer:

```bash
kubectl patch subscription <name> -n <namespace> \
  -p '{"metadata":{"finalizers":[]}}' \
  --type=merge
```

> **Warning:** Manually removing finalizers bypasses the `minPeriods` guard. Do this only when you are certain you do not need the billing records for the remaining ticks.

### 3. Delete all Offerings

With no Subscriptions remaining, Offerings can be deleted. The operator blocks Offering deletion while any Subscription references it, so Subscriptions must be gone first.

```bash
kubectl delete offering --all -n finops-operator-system
```

If deletion is blocked with reason `DependentSubscriptionsExist`, there are still active Subscriptions. Go back to step 2.

Wait until all Offerings are gone:

```bash
kubectl get offering -A
```

### 4. Delete the PriceBook

```bash
kubectl delete pricebook --all -n finops-operator-system
```

Repeat for any other namespace where PriceBooks exist.

### 5. Delete the FinOpsProvider

```bash
kubectl delete finopsprovider default
```

### 6. Delete all CostJobs

```bash
kubectl delete costjob --all -n finops-operator-system
```

This also causes the operator to remove the managed `CronJob` objects it created for each CostJob.

### 7. Run helm uninstall

```bash
helm uninstall finops-operator -n finops-operator-system
```

This removes the operator Deployment, Services, RBAC resources, and webhook configurations. The CRDs are not removed by `helm uninstall` by default (this is standard Helm behavior — CRDs are left in place to preserve any existing custom resources).

### 8. Remove the CRDs last

Only remove the CRDs after all custom resources have been fully deleted and all finalizers have been released.

```bash
kubectl get crds | grep finops.stakater.com
```

Delete each CRD:

```bash
kubectl delete crd finopsproviders.finops.stakater.com
kubectl delete crd pricebooks.finops.stakater.com
kubectl delete crd costjobs.finops.stakater.com
kubectl delete crd offerings.finops.stakater.com
kubectl delete crd subscriptions.finops.stakater.com
```

> **Warning:** If you delete CRDs while any Subscription still has a finalizer, Kubernetes will remove the CRD's custom resources but the finalizer records may prevent the objects from being garbage-collected cleanly. You will need to use `kubectl patch` to manually remove finalizers from each stranded object before they can be fully deleted. Always remove all Subscriptions and release their finalizers before deleting CRDs.

### 9. Verify the cluster is clean

```bash
kubectl get all -n finops-operator-system
kubectl get crds | grep finops.stakater.com
```

Both commands should return empty results.

## Troubleshooting

If Offerings are stuck in deletion with reason `DependentSubscriptionsExist` or `DependentOfferingsExist`, remove all referencing Subscriptions and dependent Offerings first. See [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Deactivation and cleanup](./deactivation-and-cleanup.md) — the per-Subscription cleanup sequence in detail.
- [Installation](../getting-started/installation.md) — re-install the operator if needed.
