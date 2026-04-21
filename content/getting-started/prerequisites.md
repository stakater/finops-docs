# Prerequisites

Before installing the FinOps Operator, you need a Kubernetes cluster with cert-manager installed, a reachable PostgreSQL database, and an OpenCost instance. Two optional components — Prometheus and MTO — unlock additional capabilities but are not required to get started.

## Required

### Kubernetes cluster

Any recent version of Kubernetes works, including OpenShift. The operator does not depend on a specific Kubernetes minor version; it uses standard APIs available across all current distributions.

### cert-manager

cert-manager provisions TLS certificates for cluster components. The operator's admission webhooks — which validate and reject invalid CRD configurations before they are stored — rely on cert-manager to provide their serving certificates. You can disable webhooks by setting the environment variable `ENABLE_WEBHOOKS=false`, but this is not recommended because admission validation is your primary safeguard against incorrectly configured resources. Install cert-manager from [https://cert-manager.io](https://cert-manager.io) before installing the operator.

### PostgreSQL

The operator requires a reachable PostgreSQL database to store cost and charge data. The Helm chart looks for a Kubernetes Secret named `finops-operator-postgres-config` by default; that Secret must exist in the same namespace as the operator and must contain a `POSTGRES_CONNECTION_STRING` key holding the database DSN. See [Installation](./installation.md) for the exact `kubectl` command to create this Secret.

### OpenCost

OpenCost is the open-source cost allocation engine the operator queries for resource usage data. You can bring your own OpenCost installation (BYO mode) or let Stakater's Multi-Dependency Operator (MDO) manage it alongside the FinOps Operator (MTO-bundled mode). BYO mode suits teams that already run OpenCost or that want full control over the installation. MTO-bundled mode is convenient when you are deploying the full Stakater platform and want MDO to handle the OpenCost lifecycle. See [Operating modes](../concepts/operating-modes.md) for a detailed comparison.

## Optional

### Prometheus

The operator can use a Prometheus endpoint to expose supplementary metrics. If your deployment includes Prometheus, create a Kubernetes Secret named `finops-operator-prometheus-config` in the operator's namespace containing the endpoint URL. The chart value `secrets.prometheus` controls which Secret name the operator mounts.

### MTO (Multi-Tenant Operator)

When the operator runs in a cluster managed by Stakater's Multi-Tenant Operator (MTO), it uses MTO's tenant labels to associate cost data with tenants. MTO is not required for single-tenant clusters or clusters where tenant isolation is handled by other means.

## Next

[Install the operator](./installation.md)
