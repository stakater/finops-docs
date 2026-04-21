# Troubleshooting

This page lists common symptoms, their typical causes, and remedies. For a reference-style listing of all status conditions and their meanings, see [Status conditions](reference/status-conditions.md).

## Symptom → cause → remedy

### Subscription stays `Ready: False`

Inspect the Ready condition to find the specific reason:

```bash
kubectl describe subscription <name>
```

| Reason | Cause | Remedy |
|---|---|---|
| `OfferingNotFound` | `offeringRef` does not resolve to an existing Offering. | Create the Offering or correct the name in `offeringRef`. |
| `OfferingNotReady` | The referenced Offering exists but its own `Ready` condition is `False`. | Resolve the Offering's condition first (see [Offering rejected on create](#offering-rejected-on-create) below). |
| `ParentSubscriptionNotFound` | `parent.subscriptionRef` points to a Subscription that does not exist. | Create the parent Subscription or correct the reference. |
| `ParentSubscriptionNotReady` | The parent Subscription exists but is not yet active. | Wait for the parent to reach `Ready: True`, or resolve its blocking condition. |
| `TargetNotFound` | `lifecycle.targetRef` points to a resource that does not exist or is not yet present. | Create the target resource or remove `targetRef` if targeting is not required. |
| `TargetIsSelfReference` | `lifecycle.targetRef` resolves to the Subscription itself. | Set `targetRef` to a different resource or remove the field. |

For the full condition vocabulary, see [Status conditions](reference/status-conditions.md).

### Offering stuck in deletion

When an Offering cannot be deleted, admission blocks the request and the `Deleting` condition carries one of these reasons:

- `DependentSubscriptionsExist` — one or more Subscriptions still reference this Offering.
- `DependentOfferingsExist` — another Offering lists this one in `compatibility.requiredOfferings`.

Identify the dependents:

```bash
kubectl describe offering <name>
```

The condition message names the blocking resources. Delete or migrate those dependents first, then retry the Offering deletion.

### Offering rejected on create

Admission rejects an Offering at creation time when the `compatibility.requiredOfferings` list contains a cycle or a self-reference:

- `CircularDependencyDetected` — the `requiredOfferings` graph forms a cycle (for example, Offering A requires B, and B requires A).
- Self-reference — the Offering lists its own name in `compatibility.requiredOfferings`.

Remove the cycle or the self-reference from the Offering spec and resubmit.

### Subscription `status.costs` is empty

Two common causes:

1. **No `SubscriptionChargeCollection` CostJob is scheduled.** Check whether an active CostJob of type `SubscriptionChargeCollection` exists:

   ```bash
   kubectl get costjob -A
   ```

   If none exists, create one. The operator will not compute subscription charges without it.

1. **The Subscription is not active.** Check `status.ready`. If it is `False`, resolve the blocking condition first (see [Subscription stays Ready: False](#subscription-stays-ready-false) above).

### Subscription will not delete

When a Subscription cannot be deleted, the `Deleting` condition shows reason `WaitingForCollectionJob`. The operator holds a finalizer until the `SubscriptionChargeCollection` job has run at least `minPeriods` full ticks since `status.activatedAt`.

Wait for `minPeriods` ticks to elapse. The finalizer is removed automatically once the condition is met and the next collection job runs.

If you need a shorter guard on future Subscriptions, create a new Offering with a lower `minPeriods` value. You cannot change `minPeriods` on the existing Offering — Offering spec is immutable.

### OpenCost shows stale prices

In BYO-OpenCost mode the operator writes pricing data to a ConfigMap named `finops-operator-custom-pricing-configs` and restarts the OpenCost deployment when the ConfigMap changes. If prices appear stale, confirm that the restart completed:

```bash
kubectl rollout status deployment/<opencost-deployment> -n <opencost-namespace>
```

If the rollout did not happen, check that the operator has permission to restart the OpenCost deployment and that the ConfigMap is in the correct namespace.

### CostJob `lastExecutionTime` never updates

The operator creates a Kubernetes CronJob in the operator's namespace for each CostJob. If `lastExecutionTime` does not advance, check:

1. The CronJob exists and is not suspended:

   ```bash
   kubectl get cronjob -n finops-operator-system
   ```

1. The operator's own logs for scheduling or connection errors.
1. The PostgreSQL and OpenCost connection strings in the relevant Secret references — confirm the Secrets exist in the operator's namespace and contain correct values.

### Webhook rejection messages

Admission rejects requests that violate the operator's invariants. The three most common messages:

| Message | Meaning | Remedy |
|---|---|---|
| `"FinOpsProvider must be named 'default'"` | Only one FinOpsProvider is allowed per cluster and it must carry the name `default`. | Rename the resource to `default`. |
| `"Exactly one provider option must be set"` | The FinOpsProvider spec must contain exactly one of `awsoptions`, `gcpoptions`, `azureoptions`, or `onpremoptions`. | Remove all but one provider option block. |
| `"Offering spec is immutable"` | A field that cannot change after creation was modified. | Create a new Offering with the desired values instead of updating the existing one. |

---

For a complete reference of every condition reason and what to do about it, see [Status conditions](reference/status-conditions.md). For task-oriented material on configuring pricing and subscriptions, see the [Guides](guides/define-pricing.md).
