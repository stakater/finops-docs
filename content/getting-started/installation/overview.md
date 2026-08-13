# Installation overview

The FinOps Operator installs as one controller Deployment, a second Deployment running the FinOps Gateway against the same database, and five custom resource definitions. It does not work in isolation: it reads allocation data from OpenCost and keeps prices, allocation rows, and charges in PostgreSQL. Installing it therefore means placing those workloads in a cluster and pointing the controller at those two dependencies through Secrets it expects by name. [Architecture](../../concepts/architecture.md) describes what the running processes do once they are there.

Both installation methods put the operator in the `finops-operator-system` namespace, and the rest of the documentation assumes that namespace.

## Choosing an installation method

On OpenShift, use the Operator Lifecycle Manager. The project builds an operator bundle and a catalog image from the same manifests the chart is generated from, so an administrator adds a `CatalogSource`, subscribes to the package, and lets OLM own upgrades. That path installs a fixed configuration: the `ClusterServiceVersion` hard-codes the Secret names and the OpenCost Deployment it looks for, so there is nothing equivalent to chart values to override. See [on OpenShift](openshift.md).

Everywhere else, use the Helm chart. It exposes the whole configuration surface as values, can optionally create a starter `PriceBook` and `CostJob` on install, and can bring up PostgreSQL, OpenCost, and Prometheus for you. The chart also runs on OpenShift, where setting `openshift.enabled=true` swaps cert-manager for the platform's service serving certificates. See [on Kubernetes](kubernetes.md).

## Prerequisites

| Prerequisite | Needed for | How the operator finds it |
| --- | --- | --- |
| A cluster and `cluster-admin` | Both methods | Cluster-scoped `ClusterRole` objects, a cluster-scoped `FinOpsProvider` CRD, and four namespace-scoped CRDs |
| cert-manager | The Helm path, unless you turn the webhooks off | `certManager.enabled`, which gates an `Issuer` and two `Certificate` objects |
| PostgreSQL | Both methods | Secret `finops-operator-postgres-config`, key `POSTGRES_CONNECTION_STRING` |
| OpenCost | Both methods | Secret `finops-operator-opencost-config`, key `OPENCOST_CONNECTION_STRING` |
| Prometheus | OpenCost, not the operator | Secret `finops-operator-prometheus-config`, key `PROMETHEUS_URL`, referenced only on the OLM path |
| Multi Tenant Operator | Optional integration | `MTO_ENABLED`, set from `controllerManager.manager.env.mtoEnabled` |

### Cluster access and tooling

You need `cluster-admin` or an equivalent role. Both installation methods create cluster-scoped objects: eighteen `ClusterRole` objects, two `ClusterRoleBinding` objects, and the five CRDs, one of which, `FinOpsProvider`, is itself cluster-scoped. You also need `kubectl` or `oc`, and the Helm CLI for the chart.

The bundle's `ClusterServiceVersion` declares `minKubeVersion: 1.21.0`. The Helm chart declares no `kubeVersion` constraint at all, so nothing in the chart stops an install on an older cluster.

### Webhook serving certificates

Both `Offering` and `Subscription` have validating webhooks, served on container port 9443 by the controller process itself. The manager is started with `--webhook-cert-path=/tmp/k8s-webhook-server/serving-certs` and mounts the `webhook-server-cert` Secret there, and something has to produce that Secret.

With `certManager.enabled=true`, the chart's default, the chart creates a self-signed `Issuer`, a `Certificate` for `finops-operator-webhook-service` whose `secretName` is `webhook-server-cert`, a second `Certificate` for the metrics service, and a `cert-manager.io/inject-ca-from` annotation on the `ValidatingWebhookConfiguration` so the CA bundle is injected for you. cert-manager must already be installed in the cluster; the chart does not install it.

With `openshift.enabled=true`, the webhook Service is annotated with `service.beta.openshift.io/serving-cert-secret-name: webhook-server-cert` and the webhook configuration with `service.beta.openshift.io/inject-cabundle: "true"`, so OpenShift issues and rotates the certificate instead.

The escape hatch is `ENABLE_WEBHOOKS=false`, which you set through `controllerManager.manager.extraEnv`. The manager registers both webhooks unless that variable is exactly `false`, so setting it starts the controller with no webhook server. What it costs is real: both webhook configurations use `failurePolicy: Fail`, so leaving them registered while the server is gone makes every `Offering` and `Subscription` write fail, and removing them gives up the checks that only run at admission. Those are dependency cycle and self-reference detection on `Offering` create, the block on deleting an `Offering` that other objects still require, and the self-reference checks on `Subscription` create. CRD validation rules still apply, and the reconcilers still enforce readiness and coverage continuously, but a cyclic `Offering` graph becomes something you discover from status rather than something that is refused.

!!! warning
    Turning the webhooks off is a development convenience. If you do it, remove the `ValidatingWebhookConfiguration` too, otherwise admission blocks on a server that is not listening.

### PostgreSQL

The operator needs a reachable PostgreSQL database. It reads the connection string from the `POSTGRES_CONNECTION_STRING` key of a Secret whose name comes from `secrets.postgres`, default `finops-operator-postgres-config`, in the release namespace. The FinOps Gateway Deployment reads the same key from the same Secret.

The reference is a plain `secretKeyRef` with no `optional: true`, so the Secret and the key have to exist before the pod can start. Whichever process connects first applies any outstanding schema migrations, so there is no separate migration step.

### OpenCost

The operator needs a reachable OpenCost instance, and it needs to know both where to query it and which Deployment to restart. The query URL comes from the `OPENCOST_CONNECTION_STRING` key of the Secret named by `secrets.opencost`, default `finops-operator-opencost-config`. This reference is also non-optional. The Deployment to restart comes from `controllerManager.manager.env.opencostDeploymentName` and `opencostDeploymentNamespace`, which default to `finops-operator-opencost` in `finops-operator-system`.

OpenCost matters at two moments. The PriceBook reconciler renders the active book into a custom pricing document and restarts that Deployment when the document changes, and the allocation-collecting job reads hourly allocation rows from the OpenCost API. Outside Multi Tenant Operator mode the `FinOpsProvider` reconciler deliberately does nothing to the OpenCost Deployment, leaving both the document and the restart to the PriceBook reconciler, so OpenCost is a prerequisite for pricing and collection regardless of whether you create a `FinOpsProvider` at all.

### Prometheus

Prometheus is a dependency of OpenCost, which needs it as a metrics backend, rather than of the operator. No process in the operator reads a Prometheus URL: `PROMETHEUS_URL` appears nowhere in the operator's code.

The Helm chart reflects that. Its `secrets.prometheus` value, default `finops-operator-prometheus-config`, is not referenced by any chart template, so on the Helm path no Prometheus Secret is required.

!!! note
    The OLM path differs. The `ClusterServiceVersion` still wires `PROMETHEUS_URL` from the `PROMETHEUS_URL` key of `finops-operator-prometheus-config`, and that reference is not optional, so the Secret must exist for the pod to start even though nothing reads the value.

### Multi Tenant Operator

Multi Tenant Operator integration is optional and off by default. `controllerManager.manager.env.mtoEnabled` defaults to `"false"` and becomes the `MTO_ENABLED` environment variable, which the operator treats as enabled only when it is exactly `"true"`.

Enabling it changes one path. The `FinOpsProvider` reconciler patches the `OpenCost` custom resource in the `dependencies.tenantoperator.stakater.com` API group and restarts OpenCost only if that patch changed something, which requires Multi Tenant Operator's dependency CRDs to be present. With the flag off, that reconciler is a deliberate no-op against the OpenCost Deployment. Everything else, pricing, collection, offerings, and subscriptions, behaves the same either way.

## Letting the chart provision the dependencies

If you do not already run PostgreSQL, OpenCost, and Prometheus, the chart can create them. Setting `mdoDependencies.enabled=true` pulls in the `mto-dependencies-operator` dependency chart and creates `Postgres`, `OpenCost`, and `Prometheus` custom resources in the release namespace, plus the two Secrets the operator reads, wired to the in-cluster service names. The generated PostgreSQL connection string uses `sslmode=disable` and the credentials in `mdoDependencies.postgres`, which ship as placeholder passwords in the chart's defaults. Treat it as a way to get a working cluster quickly, not as a production database. [On Kubernetes](kubernetes.md) covers the values.

## Next

- [On OpenShift](openshift.md) to install through the Operator Lifecycle Manager.
- [On Kubernetes](kubernetes.md) to install with Helm.
- [Quick start](../quick-start.md) to go from a fresh install to a Subscription accruing charges.
- [Configuration reference](../../reference/configuration.md) for the full set of values, environment variables, and flags.
