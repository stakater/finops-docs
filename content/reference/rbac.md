# RBAC

Everything the FinOps Operator does to your cluster goes through a single ServiceAccount, `finops-operator-controller-manager`, created in the release namespace. Three bindings attach to it: a ClusterRoleBinding to `finops-operator-manager-role`, which carries all of the operator's real authority; a RoleBinding in the release namespace to `finops-operator-leader-election-role`; and a ClusterRoleBinding to `finops-operator-metrics-auth-role`, used only by the filter in front of the metrics endpoint.

The pod template of every CronJob the operator generates names that same ServiceAccount, so a collection run holds exactly the permissions the manager holds. There is no separate, narrower identity for the jobs.

## The manager ClusterRole

`finops-operator-manager-role` is generated from the `+kubebuilder:rbac` markers on the five reconcilers, so it is the union of what they declare rather than a hand-tuned list. It contains nine rules.

| API group | Resources | Verbs |
| --- | --- | --- |
| `finops.stakater.com` | `costjobs`, `finopsproviders`, `offerings`, `pricebooks`, `subscriptions` | create, delete, get, list, patch, update, watch |
| `finops.stakater.com` | `costjobs/status`, `finopsproviders/status`, `offerings/status`, `pricebooks/status`, `subscriptions/status` | get, patch, update |
| `finops.stakater.com` | `costjobs/finalizers`, `offerings/finalizers`, `pricebooks/finalizers`, `subscriptions/finalizers` | update |
| `""` (core) | `configmaps`, `secrets`, `serviceaccounts` | create, delete, get, list, patch, update, watch |
| `""` (core) | `namespaces` | get, list, watch |
| `apps` | `deployments` | create, delete, get, list, patch, update, watch |
| `batch` | `cronjobs` | create, delete, get, list, patch, update, watch |
| `dependencies.tenantoperator.stakater.com` | `opencosts` | get, list, patch |
| `rbac.authorization.k8s.io` | `roles`, `rolebindings` | create, delete, get, list, patch, update, watch |

## Why each rule is there

The three `finops.stakater.com` rules cover the operator reconciling its own API. The first watches and updates the five kinds, the second writes the conditions and status fields described in [status conditions](status-conditions.md), and the third manages the finalizers that hold an Offering or a Subscription open while dependents remain or hours are still to be charged. Status and finalizer writes go through their own API endpoints, so they are their own rules, and splitting them keeps the object rule from implying more than it grants.

`configmaps` is how the active PriceBook reaches OpenCost. The PriceBook reconciler renders the winning book's rates into a `default.json` document and applies it to the `finops-operator-custom-pricing-configs` ConfigMap in the OpenCost deployment's namespace with a create-or-patch, which is why the rule carries `create` as well as `patch`. [How the active PriceBook reaches OpenCost](../concepts/architecture.md#how-the-active-pricebook-reaches-opencost) covers the mechanism.

`secrets` is a write permission rather than a read one, and this is the rule most often misread. The operator never reads the PostgreSQL, OpenCost, or Prometheus dependency Secrets through the API: the kubelet resolves those `secretKeyRef` entries when it starts the manager pod, so their values arrive as environment variables and need no RBAC at all. What the operator does with this rule is create and update one Secret per CostJob, named `<costjob-name>-costjob-secret` in the CostJob's own namespace, holding the `POSTGRES_CONNECTION_STRING` key that the generated pod reads. [Credentials the operator holds](security-model.md#credentials-the-operator-holds) covers what that copy means.

`deployments` exists so the operator can restart OpenCost after a pricing change. The restart is a patch of the OpenCost Deployment's pod template annotation `finops.stakater.com/restartedAt`, applied only when the pricing document actually changed. Reads and that patch are all the code performs; `create` and `delete` come from a broad marker on the FinOpsProvider reconciler and nothing exercises them.

`cronjobs` is how a `CostJob` becomes work. The CostJob reconciler creates or updates `<costjob-name>-cronjob` in the CostJob's namespace and sets itself as controller owner, so the CronJob is garbage-collected with its CostJob. There is deliberately no grant on `batch/jobs`: the Kubernetes CronJob controller creates the Jobs, and the operator neither reads nor manages the Jobs or the pods that follow from them. To inspect a run you go to the Jobs yourself.

`namespaces` is read-only, and narrower in purpose than it looks. The Subscription reconciler fetches the Namespace object of each Subscription it reconciles so it can capture that namespace's labels and mirror them alongside the Subscription into PostgreSQL. Nothing else in the operator reads a Namespace.

`opencosts` in the `dependencies.tenantoperator.stakater.com` group applies only when `MTO_ENABLED` is exactly `"true"`. In that mode the FinOpsProvider reconciler patches the `OpenCost` custom resource to carry the cloud integration secret and to switch custom pricing on. Outside that mode the rule is unused, and if the CRD is absent the group never resolves.

`roles` and `rolebindings`, together with `serviceaccounts` in the core rule, come from markers on the CostJob reconciler and are not used. No code path in the operator creates, reads, or modifies a Role, a RoleBinding, or a ServiceAccount. If your cluster policy objects to an operator holding RBAC write permissions, these are the rules to trim first, and removing them changes no behaviour on either install path.

## What is cluster-scoped, and why

`FinOpsProvider` is declared with `scope=Cluster`, so it has no namespace and can only be granted through a ClusterRole. `Offering`, `Subscription`, `PriceBook`, and `CostJob` are namespace-scoped, but the operator watches all four across every namespace rather than in one, so their rules also have to be cluster-wide. Reading `namespaces` is cluster-scoped by definition.

That leaves one namespace-scoped Role, `finops-operator-leader-election-role`, bound in the release namespace.

| API group | Resources | Verbs |
| --- | --- | --- |
| `coordination.k8s.io` | `leases` | get, list, watch, create, update, patch, delete |
| `""` (core) | `configmaps` | get, list, watch, create, update, patch, delete |
| `""` (core) | `events` | create, patch |

The Lease is what `--leader-elect` acquires, under the election ID `4f7ee504.stakater.com`. The chart passes that flag, so a chart install holds a Lease in the release namespace and any extra replicas stand by. The `configmaps` and `events` entries come with the election Role as it is generated, rather than being something the operator drives: no reconciler registers an event recorder, so the operator emits no Kubernetes events of its own and conditions are the only signal it writes.

## Metrics roles

Two more ClusterRoles ship for the metrics endpoint, and only one of them is bound.

`finops-operator-metrics-auth-role` grants `create` on `tokenreviews` in `authentication.k8s.io` and on `subjectaccessreviews` in `authorization.k8s.io`, and it is bound to the manager's ServiceAccount. The manager needs it because `--metrics-secure` defaults to true, which puts an authentication and authorization filter in front of the endpoint; the filter validates a scraper's bearer token and checks its access by calling those two APIs on the operator's own behalf.

`finops-operator-metrics-reader` grants `get` on the non-resource URL `/metrics` and ships with no binding at all. It is the role you bind to whatever identity scrapes the endpoint. [Metrics](metrics.md) covers the endpoint itself.

## Roles for your users

The chart also installs fifteen unbound ClusterRoles, three for each of the five kinds, named `finops-operator-<kind>-admin-role`, `-editor-role`, and `-viewer-role`. The operator does not use them; they exist so you can delegate access without writing rules yourself.

| Role | On the resource | On its status |
| --- | --- | --- |
| admin | `*` | get |
| editor | create, delete, get, list, patch, update, watch | get |
| viewer | get, list, watch | get |

Because they are ClusterRoles, a RoleBinding scopes one to a single namespace while a ClusterRoleBinding grants it everywhere. For the four namespace-scoped kinds a RoleBinding is usually what you want:

```sh
kubectl create rolebinding acme-subscription-editor \
  --clusterrole=finops-operator-subscription-editor-role \
  --user=alice \
  --namespace=acme-billing
```

`FinOpsProvider` is cluster-scoped, so `finops-operator-finopsprovider-admin-role` only takes effect through a ClusterRoleBinding. Granting it is granting control over how the whole cluster is priced. [Who can create what](security-model.md#who-can-create-what) explains why the two scopes are worth treating differently.

## Related

- [Security model](security-model.md) for the trust boundaries these permissions draw.
- [Configuration reference](configuration.md) for the flags and Secret names this page refers to.
- [Metrics](metrics.md) for the endpoint the metrics roles protect.
