# Deactivate a subscription

Deactivation is how a billing relationship ends, and a Subscription only ever ends once. `kubectl delete` starts that wind-down rather than finishing it: the object stays in the cluster, held by a finalizer, until the collection job is satisfied that its billing is settled. This guide deletes an active Subscription, reads what each stage of the wind-down wrote, prices the closing tick, and works through the gates that decide when the object is finally released. It is for a platform engineer ending a subscriber's terms, or for whoever is investigating a Subscription that will not go away.

## Prerequisites

- An active `Subscription` and `kubectl` delete permission in its namespace, which is `finops-operator-system` throughout this guide.
- A [`SubscriptionChargeCollection` CostJob](collect-cost-data.md) scheduled and running. It is the only thing that releases the finalizer, so a cluster without one never finishes a deletion.
- The bound Offering's `pricing.subscriptionFee` to hand. Its `period`, `tickAlignment` and `minPeriods` decide both what the final tick costs and how long the wind-down takes.

!!! warning
    There is no undo. `status.deactivatedAt` is written once and never cleared, and a Subscription carrying it is not re-validated on any later reconcile, so it does not come back if the Offering recovers or the parent returns. Resuming billing for the same subscriber means a new Subscription, which opens a new billing epoch with its own `activatedAt`. [Deactivation is terminal](../concepts/subscription.md#deactivation-is-terminal) explains why the charge history requires that.

## Step 1: Delete the Subscription

```sh
kubectl delete subscription acme-platform-base -n finops-operator-system --wait=false
```

The reconciler puts `subscriptions.finops.stakater.com/finalizer` on every Subscription the first time it sees one, so this call records a `metadata.deletionTimestamp` and stops there. Kubernetes will not remove the object while the finalizer is present, which is what gives the operator time to close out the billing.

`--wait=false` is worth the habit. Without it `kubectl` blocks until the object is actually gone, and that is the end of step 4 rather than the end of this command, which under a `minPeriods` guard can be a long way off.

## Step 2: Read what the delete path wrote

On its next reconcile the controller takes the delete branch and writes the deactivation and the cleanup marker in the same pass:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system \
  -o jsonpath='{.status.ready}{"  "}{.status.deactivatedAt}{"\n"}{range .status.conditions[*]}{.type}{"  "}{.status}{"  "}{.reason}{"\n"}{end}'
```

```text
False  2026-04-01T13:42:07Z
Ready  False  ValidationSucceeded
Active  False  MarkedForDeletion
CostsResolved  True  FromDB
Deleting  False  WaitingForCollectionJob
```

| Condition | Status | Reason | What it tells you |
| --- | --- | --- | --- |
| `Active` | `False` | `MarkedForDeletion` | The relationship has ended and a delete is what ended it. This is the condition that names the cause |
| `Deleting` | `False` | `WaitingForCollectionJob` | The finalizer is still on. `False` here means cleanup is not permitted yet, not that nothing is being deleted |
| `Ready` | `False` | `ValidationSucceeded` | Nothing about the cause. Deactivation always sets `Ready` false with this reason |

Read `Active` and not `Ready`. `Ready=False` with reason `ValidationSucceeded` is the same thing you would see on a Subscription that is perfectly healthy in every other respect, so the reason says nothing; the table in [tell a waiting Subscription from a finished one](subscribe-to-offering.md#step-5-tell-a-waiting-subscription-from-a-finished-one) separates the states that `READY False` covers.

`status.deactivatedAt` is the clock the reconciler read at the instant it applied that patch. It is not the `deletionTimestamp`, it is not rounded, and it is not a tick boundary. Like `activatedAt` it is written once, so a later reconcile of the same object leaves it alone.

Children are not deactivated by this write. Ending this Subscription is a change in compatibility coverage, which re-enqueues each child so it resolves its own `lifecycle.onParentDeactivate` policy, and a family therefore unwinds one level at a time rather than in one sweep. [Compose subscriptions](compose-subscriptions.md) covers the policies and what an orphan does instead.

## Step 3: Price the closing tick

The fee calculation does not bill to the instant in `status.deactivatedAt`. It snaps that value forward to the next tick boundary on the Subscription's alignment and clamps both ends of every window to the snapped time, so the closing tick is charged as a whole tick and windows opening after it contribute nothing. There is never a partial final tick.

Take the terms from the [quick start](../getting-started/quick-start.md), `tickAlignment: ActivatedAt` with `period: 1h` and `priceMicros: 40000000`, and an activation at `09:00:00Z`. Boundaries then fall on every hour from `10:00`. The deactivation above at `13:42:07Z` snaps forward to `14:00:00Z`:

- Ticks charged from activation: the boundaries at `10:00`, `11:00`, `12:00`, `13:00` and `14:00`, so five.
- Total fee: `40000000 × 5 = 200000000`, that is 200.00.
- Elapsed life: `09:00:00Z` to `13:42:07Z` is 4 hours 42 minutes 7 seconds, so the last 17 minutes 53 seconds of the fifth tick are billed and were not used.

The gap widens with the period. Under a period of a day or a month, a deactivation shortly after a boundary pays for a tick that ran for a small fraction of its length, which is the trade-off for never issuing a fractional closing charge. [Charging the final tick](../concepts/billing-model.md#charging-the-final-tick) has the arithmetic for the wider cases.

!!! note
    The snapped time exists only inside that calculation and is never written back, so do not expect `status.deactivatedAt` to move to `14:00:00Z`. Reconciling a status timestamp against a charge means applying the snap yourself. A deactivation that already lands exactly on a boundary is not pushed forward to the next one.

## Step 4: Wait out the finalizer gates

Only a `SubscriptionChargeCollection` run takes the finalizer off, and only when all four of these hold on the same run:

| Gate | Passes when |
| --- | --- |
| Deactivated | `status.deactivatedAt` is set. A Subscription whose `deletionTimestamp` has landed but whose deactivation patch has not yet is held, because its final billable instant is not known |
| `minPeriods` | The Offering sets no `minPeriods`, or at least that many tick boundaries have fallen since `status.activatedAt` |
| Charges settled | The hour containing `status.deactivatedAt` is already covered by this run's finalized pass, which reaches the run's own scheduled hour for a fee-only Subscription and the cluster's allocation boundary for one that bills usage |
| No errors | Nothing was recorded against this Subscription during the run. A failed Offering read, a failed charge write or a failed status update all hold the finalizer so the next run retries |

The `minPeriods` gate is a cleanup guard and nothing more. Billing carries on tick by tick while it waits, under exactly the rules of step 3, and no shortfall is added for the ticks between the deactivation and the count being reached: a Subscription deleted early is simply never charged for the ticks that did not run. It is counted with the same tick counter the fee uses, so it inherits the alignment and it is measured from `activatedAt` rather than from the delete. `minPeriods: 24` against `HourBoundary` with `period: "1"` means 24 hourly boundaries since activation, so a Subscription that had already been running a month clears that gate on the first run after its deletion. [Decide whether to hold deleted Subscriptions](define-offering.md#step-4-decide-whether-to-hold-deleted-subscriptions) covers choosing the value.

Each run says which gate held the object. Find the most recent Job the CronJob created and read its log:

```sh
kubectl get jobs -n finops-operator-system --sort-by=.metadata.creationTimestamp
kubectl logs -n finops-operator-system job/subscription-charge-collection-cronjob-29618280
```

```text
MinPeriods not yet satisfied, keeping finalizer
```

```text
Charges not finalized through deactivation hour, keeping finalizer
```

```text
Removed finalizer for deleted subscription
```

The CostJob's own status stays empty for this job type, so the pod log is where the wind-down is visible. Holding the finalizer is not an error and the run still exits cleanly; only a real failure makes the Job retry.

## Step 5: Confirm the object is gone

Once the finalizer comes off, Kubernetes removes the object without further help:

```sh
kubectl get subscription acme-platform-base -n finops-operator-system
```

```text
Error from server (NotFound): subscriptions.finops.stakater.com "acme-platform-base" not found
```

`status.costs` goes with the object, so read the closing figures before the run that releases it if you want them. The charge rows do not go: they live in `subscription_charges` keyed by the Subscription's UID rather than by its name, and nothing in the deletion path removes them. [Read subscription costs](read-subscription-costs.md) covers both.

## Deactivation without a deletion

Three other things end a Subscription, and none of them involves the deletion machinery: a parent that deactivated or disappeared while the policy is `Deactivate`, compatibility coverage that went away, and a `lifecycle.targetRef` whose object was deleted. Each writes the same pair as step 2, `Ready=False` with reason `ValidationSucceeded` and `Active=False`, and the `Active` reason names the cause instead: `ParentDeactivated`, `CompatibilityRequirementNotMet` or `TargetNotFound`. The clamp in step 3 applies identically.

What is missing is the rest. There is no `deletionTimestamp`, no `Deleting` condition, and nothing to release, so the object stays in the cluster indefinitely reporting `READY False` and accruing nothing. Cleaning it up afterwards is a normal delete and runs steps 1 to 5, with one difference: `status.deactivatedAt` keeps the instant of the original deactivation, so nothing is charged twice, and only the `Active` condition's reason is rewritten to `MarkedForDeletion`. [The four activation gates](../concepts/subscription.md#the-four-activation-gates) sets out which gates can end an active Subscription and which only hold it.

## When the finalizer will not release

A Subscription that sits at `WaitingForCollectionJob` for longer than its `minPeriods` explains has one of a short list of causes:

- **No collection job.** Check `kubectl get costjob -A` for a CostJob of type `SubscriptionChargeCollection`. Without one, nothing ever evaluates the gates.
- **The collection job is failing.** Its CostJob status stays empty, so compare Job completions and read the pod log, as in step 4. A run that exits non-zero leaves every gate unevaluated for the Subscriptions it failed on.
- **`minPeriods` has not elapsed.** Count boundaries from `status.activatedAt` under the Offering's alignment. The value cannot be lowered, because an Offering's spec is immutable; a shorter guard is a new Offering for future Subscriptions, which does nothing for this one.
- **The Offering is gone.** Each run re-reads the Subscription's Offering, and a failed read is an error recorded against the Subscription, which holds the finalizer. The next run gets past that read only if an Offering exists again at the same name and namespace.

!!! warning
    Do not delete an Offering while a Subscription that references it is still winding down. The Offering's own delete guard counts only Subscriptions that are ready, and a deleting Subscription is not ready, so the guard does not stop you and the Subscription is stranded afterwards. [Uninstalling](../getting-started/uninstalling.md) gives the order to tear resources down in.

Editing the finalizer off by hand is a last resort rather than a remedy. It removes the object immediately, along with any closing charges that had not yet been written, and leaves the charge history for that Subscription short of its final hours.

## Related guides

- [Subscribe to an offering](subscribe-to-offering.md) for the activation this is the counterpart to, and for telling a waiting Subscription from a finished one.
- [Read subscription costs](read-subscription-costs.md) for the closing figures and where they are stored afterwards.
- [Compose subscriptions](compose-subscriptions.md) for what happens to children and orphans when a parent ends.
- [Billing model](../concepts/billing-model.md) for the snap, the tick arithmetic, and the guard on a deleted Subscription.
- [Subscription](../concepts/subscription.md) for the finalizer, the status fields, and why deactivation cannot be reversed.
