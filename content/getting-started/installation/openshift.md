# On OpenShift

The FinOps Operator ships an operator bundle and a catalog index, so on OpenShift you install it through the Operator Lifecycle Manager rather than with Helm. Those artifacts are published to the project's own registry, so the install starts by adding a `CatalogSource` that points at the catalog image. Once that catalog is reachable, the rest is the standard OLM sequence: an `OperatorGroup`, a `Subscription`, then an `InstallPlan` that OLM resolves into a `ClusterServiceVersion`.

!!! note
    This procedure installs from the project's own catalog and does not depend on the operator appearing in the catalogs OpenShift ships with. Once you have added the catalog below, the package shows up on the console's **OperatorHub** page under that catalog's display name, and you can install it from there instead of applying the manifests by hand.

## What the project ships for OLM

| Artifact | Value |
| --- | --- |
| Package name | `finops-operator` |
| Bundle format | `registry+v1`, manifests in `manifests/`, metadata in `metadata/` |
| Channel declared by the bundle | `alpha` |
| `ClusterServiceVersion` name | `finops-operator.v<version>`, for example `finops-operator.v0.1.16` |
| Supported install mode | `AllNamespaces` only |
| Catalog image | `ghcr.io/stakater/finops-operator-catalog:v<version>` |
| Install namespace | `finops-operator-system` |

The bundle carries the same five CRDs, RBAC, and controller Deployment the Helm chart does, plus a set of `alm-examples` the console uses to fill in sample resources. It declares the two validating webhooks as `webhookdefinitions` on the `ClusterServiceVersion` rather than shipping a `ValidatingWebhookConfiguration` and a cert-manager `Certificate`, both `ValidatingAdmissionWebhook` entries targeting container port 443 and target port 9443 on the `finops-operator-controller-manager` Deployment. Webhook serving certificates are therefore the responsibility of OLM on this path, and cert-manager is not a prerequisite.

The `Subscription` manifest checked into the project uses channel `alpha`, matching the bundle's own annotation. The file-based catalog under the project's `catalog/` directory declares a single channel named `preview` and makes it the default, so the channel you need depends on which catalog image you point at. Read it off the cluster rather than assuming. The `PackageManifest` only exists once the `CatalogSource` below is added and reporting `READY`, so this is a check to come back to after that step:

```sh
oc get packagemanifest finops-operator -o jsonpath='{.status.channels[*].name}{"\n"}'
```

## Before you start

- `cluster-admin` on the cluster, and `oc` configured against it.
- A pull secret for the catalog and bundle images. Neither image can be pulled anonymously, so OLM needs credentials in the namespace holding the `CatalogSource`.
- The dependency Secrets. The `ClusterServiceVersion` wires the controller's environment from three Secrets by hard-coded name, all with non-optional key references, so the pod cannot start until each exists in `finops-operator-system`.

| Secret | Key | Purpose |
| --- | --- | --- |
| `finops-operator-postgres-config` | `POSTGRES_CONNECTION_STRING` | The PostgreSQL DSN |
| `finops-operator-opencost-config` | `OPENCOST_CONNECTION_STRING` | The OpenCost API endpoint |
| `finops-operator-prometheus-config` | `PROMETHEUS_URL` | Referenced but never read by the operator |

The OLM path offers no equivalent of chart values, so these names are not configurable. Create the namespace and the Secrets first:

```sh
oc create namespace finops-operator-system

oc create secret generic finops-operator-postgres-config \
  --namespace finops-operator-system \
  --from-literal=POSTGRES_CONNECTION_STRING='postgres://finops:PASSWORD@postgres.example.svc:5432/finops?sslmode=require'

oc create secret generic finops-operator-opencost-config \
  --namespace finops-operator-system \
  --from-literal=OPENCOST_CONNECTION_STRING='http://opencost.opencost.svc:9003'

oc create secret generic finops-operator-prometheus-config \
  --namespace finops-operator-system \
  --from-literal=PROMETHEUS_URL='http://prometheus-server.monitoring.svc'
```

See [installation overview](overview.md) for what each dependency is for and why the Prometheus Secret has to exist despite being unused.

## Add the catalog source

Put the `CatalogSource` where your `Subscription` will point at it. On OpenShift that is conventionally `openshift-marketplace`; the manifest in the project targets `olm`, because it was written for a local kind cluster. Whichever you choose, the `Subscription`'s `sourceNamespace` has to match.

```sh
oc create secret docker-registry finops-operator-pull \
  --docker-server=ghcr.io \
  --docker-username='<username>' \
  --docker-password='<token>' \
  --namespace openshift-marketplace

oc apply -f - <<'EOF'
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: finops-operator-catalog
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: ghcr.io/stakater/finops-operator-catalog:v0.1.16
  displayName: FinOps Operator Catalog
  publisher: stakater
  secrets:
    - finops-operator-pull
EOF
```

A healthy catalog reports `READY` and runs a pod serving its gRPC endpoint:

```sh
oc get catalogsource finops-operator-catalog -n openshift-marketplace \
  -o jsonpath='{.status.connectionState.lastObservedState}{"\n"}'
oc get packagemanifest finops-operator
```

If the catalog pod stays in `ImagePullBackOff`, the pull secret is missing or lacks access to the image. Nothing downstream resolves until the `PackageManifest` appears.

## Create an OperatorGroup

The `ClusterServiceVersion` supports only the `AllNamespaces` install mode, so the `OperatorGroup` must watch all namespaces. An empty `targetNamespaces` list is how that is expressed.

```sh
oc apply -f - <<'EOF'
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: finops-operator-operatorgroup
  namespace: finops-operator-system
spec:
  targetNamespaces: []
EOF
```

An `OperatorGroup` scoped to a single namespace leaves the `Subscription` unresolvable, because no install mode the bundle supports matches it.

## Subscribe to the operator

```sh
oc apply -f - <<'EOF'
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: finops-operator-subscription
  namespace: finops-operator-system
spec:
  channel: alpha
  name: finops-operator
  source: finops-operator-catalog
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
EOF
```

`installPlanApproval: Automatic` is what the project's own manifest uses and lets OLM apply new versions from the channel as they arrive. Use `Manual` where you want to review each upgrade, and add `startingCSV: finops-operator.v<version>` to pin the version the first `InstallPlan` resolves to.

## Check the InstallPlan and the CSV

OLM creates an `InstallPlan` in the operator namespace and then a `ClusterServiceVersion`. Both carry the state you need:

```sh
oc get installplan -n finops-operator-system
oc get csv -n finops-operator-system
```

An `InstallPlan` in `Complete` and a `ClusterServiceVersion` phase of `Succeeded` mean OLM applied the bundle. With `installPlanApproval: Manual`, the plan sits at `RequiresApproval` until you patch `spec.approved` to `true`.

A `Succeeded` phase says the manifests were applied, not that the controller is serving. Check the workload it created:

```sh
oc get deployment -n finops-operator-system
oc logs -n finops-operator-system deployment/finops-operator-controller-manager
```

The bundle creates two Deployments: `finops-operator-controller-manager`, and `finops-operator-finops-gateway-gateway`, which runs the FinOps Gateway image and connects to the same PostgreSQL database and listens on port 8080. A controller pod stuck in `CreateContainerConfigError` almost always means one of the three Secrets, or one of their keys, is missing. Reconciliation only begins once the manager reports it is running; the resources it then acts on are the ones you create.

The bundle installs no `PriceBook` and no `CostJob`, so nothing is priced or collected until you author them. The [quick start](../quick-start.md) walks through that, and [PriceBook](../../concepts/pricebook.md) and [CostJob](../../concepts/costjob.md) explain the resources.

## Installing with Helm on OpenShift instead

Nothing forces the OLM path on OpenShift. The Helm chart runs there too, and it is the only way to reach the configuration surface, which includes the Secret names, the OpenCost Deployment to restart, the optional starter `PriceBook` and `CostJob`, and Multi Tenant Operator mode. On OpenShift, set `openshift.enabled=true` and `certManager.enabled=false` so the platform issues the webhook serving certificate instead of cert-manager. See [on Kubernetes](kubernetes.md).

## Next

- [Quick start](../quick-start.md) to get from a running operator to a Subscription accruing charges.
- [Architecture](../../concepts/architecture.md) for what the installed Deployment and the generated CronJobs do.
- [Uninstalling](../uninstalling.md#the-olm-path) to remove the operator and its OLM objects.
