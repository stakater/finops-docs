# On Kubernetes

The Helm chart is the installation method for every Kubernetes distribution, and the only one that exposes the operator's configuration surface. It installs the five CRDs, the controller Deployment, the FinOps Gateway Deployment, the RBAC and Services they need, and, when cert-manager is enabled, the certificate objects that make the webhooks serve. It can also create a starter `PriceBook` and `CostJob`, and, if you have no database or OpenCost yet, bring those up for you.

The chart is published as an OCI artifact at `oci://ghcr.io/stakater/public/charts/finops-operator`. Read the value surface of whatever version you are about to install with `helm show values` against that reference, and see [installation overview](overview.md) for what the dependencies are and why they are needed.

## Create the namespace and dependency Secrets

The controller mounts two Secrets by name and neither key reference is optional, so the pod will not start until both exist. Create them before installing, in the namespace the release will use.

```sh
kubectl create namespace finops-operator-system

kubectl create secret generic finops-operator-postgres-config \
  --namespace finops-operator-system \
  --from-literal=POSTGRES_CONNECTION_STRING='postgres://finops:PASSWORD@postgres.example.svc:5432/finops?sslmode=require'

kubectl create secret generic finops-operator-opencost-config \
  --namespace finops-operator-system \
  --from-literal=OPENCOST_CONNECTION_STRING='http://opencost.opencost.svc:9003'
```

The names above are the chart's defaults, `secrets.postgres` and `secrets.opencost`. If you keep your Secrets under different names, set those two values instead of renaming your Secrets; the chart uses whatever you give it to build the `secretKeyRef`. The key names inside each Secret are fixed and cannot be changed.

The chart's third Secret value, `secrets.prometheus`, defaults to `finops-operator-prometheus-config` but is not referenced by any template, so on this path no Prometheus Secret is needed.

## Install the chart

cert-manager has to be present before the install, because the chart creates an `Issuer` and two `Certificate` objects and the controller mounts the Secret one of them produces.

```sh
helm install finops-operator oci://ghcr.io/stakater/public/charts/finops-operator \
  --namespace finops-operator-system
```

On OpenShift, install the same chart with the platform issuing the webhook certificate instead:

```sh
helm install finops-operator oci://ghcr.io/stakater/public/charts/finops-operator \
  --namespace finops-operator-system \
  --set openshift.enabled=true \
  --set certManager.enabled=false
```

## What the chart installs

| Object | Name | Notes |
| --- | --- | --- |
| CRDs | `costjobs`, `finopsproviders`, `offerings`, `pricebooks`, `subscriptions` | Applied from the chart's `crds/` directory; `finopsproviders` is cluster-scoped, the rest are namespace-scoped |
| Deployment | `finops-operator-controller-manager` | Runs the five reconcilers and the webhook server; probes on `:8081`, webhooks on `:9443` |
| Deployment | `finops-operator-finops-gateway-gateway` | Runs the FinOps Gateway against the same database, listening on `:8080` |
| Services | `finops-operator-webhook-service`, `finops-operator-controller-manager-metrics-service`, `finops-operator-finops-gateway-service` | Ports 443 to 9443, 8443, and 8080 |
| `ValidatingWebhookConfiguration` | `finops-operator-validating-webhook-configuration` | The `Offering` and `Subscription` webhooks, both `failurePolicy: Fail` |
| RBAC | `finops-operator-controller-manager` ServiceAccount, 18 ClusterRoles, 2 ClusterRoleBindings, and a leader-election Role and RoleBinding | Includes the per-resource admin, editor, and viewer roles |
| cert-manager objects | `finops-operator-selfsigned-issuer`, `finops-operator-serving-cert`, `finops-operator-metrics-certs` | Only when `certManager.enabled` is true |

The last three names, and the webhook configuration's, are built from the chart's full name, which is the release name when it already contains the chart name. Installing under a release name of `finops-operator`, as above, gives exactly the names shown.

Nothing cost-related exists yet. No `FinOpsProvider`, no `PriceBook`, and no `CostJob` is created unless you ask for one, so a default install reconciles nothing until you author those resources. The [quick start](../quick-start.md) walks through the first set.

## A production `values.yaml`

Every key below exists in the chart's `values.yaml`; the comments give the shipped defaults so you can see what you are changing.

```yaml
# Secret names the controller builds its secretKeyRef entries from.
secrets:
  postgres: finops-operator-postgres-config   # default
  opencost: finops-operator-opencost-config   # default

controllerManager:
  replicas: 1                                 # default 1
  manager:
    env:
      # The OpenCost Deployment the PriceBook reconciler restarts on a pricing change.
      opencostDeploymentName: finops-operator-opencost           # default
      opencostDeploymentNamespace: finops-operator-system        # default
      mtoEnabled: "false"                                        # default "false"
    # The chart sets no resource requests or limits; add them here if your
    # cluster enforces quotas. extraEnv is also where ENABLE_WEBHOOKS goes.
    extraEnv: []                                                 # default []

# Webhook serving certificates. Leave certManager.enabled on for plain
# Kubernetes; on OpenShift, swap to the platform's serving certificates.
certManager:
  enabled: true                               # default true
openshift:
  enabled: false                              # default false

# Registry credentials, propagated to both Deployments and to the generated
# CronJob pods through the IMAGE_PULL_SECRETS environment variable.
imagePullSecrets: []                          # default []

# Optional starter CostJob resources. Both default to false, and both default
# to an interval of 1m, which fires the generated CronJob every minute.
costJob:
  enabled: true                               # default false; ResourceCostCollection
  interval: 1h                                # default 1m
chargeCollectionJob:
  enabled: true                               # default false; SubscriptionChargeCollection
  interval: 1h                                # default 1m

# Optional starter PriceBook, created in the release namespace as
# <release-name>-default-pricing. Empty rates are omitted from the object.
priceBook:
  enabled: true                               # default false
  currency: USD                               # default USD
  valuationMode: currency                     # default currency
  rates:
    cpuHour: "0.031"                          # default ""
    ramGbHour: "0.004"                        # default ""
    pvGbHour: "0.00012"                       # default ""
    gpuHour: "1.80"                           # default ""
    networkGiB: "0.09"                        # default ""
    spotCPUHour: ""                           # default ""
    spotRAMGbHour: ""                         # default ""
```

Install or upgrade with the file:

```sh
helm upgrade --install finops-operator oci://ghcr.io/stakater/public/charts/finops-operator \
  --namespace finops-operator-system \
  -f values.yaml
```

Two things about the starter resources are worth knowing before you turn them on. The chart's default interval for both `CostJob` objects is `1m`, which the operator maps to the cron expression `* * * * *`, so an unchanged default runs collection every minute; pick an interval that matches how often you want the work done. And the chart marks the `PriceBook` it creates with `finops.stakater.com/active: "true"` as a **label**, while the operator reads that marker as an **annotation**, so the chart's marker does not pin the book.

!!! warning
    Because the marker lands as a label, a chart-created `PriceBook` only becomes active by falling through to the operator's election, which is what happens while it is the only book in the cluster. Add the annotation yourself if you want it pinned. [PriceBook](../../concepts/pricebook.md) covers all three selection tiers, and also why a namespace that runs a `ResourceCostCollection` `CostJob` should hold only one book.

The chart exposes more than this: the gateway's own image, replicas, auth and CORS settings, an optional `Ingress` for it, the metrics and webhook Service types, and `kubernetesClusterDomain`. [Configuration reference](../../reference/configuration.md) lists the full surface.

## Optional: let the chart provision the dependencies

Setting `mdoDependencies.enabled=true` pulls in the `mto-dependencies-operator` dependency chart and creates `Postgres`, `OpenCost`, and `Prometheus` custom resources in the release namespace, along with the PostgreSQL and OpenCost Secrets pointing at the in-cluster services it brings up. In that mode you do not create the Secrets yourself.

```yaml
mdoDependencies:
  enabled: true                               # default false
  postgres:
    username: finopsuser                      # default finopsuser
    password: CHANGE-ME                       # default is a placeholder
    postgresPassword: CHANGE-ME               # default is a placeholder
    database: finopsdb                        # default finopsdb
```

The connection string the chart generates from these values uses `sslmode=disable`, and the shipped passwords are placeholders. Use this to get a cluster working, not to run a production database.

## Verify the install

Check that both Deployments report their replicas available:

```sh
kubectl get deployment -n finops-operator-system
```

Then read the controller's logs:

```sh
kubectl logs -n finops-operator-system deployment/finops-operator-controller-manager
```

A clean start logs `starting manager` after it has set up the five reconcilers and both webhooks. Two failure shapes are common, and `kubectl describe pod` distinguishes them. A pod in `CreateContainerConfigError` means one of the two Secrets, or one of their keys, is missing. A pod stuck in `ContainerCreating` with a `FailedMount` event for `webhook-certs` means the `webhook-server-cert` Secret does not exist, because the container mounts it unconditionally and nothing has issued the certificate.

Confirm the CRDs and the webhook registration landed:

```sh
kubectl get crd | grep finops.stakater.com
kubectl get validatingwebhookconfiguration | grep finops-operator
```

## Upgrading

Upgrade with the same reference and your values file:

```sh
helm upgrade finops-operator oci://ghcr.io/stakater/public/charts/finops-operator \
  --namespace finops-operator-system \
  -f values.yaml
```

Helm applies files in a chart's `crds/` directory on install but not on upgrade, so a chart version that changes a CRD needs those five definitions applied yourself. Pin the chart version with `--version` so an upgrade is a deliberate change rather than whatever the registry currently tags as latest.

## Uninstalling

`helm uninstall` leaves the CRDs and every object made from them in place. [Uninstalling](../uninstalling.md) covers the ordering that matters, including the finalizers on `Subscription` objects.

## Next

- [Quick start](../quick-start.md) to define pricing, an Offering, and a Subscription that accrues charges.
- [Architecture](../../concepts/architecture.md) for what the controller and the generated CronJobs do.
- [Configuration reference](../../reference/configuration.md) for every chart value, environment variable, and flag.
