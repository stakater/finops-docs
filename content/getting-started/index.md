# Getting started

This section walks you from a fresh cluster to your first active Subscription accruing charges. By the end you will have the operator running, a pricing model in place, and a Subscription whose `status.costs` reflects real billing data.

## What you'll do

1. [Confirm prerequisites](./prerequisites.md) — Kubernetes, cert-manager, PostgreSQL, and OpenCost.
1. [Install the operator via Helm](./installation.md) — add the chart repository, wire in the PostgreSQL Secret, and verify the Deployment is running.
1. [Walk through the quickstart](./quickstart.md) — create the five CRDs in order and watch a Subscription start accruing charges.

## Roughly how long

Plan for about 15 minutes on a cluster that already has PostgreSQL reachable and OpenCost installed. Add more time if you need to install PostgreSQL yourself, provision cloud credentials, or set up OpenCost from scratch.

After finishing this section, move on to [Concepts](../concepts/index.md) to understand the mental model behind the five CRDs, or browse the [guides](../guides/define-pricing.md) for specific tasks such as defining pricing or reading subscription costs.
