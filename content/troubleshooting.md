# Troubleshooting

Almost everything the operator decides is recorded on a condition, so reading the conditions is the first move for every symptom on this page:

```sh
kubectl describe subscription acme-platform-base -n finops-operator-system
```

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{range .status.conditions[*]}{.type}{"  "}{.status}{"  "}{.reason}{"  "}{.message}{"\n"}{end}'
```

This page runs the other way round from [Status conditions](reference/status-conditions.md), which is the exhaustive table of every type, status, and reason. Here the entry point is what you observed. Each symptom names the reason string you will actually see, says why the operator wrote it, and gives the remedy.

## Subscriptions

### A Subscription never becomes ready

Activation is four checks in a fixed order, the Offering, then the parent, then compatibility coverage, then the `lifecycle.targetRef`, and they run on every reconcile rather than at admission. A Subscription that fails one is still admitted, held at `Ready=False`, and activates by itself once the cause clears. Only the first failing gate is reported, so fix that one and read the condition again.

The Offering gate is the common one:

| Reason | Cause | Remedy |
| --- | --- | --- |
| `OfferingNotFound` | `spec.offeringRef` resolves to nothing. | Create the Offering, or replace the Subscription. `namespace` is required on the reference and is never filled in from the Subscription's own namespace, so a reference that reads correctly in a single-namespace manifest can still point nowhere. `spec.offeringRef` is immutable, so it cannot be corrected in place. |
| `OfferingNotReady` | The Offering exists and its own `Ready` condition is `False`. | Fix that Offering, starting from [an Offering that is not ready](#an-offering-is-not-ready-and-publishes-no-pricing). This Subscription activates on its own afterwards. |

A gate failing does not stop the billing on a Subscription that had already activated. `status.activatedAt` stands, and the charge collection job selects on that timestamp rather than on readiness, so charges keep accruing while `Ready` reads `False`. [Subscription Ready reasons](reference/status-conditions.md#ready) has the full list, and [the four activation gates](concepts/subscription.md#the-four-activation-gates) sets out what each gate tests.

### A Subscription is waiting on its parent or its target

Where `spec.parent` is set, the parent gate holds the Subscription until the parent exists, has not deactivated, and is ready itself:

| Reason | Meaning | Remedy |
| --- | --- | --- |
| `ParentSubscriptionNotFound` | `spec.parent.subscriptionRef` does not resolve. | Create the parent at exactly that name and namespace. `spec.parent` is immutable including whether it is present at all, so a wrong parent means a new Subscription rather than an edit. |
| `ParentSubscriptionNotReady` | The parent exists but has not activated. | Transient. Clear the parent's own gate and this one clears with it. |
| `ParentSubscriptionDeactivated` | The parent has ended. | On a Subscription that never activated this never clears, because deactivation is one-way. Rebuild the family instead of waiting. |

Where `spec.lifecycle.targetRef` is set, the target gate holds the Subscription until that object exists and reports `TargetNotFound` while it does not. The check is a plain get on the name, namespace, kind, and API version you gave it, so a typo in any of the four reads as a missing target. It tests existence only: a target that exists and is itself broken does not hold the Subscription back.

`TargetIsSelfReference` means the `targetRef` names this Subscription, matching on all four fields. That is refused at admission on create, so it only appears when a later edit introduces it.

### A Subscription reads `Ready=False` with reason `ValidationSucceeded`

This looks like success and is not. Every deactivation writes `Ready=False` with reason `ValidationSucceeded`, which says nothing about the cause, and puts the real cause on the `Active` condition. Read both, plus `status.deactivatedAt`:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{.status.ready}{"  "}{.status.deactivatedAt}{"\n"}{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\n"}{end}'
```

A Subscription with no `Active` condition at all has never activated, and its `Ready` reason names the failing gate. `Active=True` beside `READY False` means it is still active and still accruing while a gate fails transiently. `Active=False` means it has ended, terminally, and the `Active` reason carries the cause. [Tell a waiting Subscription from a finished one](guides/subscribe-to-offering.md#step-5-tell-a-waiting-subscription-from-a-finished-one) has the discriminator table for all four states.

### A Subscription deactivated itself with `CompatibilityRequirementNotMet`

`Active=False` with that reason, and a message of the form `required offering <namespace>/<name> not covered by an active subscription in the family`.

The bound Offering lists `compatibility.requiredOfferings`, and coverage for one of those entries went away, usually because the sibling Subscription supplying it was deleted or deactivated. Coverage is re-evaluated on every reconcile rather than once at activation, and only an active Subscription satisfies it: one in the same family, meaning sharing the same root ancestor recorded in `status.compatibilityRoot`, and excluding the Subscription itself and its own descendants, because coverage never flows up from a Subscription's own dependents.

Find what is missing, then find who could cover it:

```sh
kubectl get offering platform-base -n finops-operator-system \
  -o jsonpath='{range .spec.compatibility.requiredOfferings[*]}{.namespace}{"/"}{.name}{"\n"}{end}'

kubectl get subscription -A \
  -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,OFFERING:.spec.offeringRef.name,READY:.status.ready,ROOT:.status.compatibilityRoot'
```

The deactivation is terminal. Restoring the sibling does not revive this Subscription, because one carrying `status.deactivatedAt` is never re-validated. Recovery means a new Subscription created after the covering Subscription is active again.

The same reason on the `Ready` condition with no `Active` condition present means nothing ended: the Subscription has not activated because coverage was never there. Subscribe a relative to the missing Offering and it activates on the next reconcile.

### A Subscription's `status.costs` stays empty

Four causes, worth checking in this order:

1. No `SubscriptionChargeCollection` CostJob is scheduled, or none has completed a run. Nothing else writes `status.costs`.

   ```sh
   kubectl get costjob -A
   ```

   That job type writes nothing to its own status, so read its Jobs and their pod logs rather than the CostJob.

1. The Subscription never activated. One with no `status.activatedAt` is skipped outright by the run, whatever else is true of it.
1. The bound Offering declares no subscription fee. The buckets are shaped around the fee, so an Offering carrying only `resourcePricing` produces no buckets at all, even while that Subscription's usage charges are computed and written to the `subscription_charges` table. Read those from the table.
1. The Offering could not be read. Every run fetches each Subscription's Offering fresh, so an Offering that has been deleted or renamed leaves its Subscriptions with no buckets.

A Subscription with no `CostsResolved` condition was never summarised at all, which points at the run rather than at the numbers. [When a bucket or a meter is missing](guides/read-subscription-costs.md#when-a-bucket-or-a-meter-is-missing) covers a bucket that is present but thinner than expected.

### A Subscription will not finish deleting

`Deleting=False` with reason `WaitingForCollectionJob` is the only thing that condition ever says, and on its own it means the wind-down is proceeding normally. It becomes a symptom when it does not end.

Only a `SubscriptionChargeCollection` run takes the finalizer off, and only when four things hold on the same run: the Subscription is deactivated, `minPeriods` has elapsed since `status.activatedAt`, charges are finalized through its last billable hour, and nothing was recorded against it during that run. The run's log says which one held it:

```sh
kubectl get jobs -n finops-operator-system --sort-by=.metadata.creationTimestamp
kubectl logs -n finops-operator-system job/<job-name>
```

`MinPeriods not yet satisfied, keeping finalizer` and `Charges not finalized through deactivation hour, keeping finalizer` both mean the wait is working as designed.

`minPeriods` is a cleanup guard and nothing more. Billing carries on tick by tick while it waits, and no shortfall is charged for the ticks between the deletion and the count being reached, so a Subscription deleted early is simply never charged for the ticks that did not run and waiting costs nothing but time. The value cannot be lowered, because an Offering's spec is immutable. Creating a new Offering with a lower `minPeriods` changes the guard only for Subscriptions created against that new Offering later; it does nothing for this one, and there is no shortfall charge for it to avoid.

The one cause that never clears by waiting is a missing Offering. Every run re-reads each deleting Subscription's Offering to price the remaining hours and to count the ticks, and a failed read is recorded as an error against that Subscription, which holds the finalizer on that run and on every run after it. The Offering's own delete guard does not prevent this, because it counts only dependents whose `status.ready` is `True` and a deactivated Subscription is not ready. [When a Subscription will not finish deleting](getting-started/uninstalling.md#when-a-subscription-will-not-finish-deleting) has the recovery, which is to recreate the Offering at the same name and namespace, and the last-resort finalizer patch and what it forfeits. [When the finalizer will not release](guides/deactivate-a-subscription.md#when-the-finalizer-will-not-release) lists the remaining causes.

## Offerings

### An Offering is not ready and publishes no pricing

`Ready` and `PricingResolved` are written in the same pass and always agree, so an Offering that is not ready has published no `status.resolvedPricing` and no Subscription against it can activate.

| Reason | Cause | Remedy |
| --- | --- | --- |
| `RequiredOfferingNotFound` | A `compatibility.requiredOfferings` entry does not resolve. | Create the missing Offering or replace this one, remembering that `namespace` is required on the entry. Apply order does not matter: interdependent Offerings may be applied in any order and each becomes ready once its requirements exist. |
| `RequiredOfferingNotReady` | A required Offering exists and is not itself ready. | Fix that one. This recovers on its own afterwards. |
| `CircularDependencyDetected` | The requirement graph loops, or the Offering requires itself. The message carries the path it walked. | Break the loop, which means replacing one of the Offerings in it, since a spec cannot be edited. |
| `NoActivePricebook` | The Offering declares `resourcePricing` and no active currency PriceBook exists. | See [the next symptom](#an-offering-is-stuck-at-pricingresolvedfalse-with-noactivepricebook). |
| `PricebookParseFailed` | The active PriceBook holds a rate this Offering's meters cannot resolve against. | Fix the rate on the PriceBook; see [a PriceBook that is not ready](#a-pricebook-is-not-ready). |
| `ValidationError` | A lookup failed some other way, typically an API error while reading a required Offering. | Read the message. Transient, and retried on a lengthening delay. |

None of these is terminal, and each is re-evaluated on the next reconcile. Pricing is resolved once and then kept, though, so an Offering that has already published `status.resolvedPricing` does not re-resolve when the PriceBook changes.

### An Offering is stuck at `PricingResolved=False` with `NoActivePricebook`

The message reads `offering <namespace>/<name>: no active pricebook to resolve metered pricing`.

The Offering declares `pricing.resourcePricing`, so its meters need unit rates, and no PriceBook in the cluster is both marked active and set to `valuationMode: currency`. The operator refuses to publish in that state deliberately: every meter rate would resolve to zero and `status.resolvedPricing` would then expose the Offering's margins as the price.

Look at what the cluster actually has:

```sh
kubectl get pricebooks --all-namespaces \
  -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,MODE:.spec.valuationMode,ACTIVE:.status.active,READY:.status.ready'
```

If nothing shows `ACTIVE true`, mark the book you want:

```sh
kubectl annotate pricebook onprem-standard -n finops-operator-system \
  finops.stakater.com/active=true --overwrite
```

If a book is active but its `MODE` is `percent`, it carries no currency rates and cannot resolve them whatever its readiness says, so a currency book has to exist as well. Either way the Offering resolves on the next reconcile, which is retried on a lengthening delay without any edit to the Offering.

An Offering with only a `subscriptionFee` and no `resourcePricing` never hits this. It needs no PriceBook and resolves regardless.

### An Offering will not delete

Deletion is refused at admission, so the `kubectl delete` fails outright rather than leaving the object terminating. The error names the dependents: `still referenced by subscriptions` followed by the Subscriptions whose `offeringRef` points here, or `still required by dependent resources` followed by the Offerings that list this one under `compatibility.requiredOfferings`. The reconciler records the same finding as `Deleting=False` with reason `DependentSubscriptionsExist` or `DependentOfferingsExist`.

Delete or migrate the dependents it named, then retry.

!!! warning
    Both checks count only dependents whose `status.ready` is `True`, so a Subscription that never activated or has already deactivated does not block the delete, even though every collection run still reads this Offering to price that Subscription's remaining hours. Deleting the Offering out from under one of those strands its finalizer permanently. Confirm no dependent Subscriptions are left at all, rather than only that the delete was accepted.

### An edit to an Offering is rejected

An Offering's `spec` is immutable in full, with the rejection message `offering spec is immutable`. That rule lives on the CRD and is evaluated by the API server, not by the Offering webhook, whose update path inspects nothing at all. Because it is a CRD rule it applies on every install, whether or not the webhooks are registered and whether or not the manager pod is running.

There is no way to change an Offering's terms. Different pricing, a different `minPeriods`, or a different requirement list means a second Offering, with new Subscriptions created against it; existing Subscriptions keep the terms they were created against. [Replacing an Offering](concepts/offering.md#replacing-an-offering) has the sequence.

## PriceBooks

### A PriceBook is not ready

`Ready=False` with reason `PricebookParseFailed`, and a message of the form `rate "<field>" ("<value>"): ...` naming the first field that failed and the value it held.

Readiness parses every rate on `spec.rates` in turn, `cpuHour`, `spotCPUHour`, `ramGbHour`, `spotRAMGbHour`, `pvGbHour`, `gpuHour`, and `networkGiB`, and stops at the first one it cannot read as a currency value. Fix that field. Malformed shapes are already refused at admission by a pattern on each rate, so what reaches this check is usually a value too large to express in micro-units. A book whose `valuationMode` is `percent` carries no rates to parse and is ready trivially.

Readiness and selection are independent, so a book can hold `Active=True` and `Ready=False` at the same time. That is on purpose: OpenCost keeps the pricing document it already had rather than silently switching to rates the operator could not read, and a typo produces a visible failure instead of different prices.

### The chart's default PriceBook never becomes active

The chart's optional `<release>-default-pricing` book writes `finops.stakater.com/active: "true"` under `metadata.labels`, and the operator reads only the annotation of that name. The chart's marker therefore has no effect on selection at all.

A chart-provisioned book still becomes active on a fresh cluster by winning the bootstrap election, which runs only when no book carries the annotation, and it loses the slot to any book you do annotate. To pin it explicitly, set the annotation yourself:

```sh
kubectl annotate pricebook finops-operator-default-pricing -n finops-operator-system \
  finops.stakater.com/active=true --overwrite
```

[Switch the active PriceBook](guides/switch-active-pricebook.md) covers moving the marker between books, and why leaving two of them annotated makes the next switch ambiguous.

### OpenCost shows stale prices

Only the active book touches OpenCost. It renders its rates into the `finops-operator-custom-pricing-configs` ConfigMap, and when the rendered document differs from what was already there the operator patches the OpenCost Deployment's pod template with a `finops.stakater.com/restartedAt` annotation to force a rolling restart, because OpenCost reads its pricing document only at startup.

Check the steps in order:

```sh
kubectl get configmap finops-operator-custom-pricing-configs -n finops-operator-system -o yaml
kubectl rollout status deployment/finops-operator-opencost -n finops-operator-system
```

The Deployment and the namespace are whatever `OPENCOST_DEPLOYMENT_NAME` and `OPENCOST_DEPLOYMENT_NAMESPACE` say on the manager, which the chart fills from `controllerManager.manager.env`. A mismatch between those two values and where OpenCost actually runs is the usual cause, because the ConfigMap is then written where OpenCost is not reading and the restart patches a Deployment that does not exist. Confirm too that the active book is the one you meant and that its `status.activePricing` is populated, which happens only on a book that is both active and ready.

### Usage is priced from a book that is not the active one

A `ResourceCostCollection` run stamps a PriceBook and its currency onto the allocation rows it writes, and it picks that book by listing the PriceBooks in its own namespace and taking the first, without consulting `status.active`. Where a namespace that runs a collection CostJob holds more than one PriceBook, the rates on its allocation rows can therefore come from a book that is not active.

Keep a single PriceBook in any namespace that runs a `ResourceCostCollection` CostJob, and hold retired or draft books in another namespace. The OpenCost pricing document is unaffected, because that path does select on the active book.

## CostJobs

### `status.lastExecutionTime` never advances

Each CostJob generates a Kubernetes CronJob named `<costjob-name>-cronjob` in the CostJob's own namespace, owned by it. The status fields are written by the run itself, so a status that never moves means no run is completing.

1. Confirm the CronJob exists, is not suspended, and carries the schedule you expected:

   ```sh
   kubectl get cronjob -n finops-operator-system
   ```

   `spec.interval` is matched against a fixed set of values rather than converted arithmetically, and an unrecognised value is accepted and falls through to the daily `0 0 * * *` with nothing on the CostJob to say the value was ignored. [From interval to schedule](concepts/costjob.md#from-interval-to-schedule) lists the values that work.

1. Read the most recent Job it created and that pod's log.
1. Confirm the dependency values reach the pod. The run needs `POSTGRES_CONNECTION_STRING`, which arrives through a `secretKeyRef` into `<costjob-name>-costjob-secret` in the same namespace, and the OpenCost URL the manager passes down from its own `OPENCOST_CONNECTION_STRING`.
1. Read the manager's log for reconcile errors. A malformed `IMAGE_PULL_SECRETS` fails the CostJob reconcile outright, and an empty `OPERATOR_IMAGE` produces a CronJob whose pods have no image to run.

Only a `ResourceCostCollection` CostJob writes these fields. A `SubscriptionChargeCollection` CostJob's status stays empty by design, so watch its Jobs and their pod logs, and the `CostsResolved` condition on the Subscriptions it prices, instead. [CostJob](reference/status-conditions.md#costjob) covers what is and is not written.

### A CostJob timeout appears to be ignored

Two of the timeout keys change nothing, and neither one tells you so:

| What you set | What happens |
| --- | --- |
| `costJob.k8sOperationTimeout` or `chargeCollectionJob.k8sOperationTimeout` in Helm values | The chart renders a field called `k8sOperationTimeout` onto the CostJob. The CRD calls that field `kubernetesOperationTimeout`, so the API server prunes the unknown field and the object comes back without it. Set `kubernetesOperationTimeout` on the CostJob directly instead. |
| `databaseViewsRefreshTimeout`, on the object or through either chart key | The field is accepted, is not pruned, and bounds nothing. The materialized view it used to refresh had no readers and was dropped, and a collection run no longer refreshes any view. |

Read the object back to see what actually landed:

```sh
kubectl get costjob allocation-collection -n finops-operator-system -o yaml
```

A third case looks the same from outside: a duration that is present and does not parse is logged and the type's default is kept, so a typo degrades to the default rather than failing the run. [databaseViewsRefreshTimeout](reference/configuration.md#databaseviewsrefreshtimeout) and the table above it give what each of the six live timeouts bounds.

## FinOpsProvider

### A FinOpsProvider is rejected at admission

FinOpsProvider's rules are validation rules on the CRD, evaluated by the API server. No webhook is involved, so they apply on every install whether or not the webhooks are registered and whether or not the manager pod is running.

| Rejection message | Cause | Remedy |
| --- | --- | --- |
| `FinOpsProvider must be named 'default' (singleton).` | The kind is cluster-scoped and a singleton. | Name the object `default`. |
| `At least one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set` | The spec sets none of the four option blocks. | Set the one that matches the environment. |
| `Exactly one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set` | The spec sets more than one. | Remove all but one. |

An admitted FinOpsProvider carries no conditions and its reconciler writes no status, so there is nothing to read back on the object to confirm it worked. Check the OpenCost side instead: the pricing ConfigMap in the operator's namespace, or the OpenCost custom resource on the Multi Tenant Operator path.

## Related

- [Status conditions](reference/status-conditions.md) for the exhaustive table behind every reason named here.
- [Webhooks](reference/webhooks.md) for which rejections come from admission and which from the CRDs.
