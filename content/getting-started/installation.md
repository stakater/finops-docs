# Installation

The Helm chart installs both the operator and its CRDs in a single step. After the chart is applied, the operator Deployment starts and begins reconciling any CRDs you create.

## Add the Helm repository

```bash
helm repo add stakater <chart-repo-url>
helm repo update
```

Replace `<chart-repo-url>` with the address of the chart repository where the operator is published.

## Install with default values

The default installation runs the operator in BYO-OpenCost mode with `MTO_ENABLED` unset, meaning the operator manages OpenCost by rewriting the `finops-operator-custom-pricing-configs` ConfigMap and restarting the OpenCost Deployment when pricing changes. No `CostJob` and no `PriceBook` are created by the chart by default; you create those yourself as part of the quickstart.

```bash
helm install finops-operator stakater/finops-operator \
  --namespace finops-operator-system \
  --create-namespace
```

After the chart is applied, a Deployment called `finops-operator-controller-manager` appears in the install namespace and becomes ready within a few seconds.

## Wire in the PostgreSQL Secret

The operator reads the database connection string from a Kubernetes Secret. The Secret must contain a key named `POSTGRES_CONNECTION_STRING` holding the PostgreSQL DSN, and it must exist in the same namespace as the operator.

```bash
kubectl create secret generic finops-operator-postgres-config \
  --namespace finops-operator-system \
  --from-literal=POSTGRES_CONNECTION_STRING='postgres://user:password@host:5432/dbname?sslmode=require'
```

If you change the Secret name, update the `secrets.postgres` chart value to match.

## Pick MTO-bundled or BYO-OpenCost mode

In BYO-OpenCost mode (the default) the operator manages pricing by writing a ConfigMap and restarting the OpenCost Deployment directly. In MTO-bundled mode, the operator patches an OpenCost custom resource managed by MDO instead. See [Operating modes](../concepts/operating-modes.md) for a full comparison.

To switch to MTO-bundled mode:

```bash
helm upgrade finops-operator stakater/finops-operator \
  --namespace finops-operator-system \
  --set controllerManager.manager.env.mtoEnabled=true
```

To let MDO manage the OpenCost installation alongside the operator:

```bash
helm upgrade finops-operator stakater/finops-operator \
  --namespace finops-operator-system \
  --set mdoDependencies.enabled=true
```

## A richer `values.yaml` example

For production installs, save your configuration to a `values.yaml` file and pass it to Helm. The example below covers the most commonly adjusted settings:

```yaml
# values.yaml

# PostgreSQL Secret name (must exist in the operator's namespace)
secrets:
  postgres: finops-operator-postgres-config       # default
  prometheus: finops-operator-prometheus-config   # optional; omit if not using Prometheus

# Image pull secret (if your registry requires authentication)
imagePullSecrets:
  - name: my-registry-credentials

controllerManager:
  manager:
    env:
      # Set to "true" for MTO-bundled mode; leave unset or "false" for BYO-OpenCost mode
      mtoEnabled: "false"
      # Name and namespace of the OpenCost Deployment the operator restarts on pricing changes
      opencostDeploymentName: finops-operator-opencost
      opencostDeploymentNamespace: finops-operator-system

# Create a default PriceBook on install (optional convenience knob)
priceBook:
  enabled: true
  currency: USD
  valuationMode: currency
  rates:
    cpuHour: "0.031"
    ramGbHour: "0.004"
    pvGbHour: "0.00012"
    gpuHour: "1.80"
    networkGiB: "0.09"
```

Install or upgrade with the file:

```bash
helm upgrade --install finops-operator stakater/finops-operator \
  --namespace finops-operator-system \
  --create-namespace \
  -f values.yaml
```

## Verify

Check that the Deployment is running:

```bash
kubectl get deployment -n finops-operator-system
```

Inspect the recent logs to confirm the operator started cleanly:

```bash
kubectl logs -n finops-operator-system \
  deployment/finops-operator-controller-manager --tail=20
```

You should see lines indicating the controller manager is running and the webhooks are registered.

## Next

[Walk through the quickstart](./quickstart.md)
