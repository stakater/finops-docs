# Security model

The FinOps Operator sits between three parties that would otherwise not talk to each other: a PostgreSQL database that holds every charge it has ever computed, an OpenCost instance it configures and queries, and the platform and application teams who author the five custom resources. This page describes what it holds, what it reaches, and where the boundaries between those parties actually fall. It is deliberately explicit about what the operator does not protect.

## Credentials the operator holds

The manager container starts with two values it did not compute and cannot function without. `POSTGRES_CONNECTION_STRING` comes from the Secret named by `secrets.postgres`, under a key of the same name, and `OPENCOST_CONNECTION_STRING` comes from the Secret named by `secrets.opencost`. Both are wired as non-optional `secretKeyRef` entries, so a missing Secret or a missing key leaves the pod unable to start rather than running degraded.

The PostgreSQL connection string is the most sensitive thing in the installation. It is a full DSN, with credentials in it, and it grants whatever that database user grants: every allocation row, every charge row, and the mirrored copy of every Offering and Subscription version. Nothing narrows it per namespace or per tenant. Treat read access to that Secret as equivalent to read access to all recorded cost history.

It does not stay in one place. When the CostJob reconciler builds a CronJob it also creates a Secret named `<costjob-name>-costjob-secret`, in the CostJob's own namespace, carrying the same `POSTGRES_CONNECTION_STRING` value copied out of the manager's environment. The generated pod reads the DSN from there rather than from the release namespace.

!!! warning
    A CostJob authored in namespace `X` causes the database DSN to be written into a Secret in namespace `X`. Anyone who can read Secrets in `X` can then read the database directly. Keep CostJobs in namespaces whose Secret readers you would trust with the database, which in practice means the operator's own namespace.

The FinOps Gateway that the chart deploys alongside the operator reads the same key from the same Secret, as `PG_CONNECTION_STRING`. Its `ENABLE_AUTH` value defaults to `"false"` and `finopsGatewayIngress.enabled` can put it behind an Ingress, so an install that turns the Ingress on without turning authentication on publishes an unauthenticated reader of the cost database. That combination is worth checking before you expose it.

One more credential-shaped field deserves care. `cloudIntegrationSecret` on a `FinOpsProvider`'s provider option is a plain string on the object's spec, not a reference the operator resolves. In Multi Tenant Operator bundled mode the reconciler copies it verbatim into the `OpenCost` custom resource, and it logs the value at info level on the way through. Anything you put there is readable by anyone who can read the `FinOpsProvider` or the operator's logs.

`secrets.prometheus` is the odd one out: no chart template references it, and the string `PROMETHEUS_URL` appears nowhere in the operator's code. It is mandatory only on the Operator Lifecycle Manager path, where the bundle's ClusterServiceVersion wires it non-optionally even though nothing consumes the value. See [`PROMETHEUS_URL`](configuration.md#prometheus_url).

## What the operator reaches

Outbound traffic from the manager is short. It talks to the Kubernetes API through its ServiceAccount, and to exactly two things outside the cluster's control plane.

OpenCost is reached without transport security. The client is built from `OPENCOST_CONNECTION_STRING` and issues unauthenticated `GET` requests to `/allocation/compute` with the window, step, resolution, and aggregation as query parameters. There is no token, no client certificate, and no TLS unless the URL you supply asks for it. On a default install that URL is a cluster-internal Service address, so the traffic never leaves the cluster, and the security of the exchange rests entirely on who else can reach that Service.

PostgreSQL is reached with the DSN as given. The operator sets no TLS options of its own, so whether the connection is encrypted is a property of the connection string you supply. If you let the chart provision the bundled dependencies, the generated string uses `sslmode=disable`; that path exists to get a cluster running, not to run production on.

Prometheus is not in this list, and that is not an omission. The operator makes no Prometheus request of any kind. Prometheus is a dependency of OpenCost: OpenCost queries it, the operator queries OpenCost, and no cost figure the operator writes comes from a query it issued to Prometheus itself.

## Admission traffic and its certificates

Both validating webhooks are served by the manager process on container port 9443, fronted by the `finops-operator-webhook-service` Service on port 443. When `certManager.enabled` is on, the chart creates a self-signed `Issuer` and a `Certificate` whose key material lands in the Secret `webhook-server-cert`, mounts that Secret read-only at `/tmp/k8s-webhook-server/serving-certs`, and annotates the `ValidatingWebhookConfiguration` with `cert-manager.io/inject-ca-from` so the API server learns the CA. The `--webhook-cert-path` argument points the manager at the same directory, which starts a certificate watcher and picks up a renewal without a restart. On OpenShift, `openshift.enabled` swaps both halves for the platform's service serving certificates; use one or the other, never both.

Setting `ENABLE_WEBHOOKS` to exactly `"false"` skips both registrations at startup. The `ValidatingWebhookConfiguration` is a separate object and stays where it is, and both of its entries carry `failurePolicy: Fail`, so the API server refuses the requests it can no longer get an answer for. Disabling webhooks therefore means removing the configuration too, and accepting that the checks in [webhooks](webhooks.md) no longer run.

## Who can create what

`FinOpsProvider` is cluster-scoped and must be named `default`, so there is exactly one of them and it belongs to whoever administers the cluster. It decides which provider the whole installation prices against and whether custom pricing applies, and its effects land on OpenCost rather than on any one namespace. Granting write access to it is a cluster-admin decision, and the role that does so only takes effect through a ClusterRoleBinding.

`PriceBook` is namespace-scoped, but the active book is elected across the entire cluster, so a book created in any namespace can win the active slot and change the rates every Offering resolves against. Namespace boundaries do not contain pricing.

`Offering` and `Subscription` are the two kinds ordinary teams author, and both are namespace-scoped, so ordinary namespace RBAC decides who can define a priced thing and who can start being billed for one. The [user-facing roles](rbac.md#roles-for-your-users) exist for exactly this.

There is one consequence of that split worth stating plainly. A reference does not require permission on its target. Creating a Subscription in namespace `A` that points at an Offering in namespace `B` needs no access to `B` at all: the operator resolves the reference with its own ClusterRole, not with the identity that made the request. An Offering's owner therefore cannot stop other namespaces from subscribing to it, and, because a ready Subscription blocks the Offering's deletion, a subscriber in another namespace can hold that Offering open.

What the design does guarantee is that the reference is never ambiguous. `namespace` is required on every `offeringRef`, every `requiredOfferings` entry, and every `parent.subscriptionRef`, with a minimum length of one, and it is never defaulted from the referring object. Reading a Subscription tells you precisely which objects it binds, in which namespaces, without knowing where it was authored. Cross-namespace reach is always visible in the spec.

## What the collection pods can reach

The pods the operator generates are the widest part of the installation. Their template names `finops-operator-controller-manager` as its ServiceAccount, so a collection run carries the whole manager ClusterRole, including its write access to Secrets, ConfigMaps, Deployments, CronJobs, Roles, and RoleBindings, none of which the job code uses. They also hold the database DSN and the OpenCost URL, and they reach both. Anything that can influence what runs in those pods, such as write access to the generated CronJob, inherits all of that.

Hardening differs between the two workloads. The manager pod runs with `runAsNonRoot: true` and `seccompProfile.type: RuntimeDefault`, and its container drops all capabilities and disallows privilege escalation. The generated CronJob's pod template sets no security context at all, at either level; it sets CPU and memory requests and limits, which `spec.resources` on the `CostJob` can override, and nothing else. If your namespaces enforce Pod Security Standards, the job pods depend on whatever the namespace applies rather than on anything the operator asks for.

## Out of scope

These are not weaknesses to work around. They are the edges of what the operator claims to do.

- **Charge data at rest is not encrypted by the operator.** Allocations, charges, prices, and the mirrored resource history are written to PostgreSQL as ordinary columns. There is no field-level encryption, no hashing, and no tenant-level key separation anywhere in the schema. At-rest protection is entirely your database's job.
- **There is no audit trail of who changed pricing.** The operator writes no Kubernetes events, and the mirror it keeps in PostgreSQL records object versions rather than the identity that submitted them. Attribution comes from your API server audit log.
- **Cost data is not partitioned by tenant.** `CLUSTER_ID` scopes rows to a cluster; nothing scopes them to a namespace or a subscriber inside one. Every reader of the database sees every subscriber's charges.
- **No NetworkPolicy is installed.** Neither install path restricts who can reach port 9443 or the metrics port. Confining them is left to you.
- **The operator does not verify what OpenCost tells it.** Allocation figures are taken as reported, so a compromised or wrongly configured OpenCost produces wrong charges rather than an error.

## Related

- [RBAC](rbac.md) for the exact permission set behind these boundaries.
- [Webhooks](webhooks.md) for what admission does and does not reject.
- [Configuration reference](configuration.md) for the Secret names, variables, and flags this page refers to.
