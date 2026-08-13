# Use cases

## Internal chargeback and showback

A platform team that funds one shared cluster out of a central budget needs to know which team caused which part of the bill. Publish an Offering that meters `cpuHour`, `ramGbHour`, and `pvGbHour`, subscribe each consuming team to it, and every hour lands as a row in the `subscription_charges` table alongside the Offering version that priced it. Showback stops there and reports the numbers; chargeback bills them, and the same rows serve both.

## Tenant billing in a Multi Tenant Operator cluster

Where namespaces are grouped into tenants by Multi Tenant Operator, the billing boundary you care about is the tenant, not the namespace. The operator records each Subscription's namespace labels with every version it writes to PostgreSQL, and indexes the `stakater.com/tenant` label specifically, so charges roll up per tenant by joining charge rows to their subscription version. Setting the `mtoEnabled` Helm value also switches the operator into MTO-bundled mode, where it configures the `OpenCost` custom resource in the `dependencies.tenantoperator.stakater.com` API group instead of a standalone OpenCost deployment.

## On-premises clusters with no cloud price list

On owned hardware there is no provider API to ask what an hour of CPU costs, which is exactly the case a `PriceBook` covers. Point `FinOpsProvider` at `onpremoptions`, put your own per-unit rates for CPU, RAM, GPU, storage, and network in a PriceBook, and mark it active; the operator renders those rates into OpenCost's custom pricing document and prices subscription charges from them directly. The accounting model is then identical to a cloud cluster, because nothing downstream reads a provider price list.

## Product-style offerings with add-ons

An internal service is rarely a single line item: a managed database has a base tier plus optional replicas, backups, and support. Model the base tier as one Offering and each add-on as its own Offering whose Subscriptions name the base Subscription as `parent`, giving you a per-customer tree of what was actually bought. Add-ons typically use `ActivatedAt` tick alignment so each one bills from its own start date, while `lifecycle.onParentDeactivate` decides whether an add-on follows the base tier down or is orphaned and kept running.
