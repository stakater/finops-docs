# Configuration reference

This page documents the external configuration surface of the FinOps Operator: the Helm chart values, environment variables on the manager and its scheduled jobs, and command-line flags. Together, these options let you integrate the operator with your cluster's infrastructure and control its runtime behavior.

## Helm values

The following table lists top-level Helm chart keys. Use dot notation to override values during chart installation.

| Key | Default | Purpose |
|---|---|---|
| `controllerManager.manager.args` | (flags for metrics, leader-elect, health probe, webhook cert) | Command-line arguments passed to the manager. |
| `controllerManager.manager.env.opencostDeploymentName` | `finops-operator-opencost` | Name of the Deployment that the operator restarts when pricing changes. |
| `controllerManager.manager.env.opencostDeploymentNamespace` | `finops-operator-system` | Namespace containing the OpenCost Deployment and pricing ConfigMap. |
| `controllerManager.manager.image.repository` | — | Container image repository. |
| `controllerManager.manager.image.tag` | — | Container image tag. |
| `controllerManager.replicas` | — | Number of manager Deployment replicas. |
| `controllerManager.podSecurityContext` | — | Pod-level security context. |
| `controllerManager.manager.containerSecurityContext` | — | Container-level security context. |
| `imagePullSecrets` | — | Names of Secrets for pulling images from private registries. |
| `kubernetesClusterDomain` | `cluster.local` | Kubernetes cluster domain for internal DNS names. |
| `metricsService.*` | (`HTTPS` on `:8443`) | Service configuration for the metrics endpoint. |
| `webhookService.*` | (`HTTPS` on `:443`) | Service configuration for the webhook endpoint. |
| `certManager.enabled` | `true` | Whether to use cert-manager for webhook certificates. Set to `false` only if you manage certificates manually. |
| `openshift.enabled` | `false` | Enable OpenShift-specific configuration. |
| `secrets.prometheus` | — | Name of the Secret containing Prometheus credentials. |
| `secrets.postgres` | — | Name of the Secret containing PostgreSQL credentials. |
| `secrets.opencost` | — | Name of the Secret containing OpenCost credentials. |
| `costJob.enabled` | `false` | Create a default `ResourceCostCollection` CostJob on install. |
| `costJob.interval` | — | Schedule interval for the default CostJob. |
| `costJob.<timeout>` (7 keys) | — | Optional timeout overrides matching the seven `CostJob` spec timeout fields. See [CostJob](./crds/costjob.md) for the field list and defaults. |
| `chargeCollectionJob.enabled` | `false` | Create a default `SubscriptionChargeCollection` CostJob on install. |
| `chargeCollectionJob.interval` | — | Schedule interval for the default charge collection job. |
| `chargeCollectionJob.<timeout>` (7 keys) | — | Optional timeout overrides matching the seven `CostJob` spec timeout fields. See [CostJob](./crds/costjob.md) for the field list and defaults. |
| `priceBook.enabled` | `false` | Create a default `PriceBook` on install. |
| `priceBook.currency` | — | ISO 4217 currency code (e.g. `USD`). |
| `priceBook.valuationMode` | — | Pricing valuation mode. |
| `priceBook.rates.*` | — | Rate definitions for pricing. |
| `finopsGatewayGateway` | — | FinOps Gateway Deployment configuration. |
| `finopsGatewayService` | — | FinOps Gateway Service configuration. |
| `finopsGatewayIngress` | — | FinOps Gateway Ingress configuration. |

The three `finopsGateway*` values enable an optional FinOps Gateway deployment — a separate component for UI/API access. These values ship the Gateway's Gateway API route, Service, and Ingress; configuring the Gateway itself is out of scope for this page.

## Manager environment variables

The manager binary reads environment variables on startup. Some are required; others are optional with sensible defaults. Scheduled jobs use a distinct set of timeout variables that can be overridden per-job.

### Required (controller mode)

These variables must be set for the manager to operate in controller mode.

| Variable | Purpose |
|---|---|
| `PROMETHEUS_URL` | Prometheus endpoint used for supplementary metrics. |
| `POSTGRES_CONNECTION_STRING` | PostgreSQL DSN for storing cost and charge data. |
| `OPENCOST_CONNECTION_STRING` | OpenCost service URL (e.g., `http://finops-operator-opencost.finops-operator-system.svc.cluster.local:9003`). |
| `OPENCOST_DEPLOYMENT_NAME` | Deployment name that the operator restarts when pricing changes. |
| `OPENCOST_DEPLOYMENT_NAMESPACE` | Namespace containing the OpenCost Deployment and pricing ConfigMap. |

### Optional

These variables have sensible defaults and are only needed in special configurations.

| Variable | Default | Purpose |
|---|---|---|
| `ENABLE_WEBHOOKS` | `true` | Set to `"false"` to disable webhook registration (local development only). |

### Scheduled-job environment variables

The operator's scheduled `CostJob` pods consume these environment variables. Each can be overridden on individual `CostJob` specifications via corresponding fields in the CR. If not overridden, the values below are used as defaults.

| Variable | Default | CostJob field |
|---|---|---|
| `DATABASE_INIT_TIMEOUT` | `2m` | `databaseInitTimeout` |
| `K8S_OPERATION_TIMEOUT` | `1m` | `kubernetesOperationTimeout` |
| `OPENCOST_FETCH_TIMEOUT` | `2m` | `openCostFetchTimeout` |
| `DATABASE_INSERT_TIMEOUT` | `3m` | `databaseInsertTimeout` |
| `DATABASE_VIEWS_REFRESH_TIMEOUT` | `5m` | `databaseViewsRefreshTimeout` |
| `STATUS_UPDATE_TIMEOUT` | `1m` | `statusUpdateTimeout` |
| `HTTP_CLIENT_TIMEOUT` | `90s` | `httpClientTimeout` |

Each timeout field corresponds to an optional override on the `CostJob` resource. See [CostJob](./crds/costjob.md) for more details.

## Manager command-line flags

The manager binary accepts command-line flags to configure its runtime behavior. Most are set automatically by the Helm chart; you only need to override them in special cases.

| Flag | Default | Purpose |
|---|---|---|
| `--mode` | `controller` | Operating mode. End users set `controller` in the Deployment; the other values are set automatically by the scheduled jobs the operator creates. |
| `--metrics-bind-address` | `0` (disabled) | Address the metrics endpoint binds to. |
| `--metrics-secure` | `true` | Serve metrics over `HTTPS`. |
| `--health-probe-bind-address` | `:8081` | Liveness and readiness probe endpoint. |
| `--leader-elect` | `false` | Enable leader election for high-availability deployments. |
| `--webhook-cert-path` | (empty) | Directory containing the webhook serving certificate. |
| `--webhook-cert-name` | `tls.crt` | Filename of the webhook certificate within the cert path. |
| `--webhook-cert-key` | `tls.key` | Filename of the webhook certificate key within the cert path. |
| `--metrics-cert-path` | (empty) | Directory containing the metrics serving certificate. |
| `--metrics-cert-name` | `tls.crt` | Filename of the metrics certificate within the cert path. |
| `--metrics-cert-key` | `tls.key` | Filename of the metrics certificate key within the cert path. |
| `--skipDBConnection` | `false` | Skip database initialisation on startup. Local debugging only. |

For cloud integration options, see [FinOpsProvider](./crds/finopsprovider.md). For pricing configuration, see [PriceBook](./crds/pricebook.md).
