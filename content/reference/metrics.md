# Metrics

The controller manager can expose a Prometheus-format `/metrics` endpoint, served by controller-runtime's metrics server inside the manager process. The two short-lived job modes expose nothing: they start, do one pass, and exit, so there is no endpoint to scrape on a collection run.

## Turning the endpoint on

`--metrics-bind-address` decides whether the server runs at all, and its default is `0`, which means disabled. The chart passes `:8443` through `controllerManager.manager.args`, so a chart install already has it on; a bare binary run does not. That list is replaced wholesale when you set it, so if you override it, carry the other entries over. [Manager flags](configuration.md#manager-flags) lists the full set.

`--metrics-secure` defaults to true, which means the endpoint is served over TLS and sits behind controller-runtime's authentication and authorization filter. Every scrape has to present a bearer token, and the filter checks it by creating a `TokenReview` and a `SubjectAccessReview` against the API server. That is why the manager is bound to `finops-operator-metrics-auth-role`; the scraper, in turn, needs `get` on the non-resource URL `/metrics`, which is what the unbound `finops-operator-metrics-reader` ClusterRole grants. [Metrics roles](rbac.md#metrics-roles) covers both.

Certificates are optional. With `--metrics-cert-path` empty, which is the default and what the chart leaves it at, controller-runtime serves the endpoint with a certificate it generates itself, so a scraper has nothing to verify against and has to skip verification. Pointing `--metrics-cert-path` at a mounted directory, with `--metrics-cert-name` and `--metrics-cert-key` if the filenames differ from `tls.crt` and `tls.key`, starts a watcher on that directory instead and picks up renewals without a restart.

!!! note
    With `certManager.enabled` on, the chart creates a `Certificate` for the metrics Service whose key material lands in the Secret `metrics-server-cert`, and then never mounts it: the manager container has only the webhook certificate volume, and no `--metrics-cert-path` argument is passed. The Secret exists and is unused. To serve verifiable metrics TLS, mount it yourself and add the flag.

## The metrics Service

The chart creates `finops-operator-controller-manager-metrics-service`, a `ClusterIP` Service with one port named `https` on 8443 targeting container port 8443. `metricsService.type` and `metricsService.ports` are the values that change it. Its selector matches the manager pods, and it carries the labels `control-plane: controller-manager` and `app.kubernetes.io/name: finops-operator`, which is what a `ServiceMonitor` selects on.

## Scraping it

Neither install path creates a `ServiceMonitor`. The operator's manifests carry one, in `config/prometheus/`, but that directory is commented out of the default overlay the chart is generated from, so it appears in neither the chart nor a `kubectl apply` of the manifests. Apply your own, shaped like the one the operator ships:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: finops-operator-controller-manager-metrics-monitor
  namespace: finops-operator-system
spec:
  selector:
    matchLabels:
      control-plane: controller-manager
      app.kubernetes.io/name: finops-operator
  endpoints:
    - path: /metrics
      port: https
      scheme: https
      bearerTokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token
      tlsConfig:
        insecureSkipVerify: true
```

`insecureSkipVerify: true` is what the shipped version uses, and it is only defensible because of the self-signed certificate described above. Once you mount `metrics-server-cert` into the manager and point `--metrics-cert-path` at it, replace that line with a `tlsConfig` that reads `ca.crt`, `tls.crt`, and `tls.key` from the same Secret and sets `serverName` to the metrics Service's DNS name.

The scraping identity also needs the metrics-reader permission:

```sh
kubectl create clusterrolebinding finops-metrics-reader \
  --clusterrole=finops-operator-metrics-reader \
  --serviceaccount=monitoring:prometheus-k8s
```

## What you get

The operator registers no metrics of its own. There is no custom collector, nothing calls into a Prometheus registry, and `prometheus/client_golang` is an indirect dependency pulled in by controller-runtime rather than something the code uses. Everything on the endpoint is the standard set that controller-runtime and its client libraries publish: per-controller reconcile counts, error counts, and latency histograms; work queue depth, adds, retries, and wait times; Kubernetes API client request counts and latencies; and Go runtime and process gauges.

There is no metric for a cost figure, a charge row, a collection run, or an active PriceBook. Those are reported through the objects themselves rather than through the endpoint. Read a run's outcome from the CostJob's `status.executionHistory`, and a Subscription's figures from its `status.costs` and `CostsResolved` condition, as [status conditions](status-conditions.md) describes.

What the standard metrics are good for is the health of the reconcilers, and the `controller` label is how you separate them. The five values are `finopsprovider-controller`, `pricebook-controller`, `costjob-controller`, `offering`, and `subscription`; the last two carry no suffix. A rising error count or reconcile latency on `offering` or `subscription` is the signal that gates are failing or the API is slow, and pairing it with the conditions on the objects tells you which gate.

## Related

- [Configuration reference](configuration.md#manager-flags) for every flag named here and its default.
- [RBAC](rbac.md#metrics-roles) for the two roles the endpoint depends on.
- [Troubleshooting](../troubleshooting.md) for working back from a failing reconcile to its cause.
