# Configuration reference

The FinOps Operator ships one binary that runs in three modes, and each mode reads its own configuration. A platform engineer configures the long-lived controller manager through Helm values, which the chart turns into container arguments and environment variables. The two short-lived job modes are configured by the operator itself, from the `CostJob` you author plus the pod template the operator embeds, so their environment is something you read rather than something you set. [The three binary modes](../concepts/architecture.md#the-three-binary-modes) explains the split.

This page is the exhaustive surface: every key in the chart's `values.yaml`, every environment variable the code reads, and every flag the binary registers. [On Kubernetes](../getting-started/installation/kubernetes.md) covers the practical subset you are likely to change.

## Helm chart values

The chart is generated from the operator's Kubernetes manifests and then post-processed, so `values.yaml` is the authoritative list of keys rather than a hand-written interface. Read the shipped defaults for the version you are installing with `helm show values oci://ghcr.io/stakater/public/charts/finops-operator`.

### Controller manager

| Key | Default | Purpose |
| --- | --- | --- |
| `controllerManager.replicas` | `1` | Replicas of the manager Deployment. Leader election is on by default, so extra replicas stand by rather than share work. |
| `controllerManager.manager.args` | `--metrics-bind-address=:8443`, `--leader-elect`, `--health-probe-bind-address=:8081`, `--webhook-cert-path=/tmp/k8s-webhook-server/serving-certs` | The manager's command line, replaced wholesale when you set it. See [manager flags](#manager-flags). |
| `controllerManager.manager.image.repository` | `ghcr.io/stakater/finops-operator` | Manager image. The same coordinate is passed to generated CronJob pods through `OPERATOR_IMAGE`. |
| `controllerManager.manager.image.tag` | `v0.1.16` | Image tag. It falls back to the chart's `appVersion` when empty, and the shipped value moves with each chart release. |
| `controllerManager.manager.env.opencostDeploymentName` | `finops-operator-opencost` | Becomes `OPENCOST_DEPLOYMENT_NAME`. The Deployment the PriceBook reconciler restarts after a pricing change. |
| `controllerManager.manager.env.opencostDeploymentNamespace` | `finops-operator-system` | Becomes `OPENCOST_DEPLOYMENT_NAMESPACE`. Where that Deployment and the pricing ConfigMap live. |
| `controllerManager.manager.env.mtoEnabled` | `"false"` | Becomes `MTO_ENABLED`. Only the exact string `"true"` switches the operator to the Multi Tenant Operator path. |
| `controllerManager.manager.extraEnv` | `[]` | Raw `env` entries appended to the manager container. The only way to set a variable the chart has no named key for, such as `ENABLE_WEBHOOKS` or `CLUSTER_ID`. |
| `controllerManager.manager.containerSecurityContext` | `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]` | Container security context. |
| `controllerManager.podSecurityContext` | `runAsNonRoot: true`, `seccompProfile.type: RuntimeDefault` | Pod security context. |
| `controllerManager.serviceAccount.annotations` | `{}` | Annotations on the `finops-operator-controller-manager` ServiceAccount. |
| `imagePullSecrets` | `[]` | Pull secrets set on both Deployments, and serialized into the manager's `IMAGE_PULL_SECRETS` variable so generated CronJob pods inherit them. |
| `kubernetesClusterDomain` | `cluster.local` | Used to build the certificate DNS names. Also passed to both containers as `KUBERNETES_CLUSTER_DOMAIN`. |

The chart sets no resource requests or limits on the manager container. Add them through your own values if the namespace enforces a quota.

### Certificates and platform

| Key | Default | Purpose |
| --- | --- | --- |
| `certManager.enabled` | `true` | Creates the self-signed `Issuer`, the webhook serving `Certificate`, and the metrics `Certificate`, and adds the cert-manager CA injection annotation to the `ValidatingWebhookConfiguration`. |
| `openshift.enabled` | `false` | Annotates the webhook Service for OpenShift's service serving certificates and switches CA injection to `service.beta.openshift.io/inject-cabundle`. Use instead of cert-manager, not alongside it. |
| `webhookService.type` | `ClusterIP` | Service type for the webhook endpoint. |
| `webhookService.ports` | port `443`, `targetPort` `9443`, `TCP` | The webhook Service's ports. The manager serves admission on 9443. |
| `metricsService.type` | `ClusterIP` | Service type for the metrics endpoint. |
| `metricsService.ports` | port `8443`, `targetPort` `8443`, `TCP`, named `https` | The metrics Service's ports. |

### Dependency Secret names

The manager's `secretKeyRef` entries are not optional, so a missing Secret or a missing key leaves the pod unable to start.

| Key | Default | Purpose |
| --- | --- | --- |
| `secrets.postgres` | `finops-operator-postgres-config` | Secret holding key `POSTGRES_CONNECTION_STRING`. Wired into the manager as that variable and into the gateway as `PG_CONNECTION_STRING`. |
| `secrets.opencost` | `finops-operator-opencost-config` | Secret holding key `OPENCOST_CONNECTION_STRING`. Mandatory: the manager refuses to start without a value. |
| `secrets.prometheus` | `finops-operator-prometheus-config` | Referenced by no chart template, so it changes nothing on the Helm path. |

!!! warning
    `secrets.prometheus` is inert under Helm but not under Operator Lifecycle Manager. The bundle's ClusterServiceVersion wires a `PROMETHEUS_URL` variable from that Secret with a non-optional `secretKeyRef`, so an OLM install needs the Secret to exist and to carry a `PROMETHEUS_URL` key even though nothing in the operator reads the value. See [PROMETHEUS_URL](#prometheus_url).

### Starter resources

The chart can create one `CostJob` of each type and one `PriceBook`. All three are off by default, so a default install reconciles nothing until you author those resources yourself.

| Key | Default | Purpose |
| --- | --- | --- |
| `costJob.enabled` | `false` | Creates `<release>-daily-scraping-job`, a `ResourceCostCollection` CostJob, in the release namespace. |
| `costJob.interval` | `1m` | Its `spec.interval`. |
| `chargeCollectionJob.enabled` | `false` | Creates `<release>-charge-collection-job`, a `SubscriptionChargeCollection` CostJob, in the release namespace. |
| `chargeCollectionJob.interval` | `1m` | Its `spec.interval`. |
| `priceBook.enabled` | `false` | Creates `<release>-default-pricing` in the release namespace. |
| `priceBook.currency` | `USD` | Its `spec.currency`. |
| `priceBook.valuationMode` | `currency` | Its `spec.valuationMode`. Only `currency` prices an Offering. |
| `priceBook.rates.cpuHour` | `""` | Rate per CPU-hour. Empty rates are omitted from the object rather than written as zero. |
| `priceBook.rates.spotCPUHour` | `""` | Rate per spot CPU-hour. |
| `priceBook.rates.ramGbHour` | `""` | Rate per GB-hour of memory. |
| `priceBook.rates.spotRAMGbHour` | `""` | Rate per spot GB-hour of memory. |
| `priceBook.rates.pvGbHour` | `""` | Rate per GB-hour of persistent volume. |
| `priceBook.rates.gpuHour` | `""` | Rate per GPU-hour. |
| `priceBook.rates.networkGiB` | `""` | Rate per GiB of network transfer. |

Both CostJob templates also expose seven timeout keys, each empty by default and each omitted from the generated object when empty: `databaseInitTimeout`, `k8sOperationTimeout`, `openCostFetchTimeout`, `databaseInsertTimeout`, `databaseViewsRefreshTimeout`, `statusUpdateTimeout`, and `httpClientTimeout`, under both `costJob` and `chargeCollectionJob`. Five of the seven take effect. [Timeouts](../concepts/costjob.md#timeouts) gives what each one bounds.

!!! warning
    Two of those keys change nothing, and neither one tells you so. `k8sOperationTimeout` renders a field of that name onto the `CostJob`, but the CRD calls the field `kubernetesOperationTimeout`, so the API server prunes the unknown field; set `kubernetesOperationTimeout` on the `CostJob` object directly instead. `databaseViewsRefreshTimeout` does reach the object, and then bounds nothing: the materialized view it used to refresh has been dropped and the collection run no longer refreshes any view. See [databaseViewsRefreshTimeout](#databaseviewsrefreshtimeout).

Two more things are worth knowing before you turn the starter resources on. An interval of `1m` maps to the cron expression `* * * * *`, so an unchanged default runs collection every minute; [from interval to schedule](../concepts/costjob.md#from-interval-to-schedule) lists the intervals the operator recognises. And the chart writes the active marker on its `PriceBook` as a label while the operator reads an annotation, so the chart's marker does not pin the book; [choosing the active PriceBook](../concepts/pricebook.md#choosing-the-active-pricebook) covers what happens instead.

### FinOps Gateway

The chart deploys a second workload, the FinOps Gateway, which reads the same PostgreSQL Secret key and listens on port 8080.

| Key | Default | Purpose |
| --- | --- | --- |
| `finopsGatewayGateway.replicas` | `1` | Replicas of the gateway Deployment. |
| `finopsGatewayGateway.finopsGatewayContainer.image.repository` | `ghcr.io/stakater/finops-gateway` | Gateway image. |
| `finopsGatewayGateway.finopsGatewayContainer.image.tag` | `v0.1.0` | Gateway image tag, falling back to the chart's `appVersion` when empty. |
| `finopsGatewayGateway.finopsGatewayContainer.env.port` | `"8080"` | Becomes `PORT`. |
| `finopsGatewayGateway.finopsGatewayContainer.env.enableAuth` | `"false"` | Becomes `ENABLE_AUTH`. |
| `finopsGatewayGateway.finopsGatewayContainer.env.mtoGatewayUrl` | `""` | Becomes `MTO_GATEWAY_URL`. |
| `finopsGatewayGateway.finopsGatewayContainer.env.allowedOrigins` | `""` | Becomes `ALLOWED_ORIGINS`. |
| `finopsGatewayGateway.finopsGatewayContainer.extraEnv` | `[]` | Raw `env` entries appended to the gateway container. |
| `finopsGatewayGateway.finopsGatewayContainer.containerSecurityContext` | `{}` | Container security context for the gateway. |
| `finopsGatewayService.type` | `ClusterIP` | Gateway Service type. |
| `finopsGatewayService.ports` | port `8080`, `targetPort` `8080`, named `http` | Gateway Service ports. |
| `finopsGatewayIngress.enabled` | `false` | Creates an Ingress for the gateway Service. |
| `finopsGatewayIngress.className` | `""` | Sets `spec.ingressClassName` when non-empty. |
| `finopsGatewayIngress.annotations` | `{}` | Annotations on the Ingress. |
| `finopsGatewayIngress.tls` | `[]` | Copied into the Ingress `spec.tls`. |
| `finopsGatewayIngress.rules` | `[]` | Copied into the Ingress `spec.rules`. An Ingress with no rules routes nothing, so set this whenever you enable the Ingress. |
| `finopsGatewayIngress.hosts` | `[]` | Declared in `values.yaml` and read by no template. Put hostnames in `rules` instead. |

### Bundled dependencies

Setting `mdoDependencies.enabled` pulls in the `mto-dependencies-operator` dependency chart and creates PostgreSQL, OpenCost, Prometheus, and the three dependency Secrets, so the operator has something to talk to on a fresh cluster.

| Key | Default | Purpose |
| --- | --- | --- |
| `mdoDependencies.enabled` | `false` | Enables the dependency chart and the objects that go with it. |
| `mdoDependencies.postgres.database` | `finopsdb` | Database created, and the database named in the generated connection string. |
| `mdoDependencies.postgres.username` | `finopsuser` | Application user, also used in the generated connection string. |
| `mdoDependencies.postgres.password` | `superfinopspassword1234` | That user's password. |
| `mdoDependencies.postgres.postgresPassword` | `supersecurepassword1234` | The `postgres` superuser password. |

!!! warning
    The two password defaults are placeholders that ship with the chart, and the generated connection string uses `sslmode=disable`. Treat `mdoDependencies` as a way to get a cluster running, not as a production database.

## Environment variables

Every variable below is one the code actually reads, at the call site named in the description. Which process reads it matters, because the three modes share a binary but not a configuration surface.

### The controller manager

The manager validates four variables at startup and exits if any is empty, so these are hard requirements rather than defaults.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `POSTGRES_CONNECTION_STRING` | Yes | none | PostgreSQL DSN. Also used to apply migrations at startup unless `--skipDBConnection` is set. |
| `OPENCOST_CONNECTION_STRING` | Yes | none | Base URL of the OpenCost service, for example `http://finops-operator-opencost.finops-operator-system.svc.cluster.local:9003`. Passed on to generated CronJob pods. |
| `OPENCOST_DEPLOYMENT_NAME` | Yes | none | Deployment restarted after the pricing ConfigMap changes. |
| `OPENCOST_DEPLOYMENT_NAMESPACE` | Yes | none | Namespace of that Deployment and of the pricing ConfigMap. |
| `MTO_ENABLED` | No | unset, treated as false | Only the exact string `"true"` enables the Multi Tenant Operator path. Any other value, including `"True"`, leaves it off. |
| `CLUSTER_ID` | No | `default` | Identifier stamped on the rows the operator mirrors into PostgreSQL. The chart has no key for it, so set it through `extraEnv` if one database serves several clusters. |
| `ENABLE_WEBHOOKS` | No | unset, webhooks on | Both validating webhooks are registered unless this is exactly `"false"`. Anything else, including an empty value, registers them. |
| `IMAGE_PULL_SECRETS` | No | unset | A JSON array of local object references, applied to the pod template of every CronJob the operator generates. Malformed JSON fails the CostJob reconcile. |
| `OPERATOR_IMAGE` | No | unset | The image written into generated CronJob pods, and passed through to them as a variable of the same name. An empty value produces a CronJob with an empty image. |
| `FINOPS_MIGRATION_DIR` | No | `/migrations` | Directory the migration files are read from. Useful when running the binary outside its image. |

`KUBERNETES_CLUSTER_DOMAIN` is set on both containers by the chart and read by no code in the operator.

#### PROMETHEUS_URL

`PROMETHEUS_URL` is not required in controller mode. It appears nowhere in the operator's Go source, and the startup validation covers only the four variables above, so the manager starts and runs without it. Prometheus is a dependency of OpenCost rather than of the operator: OpenCost queries it, and the operator queries OpenCost.

The name survives in one place. The bundle's ClusterServiceVersion still declares a `PROMETHEUS_URL` variable sourced from the Prometheus Secret with a non-optional `secretKeyRef`, so on the OLM path the Secret and the key must exist for the pod to start even though the value is never used. On the Helm path no template references it at all.

### The allocation CronJob

Pods of a `ResourceCostCollection` run start in `--mode=cronjob`. Four variables are required and the run aborts without them; the rest are read with a fallback. The reconciler overlays what it computes onto the operator's pod template by name, so a variable the template sets and the reconciler does not name reaches the pod with the template's value, and the compiled-in fallback applies only when neither supplies it.

| Variable | Set by | Effective value in the generated pod |
| --- | --- | --- |
| `COSTJOB_NAME` | Reconciler | The CostJob's name. Required. |
| `COSTJOB_NAMESPACE` | Reconciler | The CostJob's namespace. Required. |
| `POSTGRES_CONNECTION_STRING` | Reconciler | A `secretKeyRef` into `<costjob-name>-costjob-secret`. Required. |
| `OPENCOST_CONNECTION_STRING` | Reconciler | The manager's own OpenCost URL, with any trailing slash trimmed. Required. |
| `OPERATOR_IMAGE` | Reconciler | The manager's `OPERATOR_IMAGE`. Carried but not read in this mode. |
| `CLUSTER_ID` | Template | `default`. The compiled-in fallback is also `default`. |
| `HOURS_LOOKBACK` | Template | `5`. See [HOURS_LOOKBACK](#hours_lookback). |
| `OPENCOST_AGGREGATE` | Template | `namespace,pod,container`, matching the compiled-in fallback. The dimensions each allocation row is grouped by. |
| `OPENCOST_STEP` | Template | `1h`, matching the compiled-in fallback. The step of each OpenCost query. |
| `OPENCOST_RESOLUTION` | Template | `1m`, matching the compiled-in fallback. The resolution of each OpenCost query. |
| `SCHEDULED_TIMESTAMP` | Template | A `fieldRef` to the `batch.kubernetes.io/cronjob-scheduled-timestamp` annotation. Parsed as RFC 3339 and truncated to the hour to pin the window a retry works on. An empty value, or one that does not parse, falls back to the current hour, which is why a hand-run pod processes now rather than a past window. |

Six timeout variables are written onto the pod, each only when the matching `CostJob` field is set, and each falling back to the default on the type otherwise.

| Variable | `CostJob` field | Default |
| --- | --- | --- |
| `DATABASE_INIT_TIMEOUT` | `databaseInitTimeout` | `2m` |
| `K8S_OPERATION_TIMEOUT` | `kubernetesOperationTimeout` | `1m` |
| `OPENCOST_FETCH_TIMEOUT` | `openCostFetchTimeout` | `2m` |
| `DATABASE_INSERT_TIMEOUT` | `databaseInsertTimeout` | `3m` |
| `STATUS_UPDATE_TIMEOUT` | `statusUpdateTimeout` | `1m` |
| `HTTP_CLIENT_TIMEOUT` | `httpClientTimeout` | `90s` |

A duration that does not parse is logged and the default is kept, so a typo degrades to the default rather than failing the run.

#### databaseViewsRefreshTimeout

The `CostJob` type carries a seventh timeout field, `databaseViewsRefreshTimeout`, which is retained for API compatibility and does nothing. There is no `DATABASE_VIEWS_REFRESH_TIMEOUT` variable on the pod: the reconciler no longer writes one, the job configuration no longer holds the value, and no code reads it.

The reason is that the work it bounded is gone. Collection runs used to rebuild the `mv_provider_allocations_summary` materialized view on every tick, which meant a full re-scan and re-aggregate of `provider_allocations` growing with retained history. Nothing read that view any more, so it was dropped in the operator's fourteenth migration and the refresh step was removed with it.

The field is still settable, on the object and through the chart's `costJob.databaseViewsRefreshTimeout` and `chargeCollectionJob.databaseViewsRefreshTimeout` keys, and it carries no default. Setting it is accepted, is not pruned, and changes nothing. Treat it as vestigial, and expect to find it on `CostJob` objects created before it was deprecated.

`OPENCOST_HOSTNAME` and `OPENCOST_PORT` are also on the pod, carried over from the template, and read by no code. The OpenCost address comes from `OPENCOST_CONNECTION_STRING` alone.

#### HOURS_LOOKBACK

`HOURS_LOOKBACK` decides how many hours before the scheduled hour a run revisits, so that hours which were empty or failed earlier get another chance before they are finalized. It has two layers. The operator's pod template sets it to `5`, and the Go fallback is `2`. Because the reconciler merges its overrides onto the template by name and does not name this variable, the template's value survives and the effective default in a generated CronJob is **5**. The fallback of `2` applies only if the variable is absent from the pod altogether, which is what happens when you run the binary in that mode yourself.

### The collection job

Pods of a `SubscriptionChargeCollection` run start in `--mode=collectionjob` and read a much smaller set. The reconciler builds their environment with the same code, so a collection-job pod also carries `COSTJOB_NAME`, `COSTJOB_NAMESPACE`, `OPENCOST_CONNECTION_STRING`, and whichever timeout variables the `CostJob` set, and reads none of them.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `POSTGRES_CONNECTION_STRING` | Yes | none | The charges and allocations are read and written through this connection. |
| `CLUSTER_ID` | No | `default` | Scopes the charge rows and the summary queries. Note the generated pod inherits `default` from the template, not the manager's value. |
| `SCHEDULED_TIMESTAMP` | No | current hour | Pinned once at construction and truncated to the hour, so every retry of a Job targets the same window. |

## Manager flags

The binary registers the same flags in every mode, but only the controller uses most of them. The chart passes four of them through `controllerManager.manager.args`.

| Flag | Default | Purpose |
| --- | --- | --- |
| `--mode` | `controller` | One of `controller`, `cronjob`, or `collectionjob`. An unrecognised value exits with an error. The operator sets the job modes on the CronJobs it generates. |
| `--skipDBConnection` | `false` | Skip database initialization and migrations. For local debugging. |
| `--metrics-bind-address` | `0` | Address the metrics endpoint binds to. `0` disables it; the chart passes `:8443`. |
| `--metrics-secure` | `true` | Serve metrics over TLS, with authentication and authorization filters in front. |
| `--health-probe-bind-address` | `:8081` | Address the liveness and readiness endpoints bind to. |
| `--leader-elect` | `false` | Enable leader election. The chart passes it, so a chart install has it on. |
| `--webhook-cert-path` | `""` | Directory holding the webhook serving certificate. Empty means no certificate watcher is started; the chart passes `/tmp/k8s-webhook-server/serving-certs`. |
| `--webhook-cert-name` | `tls.crt` | Certificate filename inside that directory. |
| `--webhook-cert-key` | `tls.key` | Private key filename inside that directory. |
| `--metrics-cert-path` | `""` | Directory holding the metrics serving certificate. Empty means the metrics server uses its own generated certificate. |
| `--metrics-cert-name` | `tls.crt` | Certificate filename inside that directory. |
| `--metrics-cert-key` | `tls.key` | Private key filename inside that directory. |

The controller-runtime logging flags are registered as well: `--zap-devel`, `--zap-encoder`, `--zap-log-level`, `--zap-stacktrace-level`, and `--zap-time-encoding`. The operator builds its logger with development mode off, so `--zap-devel` defaults to `false` and logs are JSON at info level unless you change it.

## Related

- [On Kubernetes](../getting-started/installation/kubernetes.md) for the values a real install sets, and why the two dependency Secrets are not optional.
- [CostJob](../concepts/costjob.md) for what the generated CronJob looks like and what each timeout bounds.
- [`CostJobSpec`](api.md#costjobspec) and [`PriceBookSpec`](api.md#pricebookspec) for the field-level schema behind the starter resources.
- [Status conditions](status-conditions.md) for reading back what the configuration produced.
