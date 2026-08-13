# Webhooks

Two validating admission webhooks ship with the operator, one for `Offering` and one for `Subscription`. Both are served by the controller manager process on container port 9443, both are validating rather than mutating, and both declare `failurePolicy: Fail` and `sideEffects: None`, so a request the webhook cannot answer is refused rather than admitted.

The reason this page exists is that the webhook layer is much smaller than it looks from the outside. Rejections readers usually attribute to a webhook, immutability above all, come from validation rules compiled into the CRDs and evaluated by the API server itself. Getting the two apart matters when you are working out why a request was refused, and matters more when you are deciding whether disabling the webhooks is safe.

## The two registrations

| Webhook | Path | Resource | Operations |
| --- | --- | --- | --- |
| `voffering-v1alpha1.kb.io` | `/validate-finops-stakater-com-v1alpha1-offering` | `offerings` | CREATE, UPDATE, DELETE |
| `vsubscription-v1alpha1.kb.io` | `/validate-finops-stakater-com-v1alpha1-subscription` | `subscriptions` | CREATE |

Both point at the `finops-operator-webhook-service` Service in the release namespace, on port 443 forwarding to 9443, and both accept only `v1` admission review versions.

Note the asymmetry in the last column. The Subscription webhook is registered for creates alone, so no update or delete of a Subscription is ever sent to it, whatever the Go methods behind that path happen to contain.

## What the Offering webhook rejects

On create it runs one check: cycles in the requirement graph. First it compares each `compatibility.requiredOfferings` entry against the Offering itself, on name and namespace, and rejects a direct self-reference. Then it walks the graph depth-first, following each requirement to the Offering it names and on to that Offering's own requirements, and rejects the request if the walk re-enters an object already on the current path. The rejection names the cycle it found. A requirement that points at an Offering which does not exist is skipped during the walk, because a missing object cannot close a cycle.

Nothing else about the spec is checked on create. A required Offering that is absent, or present but not ready, is admitted on purpose: the Offering reconciler holds it not ready with `RequiredOfferingNotFound` or `RequiredOfferingNotReady` until the situation resolves, which lets you apply a set of interdependent Offerings in any order.

On update the webhook does nothing at all. `ValidateUpdate` returns without inspecting either the old or the new object, so the UPDATE registration costs a round trip and never rejects anything. Offering spec immutability, the rule people expect this to be, is a CRD rule.

On delete it checks for dependents, and refuses while any exist: a Subscription whose `offeringRef` names this Offering, or another Offering that lists this one in its `compatibility.requiredOfferings`. The error names them.

!!! warning
    Both dependency checks list with a `status.ready` field selector, so only dependents that are currently ready are counted. A Subscription that never activated, or that has already deactivated, does not block the delete, and deleting the Offering out from under it strands that Subscription's finalizer. [Uninstalling](../getting-started/uninstalling.md) gives a teardown order that avoids this.

## What the Subscription webhook rejects

Exactly one thing, on create only: a Subscription that names itself.

It rejects `spec.parent.subscriptionRef` pointing at the Subscription's own name and namespace, with the reason `CircularDependencyDetected`. It also rejects `spec.lifecycle.targetRef` pointing at the Subscription itself, with the reason `TargetIsSelfReference`, matching on all four of name, namespace, `kind: Subscription`, and the `finops.stakater.com/v1alpha1` API version, so a `targetRef` at some other kind of the same name is fine.

That is the whole webhook. It does not resolve `offeringRef`, does not look at the parent, does not evaluate compatibility coverage, and does not check that a `targetRef` exists. All four of those are activation gates the Subscription reconciler re-runs continuously, which is what lets a Subscription be created before the objects it depends on. [The four activation gates](../concepts/subscription.md#the-four-activation-gates) sets them out.

## Where the rest of the validation lives

Everything below is enforced by the API server from validation rules on the CRDs, not by either webhook. That means it applies on every install, whether or not the webhooks are registered, and whether or not the manager pod is running.

| Rule | Kind | Rejection message |
| --- | --- | --- |
| The object must be named `default` | FinOpsProvider | `FinOpsProvider must be named 'default' (singleton).` |
| At least one provider option must be set | FinOpsProvider | `At least one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set` |
| Exactly one provider option must be set | FinOpsProvider | `Exactly one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set` |
| `spec` cannot change after creation | Offering | `offering spec is immutable` |
| `spec.offeringRef` cannot change | Subscription | `offeringRef is immutable; create a new Subscription instead` |
| `spec.parent` cannot change, including whether it is present at all | Subscription | `parent is immutable; create a new Subscription instead` |
| A margin cannot set both `absoluteMicros` and `factorMilli` | Offering | `absoluteMicros and factorMilli are mutually exclusive — set only one` |
| `absoluteMicros` cannot be negative | Offering | `absoluteMicros must be >= 0` |
| `factorMilli` cannot be negative | Offering | `factorMilli must be >= 0` |
| `period` must be a duration for `ActivatedAt` alignment and a plain integer otherwise | Offering | `period must be a Go duration (e.g. '1h') for ActivatedAt alignment, or a plain integer for boundary alignments` |
| A `usageSources` entry must set at least one of `resourceType`, `name`, or `namespace` | Subscription | `at least one of resourceType, name, or namespace must be set` |

Ordinary schema validation carries the rest, in the same place and with the same reach. `namespace` is required on every `offeringRef`, every `requiredOfferings` entry, and every `parent.subscriptionRef`, with a minimum length of one so an empty string is refused as well as an absent field. A fixed set of accepted values bounds `meters[].name`, `tickAlignment`, `onParentDeactivate`, `usageSources[].resourceType`, and the `CostJob` type; numeric bounds reject a `priceMicros` below 1. None of this is webhook work.

## The split, in one line each

| Layer | Fires on | Enforces |
| --- | --- | --- |
| Offering webhook | Offering CREATE | Self-reference and cycles in `compatibility.requiredOfferings` |
| Offering webhook | Offering DELETE | Refusal while a ready Subscription or a ready dependent Offering references it |
| Offering webhook | Offering UPDATE | Nothing |
| Subscription webhook | Subscription CREATE | A Subscription naming itself as its parent or as its own `lifecycle.targetRef` |
| CRD validation rules | Every write, on every kind | Singleton naming, how many provider options may be set, immutability, field formats, mutual exclusions, bounds |
| Reconcilers | Continuously, after admission | Offering readiness, parent state, compatibility coverage, target existence |

The third row is the one to remember. There is no webhook rule that only applies to updates, which is why immutability had to be CEL and why a mutation you expect to be rejected is rejected by the API server with a CEL message rather than by anything the operator wrote.

Reasons written onto conditions tell you which layer produced a failure: [status conditions](status-conditions.md) marks the ones that come from admission, and [admission validation and CRD validation](../concepts/architecture.md#admission-validation-and-crd-validation) is the same split from the architecture side.

## Certificates

The webhook server needs TLS, and the CA has to reach the API server. With `certManager.enabled` on, which is the default, the chart creates a self-signed `Issuer`, a `Certificate` for `finops-operator-webhook-service` in the release namespace covering both the `.svc` and cluster-domain DNS names, and stores the result in the Secret `webhook-server-cert`. That Secret is mounted read-only into the manager at `/tmp/k8s-webhook-server/serving-certs`, which is what `--webhook-cert-path` points at, so the manager starts a watcher on the directory and picks up a renewal without restarting. The `ValidatingWebhookConfiguration` carries the `cert-manager.io/inject-ca-from` annotation, which is how the API server gets the CA bundle.

On OpenShift, setting `openshift.enabled` annotates the webhook Service with `service.beta.openshift.io/serving-cert-secret-name` and switches the CA annotation to `service.beta.openshift.io/inject-cabundle`, filling the same Secret from the platform instead. Use one mechanism or the other, not both. To supply your own material, mount it and set `--webhook-cert-path`, `--webhook-cert-name`, and `--webhook-cert-key` accordingly.

## Turning webhooks off

Setting `ENABLE_WEBHOOKS` to exactly the string `"false"` on the manager container skips both registrations at startup. Anything else, including an empty value and `"False"`, leaves them on. The chart has no named key for it, so it goes in `controllerManager.manager.extraEnv`.

What you lose is short: the cycle check on Offering create, the dependent check on Offering delete, and the self-reference check on Subscription create. Everything in the CRD table above still applies, because the API server evaluates it without the operator's help. Cycles and self-references are still caught afterwards, on the objects rather than at the request: the Offering reconciler reports `CircularDependencyDetected`, and a Subscription that names itself is held not ready with the same reason. The one check with no continuous equivalent is the deletion guard, so an Offering can be deleted from under its dependents.

!!! warning
    Disabling the registrations is not enough on its own. The `ValidatingWebhookConfiguration` is a separate object, it stays in place, and both of its entries use `failurePolicy: Fail`, so the API server will refuse every Offering write and every Subscription create once there is nothing serving those paths. Delete the configuration in the same change.

## Related

- [Status conditions](status-conditions.md) for the reasons the reconcilers write once an object is admitted.
- [Offering](../concepts/offering.md#deletion) and [Subscription](../concepts/subscription.md) for the behaviour behind each check.
- [Configuration reference](configuration.md) for `ENABLE_WEBHOOKS`, the certificate flags, and the chart's webhook values.
