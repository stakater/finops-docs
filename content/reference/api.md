<!-- markdownlint-disable -->
# API Reference

## Packages
- [finops.stakater.com/v1alpha1](#finopsstakatercomv1alpha1)


## finops.stakater.com/v1alpha1

Package v1alpha1 contains API Schema definitions for the finops v1alpha1 API group.

### Resource Types
- [CostJob](#costjob)
- [FinOpsProvider](#finopsprovider)
- [Offering](#offering)
- [PriceBook](#pricebook)
- [Subscription](#subscription)



#### AWSOptions



AWSOptions defines AWS-specific options.



_Appears in:_
- [FinOpsProviderSpec](#finopsproviderspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `cloudIntegrationSecret` _string_ | CloudIntegrationSecret is the Azure Subscription ID. |  | Optional: \{\} <br /> |
| `pricingModelSource` _string_ | PricingModelSource indicates how the pricing model is provided to OpenCost.<br />e.g., "Pricebook" if derived from PriceBook CRs. |  | Optional: \{\} <br /> |


#### AzureOptions



AzureOptions defines Azure-specific options.



_Appears in:_
- [FinOpsProviderSpec](#finopsproviderspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `cloudIntegrationSecret` _string_ | CloudIntegrationSecret is the Azure Subscription ID. |  | Optional: \{\} <br /> |
| `pricingModelSource` _string_ | PricingModelSource indicates how the pricing model is provided to OpenCost.<br />e.g., "Pricebook" if derived from PriceBook CRs. |  | Optional: \{\} <br /> |


#### Compatibility



Compatibility defines compatibility requirements for subscriptions bound to this offering



_Appears in:_
- [OfferingSpec](#offeringspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `requiredOfferings` _[ObjectReference](#objectreference) array_ | RequiredOfferings lists offerings that must be covered by an active subscription in<br />the same family (the connected tree sharing a root ancestor) for a subscription to<br />this offering to activate. Coverage spans the whole family EXCEPT the subscription's<br />own subtree: ancestors, siblings, uncles, and cousins all count; the subscription's<br />own children and descendants do not. A root subscription's subtree is the entire<br />family, so a requirement-bearing root can never be covered. |  | Optional: \{\} <br /> |


#### CostBucket







_Appears in:_
- [SubscriptionStatus](#subscriptionstatus)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `granularity` _string_ | Granularity is the time granularity of this bucket (e.g., hour, day, month). |  | Enum: [hour day month] <br /> |
| `start` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | Start is the start time of the bucket (inclusive). |  |  |
| `endExclusive` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | EndExclusive is the end time of the bucket (exclusive). |  |  |
| `current` _integer_ | Current is the current accumulated spend for the period in micro-currency units. |  | Optional: \{\} <br /> |
| `projected` _integer_ | Projected is the projected spend for the full period cycle in micro-currency units. |  | Optional: \{\} <br /> |
| `breakdown` _[CostMetric](#costmetric) array_ | Breakdown contains the cost breakdown by component. |  | Optional: \{\} <br /> |


#### CostJob



CostJob is the Schema for the costjobs API.





| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `apiVersion` _string_ | `finops.stakater.com/v1alpha1` | | |
| `kind` _string_ | `CostJob` | | |
| `metadata` _[ObjectMeta](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#objectmeta-v1-meta)_ | Refer to Kubernetes API documentation for fields of `metadata`. |  |  |
| `spec` _[CostJobSpec](#costjobspec)_ |  |  |  |
| `status` _[CostJobStatus](#costjobstatus)_ |  |  |  |




#### CostJobSpec



CostJobSpec defines the desired state of CostJob.



_Appears in:_
- [CostJob](#costjob)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `type` _[CostJobType](#costjobtype)_ | Type of the cost collection job, e.g., "ResourceCostCollection" | ResourceCostCollection | Enum: [ResourceCostCollection SubscriptionChargeCollection] <br />Optional: \{\} <br /> |
| `databaseInitTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | DatabaseInitTimeout is the timeout for database initialization | 2m | Optional: \{\} <br /> |
| `kubernetesOperationTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | KubernetesOperationTimeout is the timeout for Kubernetes API operations | 1m | Optional: \{\} <br /> |
| `openCostFetchTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | OpenCostFetchTimeout is the timeout for fetching data from OpenCost | 2m | Optional: \{\} <br /> |
| `databaseInsertTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | DatabaseInsertTimeout is the timeout for database insert operations | 3m | Optional: \{\} <br /> |
| `databaseViewsRefreshTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | DatabaseViewsRefreshTimeout is retained for API compatibility and has no<br />effect. The cost ingestion job no longer refreshes any database view: the<br />mv_provider_allocations_summary materialized view it used to rebuild on<br />every run had no readers and was dropped in migration 14.<br />Deprecated: no-op. Setting this value changes nothing. |  | Optional: \{\} <br /> |
| `statusUpdateTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | StatusUpdateTimeout is the timeout for status update operations | 1m | Optional: \{\} <br /> |
| `httpClientTimeout` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ | HTTPClientTimeout is the timeout for HTTP client requests | 90s | Optional: \{\} <br /> |
| `interval` _[Duration](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#duration-v1-meta)_ |  | 24h |  |
| `resources` _[ResourceRequirements](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#resourcerequirements-v1-core)_ | Resources overrides compute resources for the generated CronJob's loader container.<br />Setting this replaces the whole block, so a partial value does not inherit the<br />template defaults for the keys it omits. Unset means the operator defaults apply. |  | Optional: \{\} <br /> |


#### CostJobStatus



CostJobStatus defines the observed state of CostJob



_Appears in:_
- [CostJob](#costjob)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `lastExecutionTime` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | Last execution time |  |  |
| `lastSuccessfulExecutionTime` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | Last successful execution time |  |  |
| `lastExecutionStatus` _string_ | Status of the last execution |  | Enum: [Success Failed Error Pending] <br /> |
| `executionHistory` _[ExecutionRecord](#executionrecord) array_ | History of the last 10 executions |  |  |


#### CostJobType

_Underlying type:_ _string_



_Validation:_
- Enum: [ResourceCostCollection SubscriptionChargeCollection]

_Appears in:_
- [CostJobSpec](#costjobspec)

| Field | Description |
| --- | --- |
| `ResourceCostCollection` |  |
| `SubscriptionChargeCollection` |  |


#### CostMetric







_Appears in:_
- [CostBucket](#costbucket)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `name` _[MeterName](#metername)_ | Name is the name of the cost metric (e.g., "cpuHour", "pvGbHour"). |  | Enum: [subscription cpuHour gpuHour ramGbHour pvGbHour networkGb] <br />Required: \{\} <br /> |
| `current` _integer_ | Current is the current accumulated value in micro-currency units. |  | Optional: \{\} <br /> |
| `projected` _integer_ | Projected is the projected value in micro-currency units. |  | Optional: \{\} <br /> |


#### ExecutionRecord



ExecutionRecord represents a single execution attempt



_Appears in:_
- [CostJobStatus](#costjobstatus)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `executionTime` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | The time when this execution started |  |  |
| `status` _string_ | Status of the execution (Success, Failed, Error) |  | Enum: [Success Failed Error] <br /> |
| `duration` _string_ | Duration of the execution |  |  |
| `error` _string_ | Error message if the execution failed |  |  |


#### FinOpsProvider



FinOpsProvider is the Schema for the finopsproviders API.





| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `apiVersion` _string_ | `finops.stakater.com/v1alpha1` | | |
| `kind` _string_ | `FinOpsProvider` | | |
| `metadata` _[ObjectMeta](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#objectmeta-v1-meta)_ | Refer to Kubernetes API documentation for fields of `metadata`. |  |  |
| `spec` _[FinOpsProviderSpec](#finopsproviderspec)_ |  |  |  |
| `status` _[FinOpsProviderStatus](#finopsproviderstatus)_ |  |  |  |


#### FinOpsProviderSpec



ProviderOptions holds provider-specific configuration options.
Exactly one of AWS, GCP, Azure, or OnPrem must be set.
These validations operate on the Go field names (AWS, GCP, Azure, OnPrem).
Se https://opencost.io/docs/configuration/ for possible options
todo: +kubebuilder:validation:XValidation:rule="has(self.Aws) || has(self.Gcp) || has(self.Azure) || has(self.OnPrem)", message="At least one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set"
todo: +kubebuilder:validation:XValidation:rule="(has(self.Aws) ? 1 : 0) + (has(self.Gcp) ? 1 : 0) + (has(self.Azure) ? 1 : 0) + (has(self.OnPrem) ? 1 : 0) == 1", message="Exactly one provider option (awsoptions, gcpoptions, azureoptions, onpremoptions) must be set"



_Appears in:_
- [FinOpsProvider](#finopsprovider)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `awsoptions` _[AWSOptions](#awsoptions)_ | AWS specific options. |  | Optional: \{\} <br /> |
| `gcpoptions` _[GCPOptions](#gcpoptions)_ | GCP specific options. |  | Optional: \{\} <br /> |
| `azureoptions` _[AzureOptions](#azureoptions)_ | Azure specific options. |  | Optional: \{\} <br /> |
| `onpremoptions` _[OnPremOptions](#onpremoptions)_ | OnPrem specific options. |  | Optional: \{\} <br /> |


#### FinOpsProviderStatus



FinOpsProviderStatus defines the observed state of FinOpsProvider.



_Appears in:_
- [FinOpsProvider](#finopsprovider)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `observedGeneration` _integer_ | ObservedGeneration reflects the generation of the most recently observed spec. |  | Optional: \{\} <br /> |
| `conditions` _[Condition](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#condition-v1-meta) array_ | Conditions represent the latest available observations of the FinOpsProvider's state. |  | Optional: \{\} <br /> |
| `lastSyncTime` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | LastSyncTime is the timestamp of the last successful sync of OpenCost configuration. |  | Optional: \{\} <br /> |


#### GCPOptions



GCPOptions defines GCP-specific options.



_Appears in:_
- [FinOpsProviderSpec](#finopsproviderspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `cloudIntegrationSecret` _string_ | CloudIntegrationSecret is the Azure Subscription ID. |  | Optional: \{\} <br /> |
| `pricingModelSource` _string_ | PricingModelSource indicates how the pricing model is provided to OpenCost.<br />e.g., "Pricebook" if derived from PriceBook CRs. |  | Optional: \{\} <br /> |




#### Lifecycle



Lifecycle defines lifecycle behavior for subscriptions



_Appears in:_
- [OfferingSpec](#offeringspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `onParentDeactivate` _[ParentDeactivateAction](#parentdeactivateaction)_ | OnParentDeactivate toggles whether subscriptions to this offering should be deactivated when their parent subscription is deactivated<br />- Deactivate: this subscription also deactivates.<br />- Orphan: this subscription stays active independently, while retaining the parent reference for traceability. | Deactivate | Enum: [Deactivate Orphan] <br /> |
| `allowOverride` _boolean_ | AllowOverride allows the subscription to override the lifecycle settings |  | Optional: \{\} <br /> |


#### Margins



Margins defines pricing adjustments. AbsoluteMicros and FactorMilli are
mutually exclusive — pick one mode per meter. Both must be non-negative: a
negative margin would drive the per-unit price (and thus the usage charge)
below zero, which usage meters don't support. Express a discount with a
factorMilli below 1000 (e.g. 980 = 0.98x), not a negative absoluteMicros.



_Appears in:_
- [Meter](#meter)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `absoluteMicros` _integer_ | AbsoluteMicros is an additive margin in micro-currency units (10^-6 of the currency)<br />1,000,000 micros = 1.00 currency unit<br />Example: 0.02 cents = 0.0002 currency units = 200 micros |  | Optional: \{\} <br /> |
| `factorMilli` _integer_ | FactorMilli is a multiplicative factor in milli-units<br />1000 = 1.000x, 1020 = 1.020x (adds 2%), 980 = 0.980x (discount 2%) |  | Optional: \{\} <br /> |


#### Meter



Meter defines pricing adjustments for a specific meter



_Appears in:_
- [Pricing](#pricing)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `name` _[MeterName](#metername)_ | Name is the name of the meter along with unit (e.g., "cpuHour", "ramGbHour"). |  | Enum: [subscription cpuHour gpuHour ramGbHour pvGbHour networkGb] <br />Required: \{\} <br /> |
| `margins` _[Margins](#margins)_ | Margins adjusts the price derived from raw usage for this meter.<br />You can specify either:<br />- absoluteMicros: an additive margin in micro-currency units (10^-6 of the currency), or<br />- factorMilli: a multiplicative factor in milli-units (1000 = 1.000x, 1020 = 1.020x). |  | Optional: \{\} <br /> |


#### MeterName

_Underlying type:_ _string_

MeterName defines the name of a usage meter for pricing adjustments

_Validation:_
- Enum: [subscription cpuHour gpuHour ramGbHour pvGbHour networkGb]

_Appears in:_
- [CostMetric](#costmetric)
- [Meter](#meter)
- [ResolvedMeter](#resolvedmeter)

| Field | Description |
| --- | --- |
| `subscription` |  |
| `cpuHour` |  |
| `gpuHour` |  |
| `ramGbHour` |  |
| `pvGbHour` |  |
| `networkGb` | MeterNetworkGB bills total data transferred (transfer + receive) per GiB.<br />No time dimension — the rate is per-GB, not per-GB-hour — hence no "Hour".<br /> |


#### ObjectReference







_Appears in:_
- [Compatibility](#compatibility)
- [SubscriptionParent](#subscriptionparent)
- [SubscriptionSpec](#subscriptionspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `name` _string_ |  |  | Required: \{\} <br /> |
| `namespace` _string_ | Namespace of the referenced object. Must be set explicitly — references are<br />never resolved against the referrer's namespace, so the same reference always<br />means the same object no matter where it is authored. MinLength guards against<br />an empty string, which +required alone would accept. |  | MinLength: 1 <br />Required: \{\} <br /> |


#### Offering



Offering describes a cost driving entity
It owns the rules for how the base cost for that entity is collected and calculated





| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `apiVersion` _string_ | `finops.stakater.com/v1alpha1` | | |
| `kind` _string_ | `Offering` | | |
| `metadata` _[ObjectMeta](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#objectmeta-v1-meta)_ | Refer to Kubernetes API documentation for fields of `metadata`. |  |  |
| `spec` _[OfferingSpec](#offeringspec)_ |  |  |  |
| `status` _[OfferingStatus](#offeringstatus)_ |  |  |  |


#### OfferingSpec



OfferingSpec defines the desired state of Offering.



_Appears in:_
- [Offering](#offering)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `pricing` _[Pricing](#pricing)_ | Pricing specifies how the price for this offering is calculated |  | Required: \{\} <br /> |
| `compatibility` _[Compatibility](#compatibility)_ | Compatibility can be used for ensuring that any subscription created for this offering<br />has the required offerings in its parents or siblings |  | Optional: \{\} <br /> |
| `lifecycle` _[Lifecycle](#lifecycle)_ | Lifecycle defines how subscriptions to this offering behave during certain lifecycle events |  | Optional: \{\} <br /> |


#### OfferingStatus



OfferingStatus defines the observed state of Offering.



_Appears in:_
- [Offering](#offering)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `resolvedPricing` _[ResolvedPricing](#resolvedpricing)_ | ResolvedPricing contains the effective pricing derived from the offering spec |  | Optional: \{\} <br /> |
| `conditions` _[Condition](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#condition-v1-meta) array_ | Conditions represent the latest available observations of the Offering's state |  | Optional: \{\} <br /> |
| `ready` _[ConditionStatus](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#conditionstatus-v1-meta)_ | Ready indicates whether the offering is ready to be subscribed to (i.e., all required offerings are present and no circular dependencies detected) |  |  |


#### OnPremOptions



OnPremOptions defines On-Premise specific options.



_Appears in:_
- [FinOpsProviderSpec](#finopsproviderspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `pricingModelSource` _string_ | PricingModelSource indicates how the pricing model is provided to OpenCost.<br />e.g., "Pricebook" if derived from PriceBook CRs. |  | Optional: \{\} <br /> |


#### ParentDeactivateAction

_Underlying type:_ _string_

ParentDeactivateAction defines the behavior when a parent subscription is deactivated.

_Validation:_
- Enum: [Deactivate Orphan]

_Appears in:_
- [Lifecycle](#lifecycle)
- [SubscriptionLifecycle](#subscriptionlifecycle)

| Field | Description |
| --- | --- |
| `Deactivate` |  |
| `Orphan` |  |


#### PriceBook



PriceBook is the Schema for the pricebooks API





| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `apiVersion` _string_ | `finops.stakater.com/v1alpha1` | | |
| `kind` _string_ | `PriceBook` | | |
| `metadata` _[ObjectMeta](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#objectmeta-v1-meta)_ | Refer to Kubernetes API documentation for fields of `metadata`. |  |  |
| `spec` _[PriceBookSpec](#pricebookspec)_ |  |  |  |
| `status` _[PriceBookStatus](#pricebookstatus)_ |  |  |  |


#### PriceBookSpec



PriceBookSpec defines the desired state of PriceBook



_Appears in:_
- [PriceBook](#pricebook)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `currency` _string_ | The base currency for financial reporting and calculations (e.g., EUR, USD). |  | Pattern: `^[A-Z]\{3\}$` <br />Required: \{\} <br /> |
| `valuationMode` _string_ | The mode of valuation - either 'currency' for direct monetary rates or 'percent' for weighted scoring. |  | Enum: [currency percent] <br />Required: \{\} <br /> |
| `rates` _[PriceRates](#pricerates)_ | Rates used for valuation in 'currency' mode. Defines cost per unit of resource. Required if valuationMode is 'currency'. |  | Optional: \{\} <br /> |


#### PriceBookStatus



PriceBookStatus defines the observed state of PriceBook



_Appears in:_
- [PriceBook](#pricebook)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `active` _boolean_ | Active indicates whether this PriceBook instance is currently designated as the active one<br />used for pricing calculations. This field is managed by the operator. |  | Optional: \{\} <br /> |
| `ready` _[ConditionStatus](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#conditionstatus-v1-meta)_ | Ready indicates whether this PriceBook's rates are valid and it is usable<br />for pricing resolution. Managed by the operator. |  | Optional: \{\} <br /> |
| `observedGeneration` _integer_ | ObservedGeneration reflects the generation of the most recently observed spec. |  | Optional: \{\} <br /> |
| `conditions` _[Condition](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#condition-v1-meta) array_ | Conditions represent the latest available observations of the PriceBook's state. |  | Optional: \{\} <br /> |
| `activePricing` _object (keys:string, values:string)_ | ActivePricing mirrors the OpenCost custom-pricing document (default.json)<br />this PriceBook has applied to OpenCost. Populated only on the active, ready<br />PriceBook (the one driving OpenCost); nil on every other PriceBook.<br />Managed by the operator. |  | Optional: \{\} <br /> |


#### PriceRates



PriceRates defines the cost rates for different resources. Each rate is a
non-negative decimal string (e.g. "0.031"); empty means "unset". The pattern
`^([0-9]+(\.[0-9]+)?)?$` rejects malformed values at admission while allowing
empty.



_Appears in:_
- [PriceBookSpec](#pricebookspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `cpuHour` _string_ | Cost per vCPU-hour (e.g., 0.031). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |
| `spotCPUHour` _string_ | Cost per vCPU-hour (e.g., 0.031). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |
| `ramGbHour` _string_ | Cost per GB-hour of RAM (e.g., 0.004). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |
| `spotRAMGbHour` _string_ | Cost per GB-hour of spotRAM (e.g., 0.004). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |
| `pvGbHour` _string_ | Cost per GB-hour of Persistent Volume (e.g., 0.00012). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |
| `gpuHour` _string_ | Cost per GPU-hour (e.g., 1.8). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |
| `networkGiB` _string_ | Cost per GiB of network data transferred (e.g., 0.09). |  | Pattern: `^([0-9]+(\.[0-9]+)?)?$` <br />Optional: \{\} <br /> |


#### Pricing



Pricing defines pricing rules for the offering



_Appears in:_
- [OfferingSpec](#offeringspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `resourcePricing` _[Meter](#meter) array_ | ResourcePricing defines per-meter pricing adjustments applied to raw usage.<br />Each meter can optionally define:<br />- includedUsage: an amount of usage included for free per subscription (same unit as the meter)<br />- margins: either an absolute add-on (in micro-currency) or a multiplicative factor (in milli-units) |  | Optional: \{\} <br /> |
| `subscriptionFee` _[SubscriptionFee](#subscriptionfee)_ | SubscriptionFee defines the recurring fee charged for the subscription being active,<br />independent of resource usage |  | Optional: \{\} <br /> |


#### ResolvedIncludedUsage



ResolvedIncludedUsage contains the resolved included usage with its unit of measurement



_Appears in:_
- [ResolvedMeter](#resolvedmeter)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `value` _integer_ | Value is the amount of free usage included per subscription |  |  |
| `unit` _string_ | Unit is the unit of measurement (e.g., "GbHour", "CoreHour") |  |  |


#### ResolvedMeter



ResolvedMeter contains the effective per-unit price for a specific meter



_Appears in:_
- [ResolvedPricing](#resolvedpricing)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `name` _[MeterName](#metername)_ | Name is the meter name (e.g., "cpuHour", "ramGbHour") |  | Enum: [subscription cpuHour gpuHour ramGbHour pvGbHour networkGb] <br />Required: \{\} <br /> |
| `unitPriceMicros` _integer_ | UnitPriceMicros is the effective per-unit price in micro-currency units (10^-6) |  |  |
| `includedUsage` _[ResolvedIncludedUsage](#resolvedincludedusage)_ | IncludedUsage is the free usage included per subscription for this meter |  | Optional: \{\} <br /> |


#### ResolvedPricing



ResolvedPricing contains the effective pricing that consumers see.
It is derived from the offering spec and stamped on status during reconciliation.



_Appears in:_
- [OfferingStatus](#offeringstatus)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `resolvedAt` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | ResolvedAt is the timestamp when pricing was last resolved |  |  |
| `meters` _[ResolvedMeter](#resolvedmeter) array_ | Meters contains per-meter resolved unit prices after margins are applied.<br />Empty when no resource pricing is configured. |  |  |
| `subscriptionFee` _[SubscriptionFee](#subscriptionfee)_ | SubscriptionFee contains the resolved subscription fee, if configured |  | Optional: \{\} <br /> |


#### Subscription



Subscription is the Schema for the subscriptions API.





| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `apiVersion` _string_ | `finops.stakater.com/v1alpha1` | | |
| `kind` _string_ | `Subscription` | | |
| `metadata` _[ObjectMeta](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#objectmeta-v1-meta)_ | Refer to Kubernetes API documentation for fields of `metadata`. |  |  |
| `spec` _[SubscriptionSpec](#subscriptionspec)_ |  |  |  |
| `status` _[SubscriptionStatus](#subscriptionstatus)_ |  |  |  |


#### SubscriptionFee



SubscriptionFee defines the recurring fee charged for the subscription being active,
independent of resource usage.

Billing model:
- The fee accrues over time in discrete "ticks" of length `period`.
- Each tick contributes `priceMicros` to the total.
- Ticks are aligned according to `tickAlignment`.

Tick alignment:
  - ActivatedAt: ticks start at status.activatedAt (tick boundaries are: activatedAt + N*period).
    Best for per-subscription billing cycles (common for add-ons).
  - HourBoundary / DayBoundary / MonthBoundary: ticks align to wall-clock boundaries.
    Best for synchronized billing windows across subscriptions (common for reporting).

Charging rule (deterministic per time window):
For a time bucket [start, endExclusive), the subscription fee charged in that bucket is:

	ticks(t) = number of full tick boundaries strictly before time t
	feeInBucket = priceMicros * (ticks(endExclusive) - ticks(start))

This ensures exports are idempotent: the same [start, endExclusive) always yields the same fee.

Minimum commitment (minPeriods):
  - minPeriods defines the minimum number of periods to bill once the subscription becomes active.
  - If the subscription deactivates before minPeriods have elapsed, the remaining periods are billed
    as an adjustment at deactivation time, so the total billed periods is at least minPeriods.

All monetary values are expressed in micro-currency units (10^-6 of the currency).



_Appears in:_
- [Pricing](#pricing)
- [ResolvedPricing](#resolvedpricing)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `period` _string_ | Period is the tick interval. Its interpretation depends on tickAlignment:<br />  - ActivatedAt: a Go duration string (e.g., "1h", "30m", "24h").<br />  - HourBoundary: an integer number of hours (e.g., "1", "2").<br />  - DayBoundary: an integer number of days (e.g., "1", "7").<br />  - MonthBoundary: an integer number of months (e.g., "1", "3", "12"). |  |  |
| `tickAlignment` _[TickAlignment](#tickalignment)_ | TickAlignment defines where tick boundaries occur.<br />ActivatedAt: ticks start at status.activatedAt (tick boundaries are: activatedAt + N*period).<br />Best for per-subscription billing cycles (common for add-ons).<br />HourBoundary / DayBoundary / MonthBoundary: ticks align to wall-clock boundaries.<br />Best for synchronized billing windows across subscriptions (common for reporting).<br />For boundary-aligned modes, the first tick after activation covers a partial period<br />and is prorated: charge = priceMicros * actualDuration / periodDuration.<br />For MonthBoundary, the period duration denominator is a fixed 365.25/12 days (30.4375 days). |  | Enum: [ActivatedAt HourBoundary DayBoundary MonthBoundary] <br /> |
| `minPeriods` _integer_ | MinPeriods is the minimum number of full tick periods before deletion is allowed.<br />The collection job keeps the subscription finalizer until at least minPeriods ticks<br />have elapsed since activation. The subscription continues accruing charges normally<br />until the finalizer is removed. |  | Minimum: 1 <br />Optional: \{\} <br /> |
| `priceMicros` _integer_ | PriceMicros is the price per tick, in micro-currency units |  | Minimum: 1 <br />Required: \{\} <br /> |


#### SubscriptionLifecycle







_Appears in:_
- [SubscriptionSpec](#subscriptionspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `onParentDeactivate` _[ParentDeactivateAction](#parentdeactivateaction)_ | OnParentDeactivate controls what happens when the parent subscription deactivates:<br />- Deactivate: this subscription also deactivates.<br />- Orphan: this subscription stays active independently, while retaining the parent reference for traceability.<br />Orphan only detaches the parent lifecycle link; compatibility requirements are still enforced.<br />An orphan whose required offering was covered only by the now-deactivated parent (and by no<br />active sibling) is still deactivated, because keeping it active would violate the requirement. | Deactivate | Enum: [Deactivate Orphan] <br /> |
| `targetRef` _[TargetReference](#targetreference)_ | TargetRef ties the lifecycle of the subscription to a target resource.<br />The subscription will not activate until the target status is Ready.<br />When the target is deleted, the subscription will be deactivated. |  | Optional: \{\} <br /> |


#### SubscriptionParent







_Appears in:_
- [SubscriptionSpec](#subscriptionspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `subscriptionRef` _[ObjectReference](#objectreference)_ | SubscriptionRef is a reference to the parent subscription. |  | Required: \{\} <br /> |


#### SubscriptionSpec



SubscriptionSpec defines the desired state of Subscription.
A Subscription creates a binding to an Offering, starting the clock and instantiating the offering.
Effectively it starts consuming the cost-driving entity from a billing perspective.

offeringRef and parent are immutable: both determine what the subscription is
billed for and which subscriptions provide its compatibility coverage, and a
subscription's activation is a billing epoch that cannot be re-pointed.



_Appears in:_
- [Subscription](#subscription)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `offeringRef` _[ObjectReference](#objectreference)_ | OfferingRef is the reference to the Offering which is being subscribed to. |  | Required: \{\} <br /> |
| `parent` _[SubscriptionParent](#subscriptionparent)_ | Parent is an optional reference to a parent subscription for traceability.<br />For example, a storage subscription attached to a VM would reference the VM subscription. |  | Optional: \{\} <br /> |
| `usageSources` _[UsageSource](#usagesource) array_ | UsageSources defines from where the data for the resource usage of this subscription comes. |  | Optional: \{\} <br /> |
| `lifecycle` _[SubscriptionLifecycle](#subscriptionlifecycle)_ | Lifecycle allows overriding lifecycle behavior if the Offering permits it.<br />If both parent and targetRef are set:<br />- activation requires BOTH (parent active AND target Ready)<br />- deactivation happens if EITHER stops applying, except parent deactivation is ignored when onParentDeactivate=Orphan<br />Note: onParentDeactivate=Orphan only governs the parent lifecycle link. It does not<br />exempt the subscription from its offering's compatibility requirements: if the deactivating<br />parent was the only active provider of a required offering, the subscription is still<br />deactivated for the coverage gap. |  | Optional: \{\} <br /> |


#### SubscriptionStatus



SubscriptionStatus defines the observed state of Subscription.
Non-active subscriptions are ignored by scrape jobs.
A subscription becomes active when:
- parent.SubscriptionRef is set and the parent is active, and/or
- targetRef is set and the target is Ready.
Unset references are ignored. If neither reference is set, the subscription activates after spec validation.



_Appears in:_
- [Subscription](#subscription)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `ready` _[ConditionStatus](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#conditionstatus-v1-meta)_ | Ready indicates whether the subscription is active and ready. |  |  |
| `activatedAt` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | ActivatedAt is the time when the subscription became active. |  | Optional: \{\} <br /> |
| `deactivatedAt` _[Time](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#time-v1-meta)_ | DeactivatedAt is the time when the subscription was deactivated. |  | Optional: \{\} <br /> |
| `compatibilityRoot` _string_ | CompatibilityRoot is the metadata.uid of this subscription's root ancestor,<br />resolved once by the controller. It identifies the connected family used<br />for compatibility coverage. |  | Optional: \{\} <br /> |
| `costs` _[CostBucket](#costbucket) array_ | Costs contains rolling cost summaries for the current hour, day, and month.<br />When populated, contains exactly 3 entries — one per granularity.	// +optional |  |  |
| `conditions` _[Condition](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.30/#condition-v1-meta) array_ | Conditions represent the latest available observations of the Subscription's state. |  | Optional: \{\} <br /> |


#### TargetReference







_Appears in:_
- [SubscriptionLifecycle](#subscriptionlifecycle)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `apiVersion` _string_ | APIVersion is the API version of the target resource. |  |  |
| `kind` _string_ | Kind is the kind of the target resource. |  |  |
| `namespace` _string_ | Namespace is the namespace of the target resource. |  | Optional: \{\} <br /> |
| `name` _string_ | Name is the name of the target resource. |  |  |


#### TickAlignment

_Underlying type:_ _string_

TickAlignment defines where tick boundaries occur for subscription fee billing.

_Validation:_
- Enum: [ActivatedAt HourBoundary DayBoundary MonthBoundary]

_Appears in:_
- [SubscriptionFee](#subscriptionfee)

| Field | Description |
| --- | --- |
| `ActivatedAt` | ActivatedAt: ticks start at status.activatedAt (tick boundaries are: activatedAt + N*period).<br />Best for per-subscription billing cycles (common for add-ons).<br /> |
| `HourBoundary` | HourBoundary ticks align to wall-clock hour boundaries (e.g., 1:00, 2:00, etc.).<br /> |
| `DayBoundary` | DayBoundary ticks align to wall-clock day boundaries (e.g., 1 calender day).<br /> |
| `MonthBoundary` | MonthBoundary ticks align to wall-clock month boundaries (e.g., 1st of each month).<br /> |


#### UsageSource







_Appears in:_
- [SubscriptionSpec](#subscriptionspec)

| Field | Description | Default | Validation |
| --- | --- | --- | --- |
| `resourceType` _string_ | ResourceType is the type of resource to track (e.g., Deployment, StatefulSet, Pod). |  | Enum: [Deployment StatefulSet Pod DaemonSet Job CronJob ReplicaSet] <br /> |
| `name` _string_ | Name is the name of the specific resource instance. |  | Optional: \{\} <br /> |
| `namespace` _string_ | Namespace is the namespace of the resource. |  | Optional: \{\} <br /> |


