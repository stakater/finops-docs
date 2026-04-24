# Status conditions

A condition is a status signal that the operator writes onto a resource to communicate state. Users observe conditions through `kubectl describe <kind> <name>` or by examining the resource in YAML format with `kubectl get <kind> <name> -o yaml`. The operator uses a small, fixed vocabulary of condition types and reasons to signal resource health, readiness, and lifecycle events.

## Condition types

| Type | Description |
|---|---|
| `Ready` | Indicates whether the resource is currently usable and its declared intent is fulfilled. |
| `Deleting` | Present while the resource is being cleaned up; the reason explains why cleanup is or is not allowed. |

## Offering conditions

### Ready reasons

| Reason | Meaning | What to do |
|---|---|---|
| `ValidationSucceeded` | The Offering's fields passed admission validation. | No action needed. |
| `ValidationError` | A validation step failed for a reason not covered above. | Inspect the condition message for specifics. Typical causes are field-level validation failures not covered by other reasons. |
| `SpecImmutable` | A user tried to modify an immutable field. | The Offering `spec` cannot be changed after creation. Create a new Offering with the desired values and migrate new Subscriptions to it. |

### Deleting reasons

| Reason | Meaning | What to do |
|---|---|---|
| `DeletionAllowed` | Nothing references the Offering; the operator will let Kubernetes delete it. | The Offering can be deleted. Kubernetes will complete cleanup shortly. |
| `DeletionBlocked` | Something still references the Offering; admission blocks deletion. | Something still references this Offering. Inspect the condition message for specifics. |
| `DependentSubscriptionsExist` | A Subscription references this Offering. | At least one Subscription still references this Offering via `offeringRef`. Delete those Subscriptions first, or migrate them to a different Offering. |

## Subscription conditions

### Ready reasons

| Reason | Meaning | What to do |
|---|---|---|
| `ValidationSucceeded` | The Subscription's fields passed admission validation. | No action needed. |
| `ActivationSucceeded` | The Subscription is activated and validated. | No action needed. The Subscription is active and accruing charges as configured. |
| `ValidationError` | A validation step failed for a reason not covered above. | Inspect the condition message for specifics. Typical causes are field-level validation failures not covered by other reasons. |
| `OfferingNotFound` | `offeringRef` does not resolve. | Check the Subscription's `offeringRef`. The referenced Offering does not exist — create it or correct the reference. |
| `OfferingNotReady` | The referenced Offering exists but is not ready. | Investigate the Ready condition on the referenced Offering. Once it becomes Ready, the Subscription activates automatically. |
| `MarkedForDeletion` | The Subscription has been marked for deletion. | Expected after a user initiates deletion. The Subscription will be fully removed once `minPeriods` has elapsed since `activatedAt`. |

### Deleting reasons

| Reason | Meaning | What to do |
|---|---|---|
| `WaitingForCollectionJob` | The Subscription is deactivated and pending cleanup by the scheduled `SubscriptionChargeCollection` job. The `minPeriods` duration has not yet fully elapsed since `activatedAt`. | Expected. The Subscription has been marked for deletion and will be removed once the scheduled `SubscriptionChargeCollection` CostJob has seen `minPeriods` full ticks pass since `activatedAt`. |

For troubleshooting guidance on remediation workflows, see [Troubleshooting](../troubleshooting.md).
