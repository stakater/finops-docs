# Required offerings

This guide explains how to declare that one `Offering` depends on another. When you configure `compatibility.requiredOfferings` on an `Offering`, the operator checks that the required `Offering` is active on the parent Subscription or a sibling Subscription before it allows the dependent Subscription to activate.

**Prerequisites:**

- A running FinOps Operator installation. See [Installation](../getting-started/installation.md).
- `kubectl` access to the operator namespace (typically `finops-operator-system`).
- Familiarity with [Define an offering](./define-offering.md).

## What "required offering" means

When Offering A lists Offering B in its `compatibility.requiredOfferings`, any Subscription to Offering A requires that Offering B is already active in the same logical group before A's Subscription becomes ready.

Concretely, the operator checks that a Subscription referencing Offering B exists and is active either:

- On the **parent Subscription** (the Subscription that acts as the parent of the Subscription being activated), or
- As a **sibling Subscription** of the same parent.

This is the mechanism for expressing service dependencies. For example, a "Managed Postgres" offering that only makes sense on a cluster that has subscribed to a "Platform Base" offering.

## Transient Ready: False is expected

When you create Offerings in a batch, there is a short window where the ordering may not have settled. During this time you will see:

```
NAME              READY
managed-postgres  False
platform-base     True
```

The `managed-postgres` Offering will show `Ready: False` with one of these condition reasons:

| Reason | Meaning |
|---|---|
| `RequiredOfferingNotFound` | The referenced Offering does not exist yet. Wait for it to be created. |
| `RequiredOfferingNotReady` | The referenced Offering exists but is not yet `Ready: True`. Wait for it to reconcile. |

Once the required Offering becomes `Ready: True`, the dependent Offering reconciles back to `Ready: True` automatically. No manual intervention is needed.

## Cycle detection

The operator checks for circular dependencies at admission time. If you attempt to create an Offering whose `requiredOfferings` graph forms a cycle — for example, A requires B and B requires A — the creation is rejected with reason `CircularDependencyDetected`. Fix the dependency graph before re-applying.

## Example: Managed Postgres requires Platform Base

**Platform Base Offering** — no dependencies; monthly subscription fee:

```yaml
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
  lifecycle:
    onParentDeactivate: Deactivate
```

**Managed Postgres Offering** — requires `platform-base` to be active:

```yaml
apiVersion: finops.stakater.com/v1alpha1
kind: Offering
metadata:
  name: managed-postgres
  namespace: finops-operator-system
spec:
  pricing:
    subscriptionFee:
      period: 1h
      tickAlignment: ActivatedAt
      priceMicros: 40000000
      minPeriods: 2
  compatibility:
    requiredOfferings:
      - name: platform-base
  lifecycle:
    onParentDeactivate: Deactivate
```

Apply both:

```
kubectl apply -f platform-base.yaml
kubectl apply -f managed-postgres.yaml
```

If you apply `managed-postgres` before `platform-base` exists, `managed-postgres` will be `Ready: False` with reason `RequiredOfferingNotFound`. Once you apply `platform-base` and it becomes ready, `managed-postgres` transitions to `Ready: True`.

## Verify it worked

```
kubectl get offering -n finops-operator-system
```

Expected output once both Offerings are ready:

```
NAME              READY
platform-base     True
managed-postgres  True
```

Check the condition detail:

```
kubectl describe offering managed-postgres -n finops-operator-system
```

Look for:

```
Conditions:
  Type:    Ready
  Status:  True
  Reason:  ValidationSucceeded
```

## Troubleshooting

If `managed-postgres` stays `Ready: False`, check the condition reason in `kubectl describe`. `RequiredOfferingNotFound` means `platform-base` was not created. `RequiredOfferingNotReady` means it exists but is not yet healthy. `CircularDependencyDetected` means the dependency graph has a cycle — review your `compatibility.requiredOfferings` entries.

See [Troubleshooting](../troubleshooting.md) and [Status conditions reference](../reference/status-conditions.md) for further guidance.

## Related

- [Define an offering](./define-offering.md) — full reference for all `Offering` fields.
- [Subscribe to an offering](./subscribe-to-offering.md) — create Subscriptions that activate under the dependency constraint.
- [Parent-child subscriptions](./parent-child-subscriptions.md) — how the parent/sibling lookup works at Subscription activation time.
- [Offering CRD reference](../reference/crds/offering.md)
