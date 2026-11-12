# Introduction

The FinOps Operator performs cost accounting for Kubernetes workloads. It collects allocation data for what actually ran in the cluster, prices that usage against rates you declare, and bills the result to whoever subscribed to it. The whole model is expressed as Kubernetes resources, so a platform engineer, SRE, or FinOps practitioner who is comfortable with `kubectl` can publish an internal price list, attach it to a service, and read accrued charges back from a resource status without leaving the cluster.

With the FinOps Operator, you can:

- **Publish an internal price list** as a `PriceBook`, with per-unit rates for CPU, GPU, RAM, storage and network.
- **Price what actually ran**, using allocation data collected from OpenCost on a schedule you control.
- **Model what you sell** as an `Offering`, with a recurring fee, margins on measured usage, or both.
- **Bill whoever consumes it** through a `Subscription` that accrues charges while it is active, including add-ons.
- **Read charges from the cluster**: hourly, daily and monthly totals land on the Subscription's status, with full history in PostgreSQL.
