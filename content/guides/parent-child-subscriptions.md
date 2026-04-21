# Parent-child subscriptions

This guide explains how to link Subscriptions together in a parent-child relationship. Use this pattern when you want to group charges for a logical service unit — for example, a database instance (parent) and its storage allocation (child) — and control whether child Subscriptions deactivate or survive when the parent deactivates.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- Two or more `Offerings` that are `Ready: True`. See [Define an offering](./define-offering.md).
- `kubectl` access to the operator namespace (typically `finops-operator-system`).

## When to use a parent Subscription

Use a parent-child relationship when:

- **Traceability**: you want to group related charges under a single logical unit. Querying the parent Subscription gives you an aggregation point; querying each child shows the detailed breakdown.
- **Cascading deactivation**: when the parent service ends (for example, a managed Postgres instance is removed), you want all its associated Subscriptions (storage, backup, monitoring) to deactivate automatically.

Without a parent link, each Subscription is independent and must be deactivated individually.

## Deactivate vs Orphan

When a parent Subscription deactivates, each child Subscription follows one of two policies:

| Policy | Effect on the child |
|---|---|
| `Deactivate` | The child Subscription is also deactivated. Billing stops for the child. The child's condition reason becomes `ParentDeactivated`. |
| `Orphan` | The child Subscription stays active. Billing continues. The child's condition reason becomes `Orphaned`. |

The `Orphan` policy is useful when a child represents a resource that outlives its parent — for example, a persistent volume that you want to keep billing for even after the service that used it is gone.

## Policy precedence

The effective policy is resolved in this order:

1. `Subscription.spec.lifecycle.onParentDeactivate` (if set on the child Subscription) — takes highest precedence.
1. The child Offering's `lifecycle.onParentDeactivate` default.
1. If neither is set: `Deactivate`.

This means a child Subscription can always override the Offering's default. See [Define an offering](./define-offering.md) for a note on `lifecycle.allowOverride`.

## Example: managed Postgres with a storage child

In this example, a "managed-Postgres" parent Subscription is tied to a `Deployment`. A child "managed-Postgres-storage" Subscription represents the persistent storage allocation. The storage Subscription uses the `Orphan` policy — if the Postgres service is removed, the storage billing continues until the volume is explicitly cleaned up.

**Parent Subscription:**

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-postgres
  namespace: finops-operator-system
spec:
  offeringRef:
    name: managed-postgres
  lifecycle:
    targetRef:
      apiVersion: apps/v1
      kind: Deployment
      namespace: acme
      name: postgres
```

**Child Subscription with Orphan policy:**

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Subscription
metadata:
  name: acme-postgres-storage
  namespace: finops-operator-system
spec:
  offeringRef:
    name: managed-postgres-storage
  parent:
    subscriptionRef:
      name: acme-postgres
  lifecycle:
    onParentDeactivate: Orphan
```

Apply both in order — the parent first, then the child:

```bash
kubectl apply -f acme-postgres.yaml
kubectl apply -f acme-postgres-storage.yaml
```

The child Subscription activates only after the parent is active. If the parent is not yet active, the child will show `Ready: False` with reason `ParentSubscriptionNotReady`.

## Verify the relationship

```bash
kubectl get subscription -n finops-operator-system
```

Expected output:

```text
NAME                    READY
acme-postgres           True
acme-postgres-storage   True
```

Inspect the child to confirm the parent reference:

```bash
kubectl describe subscription acme-postgres-storage -n finops-operator-system
```

The `Spec` section will show the `parent.subscriptionRef` pointing to `acme-postgres`.

### Simulate a parent deactivation

Delete the parent Deployment to trigger deactivation via `targetRef`:

```bash
kubectl delete deployment postgres -n acme
```

Then check the child:

```bash
kubectl get subscription acme-postgres-storage -n finops-operator-system -o yaml
```

Because the child uses `Orphan`, it will remain `Ready: True` with condition reason `Orphaned`.

## Troubleshooting

If the child Subscription shows `ParentSubscriptionNotFound` or `ParentSubscriptionNotReady`, check that the parent Subscription exists and is active. See [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md).

## Related

- [Subscribe to an offering](./subscribe-to-offering.md) — create a basic Subscription.
- [Required offerings](./required-offerings.md) — a complementary mechanism for declaring service dependencies at the Offering level.
- [Deactivation and cleanup](./deactivation-and-cleanup.md) — understand what happens when a parent deactivates and how cleanup proceeds.
- [Subscription CRD reference](../reference/crds/subscription.md)
