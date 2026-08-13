# Uninstalling

Removing the FinOps Operator is a sequence, not a single command. Two of the five types carry finalizers, and the things that release them, the controller and the `SubscriptionChargeCollection` CostJob, are themselves part of what you are removing. Take them away too early and objects are left behind that nothing can finish deleting.

Work from the outside in: the objects that reference something first, the things they reference next, and the operator itself last.

| Stage | What you remove | Why it comes here |
| --- | --- | --- |
| 1 | Subscriptions | Their finalizer is removed only by a collection run, so the CostJob and the controller must still be running |
| 2 | Offerings | Deletion is refused while a ready Subscription references the Offering, and a deleting Subscription still reads its Offering on every run |
| 3 | CostJobs, PriceBooks, FinOpsProvider | Nothing references them any more, and none of them carries a finalizer |
| 4 | The operator itself, as a Helm release or as OLM objects | Once no custom resources are left, nothing needs the controller or the webhooks |
| 5 | The CRDs | Neither install path removes them, and a CRD deletion cannot complete while an object still holds a finalizer |

The commands below use `finops-operator-system`. Subscriptions, Offerings, PriceBooks, and CostJobs are namespace-scoped, so repeat each of their deletes in every namespace that holds them. `FinOpsProvider` is cluster-scoped.

## 1. Delete the Subscriptions

Deleting a Subscription starts a wind-down rather than removing the object. The controller deactivates it immediately and records `Deleting=False` with reason `WaitingForCollectionJob`, and the finalizer `subscriptions.finops.stakater.com/finalizer` stays on until a `SubscriptionChargeCollection` run finds three things true: the Subscription is deactivated, at least `minPeriods` ticks have elapsed since `status.activatedAt` where its Offering sets one, and charges are finalized through its last billable hour. A run that records any error against the Subscription also holds the finalizer.

```sh
kubectl delete subscription --all -n finops-operator-system
```

Then leave the CostJob running and wait. `minPeriods` only holds the object: billing carries on normally during the wait and no shortfall is charged for ticks that never ran, so waiting costs nothing but time. The two fields that decide how much time read from the Offering and from each Subscription:

```sh
kubectl get offering -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,PERIOD:.spec.pricing.subscriptionFee.period,MINPERIODS:.spec.pricing.subscriptionFee.minPeriods'

kubectl get subscription -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,ACTIVATED:.status.activatedAt,DEACTIVATED:.status.deactivatedAt'
```

An Offering with no `minPeriods` still leaves one wait behind, because the last billable hour has to be covered first. For a fee-only Subscription that is the next run after the hour it deactivated in; for one that bills usage it is the next run whose allocation data has reached that hour. The alternative is the manual escape hatch below, which forfeits the charge records for those hours.

Confirm the stage is done when the list is empty:

```sh
kubectl get subscription -A
```

If a Subscription is still there, the last collection run said why. Find the most recent job and read it:

```sh
kubectl get jobs -n finops-operator-system
kubectl logs -n finops-operator-system job/<job-name>
```

`MinPeriods not yet satisfied, keeping finalizer` and `Charges not finalized through deactivation hour, keeping finalizer` both mean the wait is proceeding as it should. An error naming the Subscription means the run failed for it, and the next scheduled run retries.

## 2. Delete the Offerings

With the Subscriptions gone, nothing points at the Offerings.

```sh
kubectl delete offering --all -n finops-operator-system
```

The check runs at admission, in the Offering's validating webhook, so a blocked delete fails the command outright rather than leaving the object terminating. `still referenced by subscriptions` names the Subscriptions that hold it; `still required by dependent resources` names the Offerings that list it under `compatibility.requiredOfferings`. Delete those first and repeat. The reconciler records the same finding as `Deleting=False` with reason `DependentSubscriptionsExist` or `DependentOfferingsExist`.

!!! warning
    Both checks select only Subscriptions and Offerings whose `status.ready` is `True`, and deactivation sets a Subscription's `ready` to false. A Subscription that is deactivated and still deleting therefore does not block the delete, even though every collection run still fetches its Offering to price the remaining hours and to evaluate `minPeriods`. Delete the Offering while that is going on and the run cannot fetch it: the run records the fetch failure against that Subscription, skips finalizer removal for it, and does the same on every run after that. The Subscription never finishes deleting. Always confirm `kubectl get subscription -A` is empty before this stage, not merely that the deletes were accepted.

Confirm:

```sh
kubectl get offering -A
```

## 3. Delete the CostJobs, PriceBooks, and FinOpsProvider

None of these three carries a finalizer, so each is gone as soon as the API server accepts the delete. Deleting a CostJob also removes the CronJob it generated, which is owned by it.

```sh
kubectl delete costjob --all -n finops-operator-system
kubectl delete pricebook --all -n finops-operator-system
kubectl delete finopsprovider default
```

Confirm, including that no generated CronJob survived:

```sh
kubectl get costjob,pricebook -A
kubectl get finopsprovider
kubectl get cronjob -n finops-operator-system
```

## 4. Remove the operator

Doing this before the earlier stages is what strands objects. Without the controller nothing adds or removes a finalizer, and without the CostJob no Subscription is ever released; meanwhile a webhook configuration still registered against a server that has gone away fails admission for every `Offering` and `Subscription` write, because both webhooks use `failurePolicy: Fail`.

Which commands you run depends on how the operator was installed. Neither path removes the CRDs, so stage 5 follows either way.

### The Helm path

```sh
helm uninstall finops-operator -n finops-operator-system
```

This removes both Deployments, the Services, the RBAC objects, the `ValidatingWebhookConfiguration`, and the cert-manager objects. It does not remove the CRDs, because Helm leaves the contents of a chart's `crds/` directory in place.

### The OLM path

On the [OpenShift install](installation/openshift.md) there is no release to uninstall. Remove the four OLM objects in the reverse of the order that page creates them. The OLM `Subscription` goes first, because it is what keeps the operator installed: delete the `ClusterServiceVersion` while the `Subscription` is still there and OLM resolves a new `InstallPlan` and puts the operator straight back.

```sh
oc delete subscriptions.operators.coreos.com finops-operator-subscription -n finops-operator-system

oc get csv -n finops-operator-system
oc delete clusterserviceversion finops-operator.v0.1.16 -n finops-operator-system

oc delete operatorgroup finops-operator-operatorgroup -n finops-operator-system
oc delete catalogsource finops-operator-catalog -n openshift-marketplace
```

The fully qualified `subscriptions.operators.coreos.com` is deliberate. Until stage 5 removes the CRDs, `subscription` is an ambiguous short name on this cluster: it matches the OLM type as well as the operator's own.

Substitute the version you installed in the `ClusterServiceVersion` name, which the `oc get csv` above prints; `finops-operator.v0.1.16` is only an example. Deleting the `ClusterServiceVersion` is what removes both Deployments, the Services, the RBAC objects, and the webhook configurations OLM generated from the bundle's `webhookdefinitions`, along with the serving certificate OLM issued for them.

The `CatalogSource` lives in whichever namespace you created it in, and the OLM `Subscription`'s `sourceNamespace` names it: `openshift-marketplace` if you followed the OpenShift page, `olm` if you applied the project's own manifest unchanged. Delete the `finops-operator-pull` image pull secret from that namespace too if nothing else uses it. Leaving the `CatalogSource` in place is harmless, but it keeps the package listed on **OperatorHub** so it can be reinstalled from the console.

### Confirm the namespace is empty

```sh
kubectl get all -n finops-operator-system
```

Delete the namespace as well if nothing else uses it. On the OLM path this also takes the three dependency Secrets with it.

## 5. Remove the CRDs

Removing a CRD removes every object made from it, so do this only once the earlier stages are confirmed empty. Neither Helm nor OLM removes them, so this stage is the same on both paths.

```sh
kubectl get crd | grep finops.stakater.com

kubectl delete crd \
  subscriptions.finops.stakater.com \
  offerings.finops.stakater.com \
  costjobs.finops.stakater.com \
  pricebooks.finops.stakater.com \
  finopsproviders.finops.stakater.com
```

Confirm the group is gone:

```sh
kubectl get crd | grep finops.stakater.com
```

A CRD deletion that hangs means one of its objects still holds a finalizer, and at this point the controller that would remove it no longer exists. Remove the finalizer by hand, as below, and the deletion completes.

## When a Subscription will not finish deleting

A Subscription stuck with a deletion timestamp is held by its finalizer, and there are only two ways out.

If the cause is a missing Offering, the ordering trap in stage 2, put the Offering back. Recreate it with the same name, namespace, and spec, and the next collection run fetches it, prices the outstanding hours, and releases the finalizer as it would have originally. This is the recovery that keeps the billing record intact, and it is the reason to keep an Offering until its last Subscription has finished deleting.

Otherwise, or if there is no collection job left to run, remove the finalizer yourself:

```sh
kubectl patch subscription <name> -n <namespace> \
  --type=merge \
  -p '{"metadata":{"finalizers":[]}}'
```

!!! warning
    This deletes the object immediately and gives up everything the finalizer was protecting. The `minPeriods` guard is bypassed, and the charges for the Subscription's final hours, up to and including the hour it deactivated in, are never computed or written, so the billing record for that Subscription ends short. Do it when you are decommissioning the cluster, not to hurry a live one along.

## Related

- [Deactivate a subscription](../guides/deactivate-a-subscription.md) for ending one Subscription rather than all of them.
- [Subscription](../concepts/subscription.md) and [Offering](../concepts/offering.md) for the finalizers and the deletion checks in full.
- [Status conditions](../reference/status-conditions.md) for the `Deleting` condition and its reasons.
