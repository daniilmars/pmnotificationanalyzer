# SAP Connectivity Options - Evaluation & Architecture Guide

## Overview

The PM Notification Analyzer needs to read (and optionally write) SAP Plant Maintenance data: notifications (QMEL), work orders (AUFK), equipment (EQUI), functional locations, and change documents. This document evaluates every connectivity option, with specific attention to how each works under the **direct-sales SaaS model** (you operate the BTP subaccount, customers connect their SAP systems to it).

---

## Option Matrix

| # | Method | SAP System | Network | Auth | Implemented | Direct-Sales Compatible |
|---|--------|-----------|---------|------|-------------|------------------------|
| 1 | OData over Internet | S/4HANA Cloud | Public internet | OAuth 2.0 / Basic | Yes | Yes |
| 2 | OData via Cloud Connector | S/4HANA / ECC on-premise | TLS tunnel | Principal Propagation / Basic | Yes | Partially |
| 3 | RFC via Cloud Connector | ECC on-premise | TLS tunnel | SNC / Basic | Yes | Partially |
| 4 | SAP Integration Suite (CPI) | Any | Middleware | OAuth 2.0 | No | Yes |
| 5 | SAP API Management | Any | API Gateway | API Key / OAuth | No | Yes |
| 6 | Customer-hosted API Proxy | Any | Customer-managed | Varies | No | Yes |
| 7 | File / Batch Export | Any | Offline | N/A | No | Yes |

---

## Option 1: OData over Internet

### How it works

The application calls SAP OData APIs directly over HTTPS. The customer's SAP system exposes APIs on a public URL (standard for S/4HANA Cloud, possible for on-premise via SAP Web Dispatcher or reverse proxy).

```
PM Analyzer (BTP)  --HTTPS-->  SAP S/4HANA Cloud API endpoint
```

### SAP APIs used

| API | Protocol | Purpose |
|-----|----------|---------|
| API_MAINTNOTIFICATION | OData v2/v4 | Read/create maintenance notifications |
| API_MAINTENANCEORDER | OData v2/v4 | Read work orders |
| API_EQUIPMENT | OData v2/v4 | Equipment master data |
| API_FUNCTIONALLOCATION | OData v2/v4 | Functional location master |
| API_MEASURINGPOINT | OData v2/v4 | Measuring points and readings |

### Current implementation

The `sap_integration_service.py` already supports this via the `ConnectionType.ODATA` path. Configuration:

```
SAP_CONNECTION_TYPE=odata
SAP_ODATA_URL=https://customer-s4hc.s4hana.ondemand.com
SAP_ODATA_PATH=/sap/opu/odata/sap/
SAP_AUTH_TYPE=basic
```

On BTP, the Destination Service manages credentials. The destination is configured with `ProxyType: Internet`.

### Authentication options

| Method | Use Case | Setup Complexity |
|--------|----------|-----------------|
| Basic Authentication | Simple, quick setup | Low |
| OAuth 2.0 Client Credentials | System-to-system, no user context | Medium |
| OAuth 2.0 SAML Bearer | User propagation (audit trail shows real user) | High |
| Client Certificate (mTLS) | High-security environments | High |

### Pros

- Simplest architecture, no additional infrastructure
- Standard for S/4HANA Cloud customers
- No Cloud Connector installation required
- Works naturally with the direct-sales model (customer just provides URL + credentials)
- Full support for all OData operations (read, create, update)

### Cons

- Requires the SAP system to be internet-accessible
- Not available for most on-premise ECC systems without additional infrastructure
- Basic Auth sends credentials with every request
- OData v2 can be verbose for large datasets

### Suitability for direct-sales model

**Excellent.** The customer provides their S/4HANA Cloud URL and a communication arrangement. No tunnel into your subaccount required. Per-tenant destination configuration stores each customer's credentials separately.

### Customer setup steps

1. Create a Communication Arrangement in S/4HANA Cloud for the PM APIs
2. Generate a Communication User with appropriate authorizations
3. Provide the URL and credentials during onboarding (step `sap_connection`)

---

## Option 2: OData via Cloud Connector

### How it works

The customer installs SAP Cloud Connector on their network. It opens an outbound TLS tunnel to SAP BTP. The application routes OData requests through this tunnel to reach the on-premise SAP system.

```
PM Analyzer (BTP)  -->  Connectivity Service  -->  [TLS Tunnel]  -->  Cloud Connector  -->  SAP ECC/S4
```

### Current implementation

Fully supported. The `btp_config.py` detects `ProxyType: OnPremise` in the destination configuration and routes traffic through the Connectivity Service proxy:

```python
if dest_config.get('ProxyType') == 'OnPremise':
    conn_config = get_connectivity_config()
    env_config['SAP_PROXY_HOST'] = conn_config.get('onpremise_proxy_host', '')
    env_config['SAP_PROXY_PORT'] = str(conn_config.get('onpremise_proxy_port', ''))
```

The Destination Service configuration uses:

```yaml
Name: SAP_PM_SYSTEM
Type: HTTP
ProxyType: OnPremise
URL: http://sap-ecc.customer.local:8000
Authentication: PrincipalPropagation  # or BasicAuthentication
sap-client: 100
```

### Authentication options

| Method | Description |
|--------|-------------|
| Basic Authentication | User/password passed through tunnel |
| Principal Propagation | BTP user identity forwarded to SAP (requires trust setup) |
| SAP Logon Ticket | SSO ticket forwarded |

### Pros

- Works with any on-premise SAP system (ECC 6.0+, S/4HANA on-premise)
- No inbound firewall changes on customer side (outbound-only tunnel)
- SAP-supported, standard BTP pattern
- Supports Principal Propagation for user-level audit trails

### Cons

- Customer must install and maintain Cloud Connector
- **In the direct-sales model**: the customer's Cloud Connector connects to *your* BTP subaccount, requiring them to trust your infrastructure with a tunnel into their network
- Cloud Connector is an additional component to monitor and update
- Network latency depends on customer's internet connection
- Cloud Connector licenses may have cost implications for the customer

### Suitability for direct-sales model

**Problematic.** Enterprise customers in regulated industries (pharma, chemical) will be reluctant to open a Cloud Connector tunnel to a third-party subaccount. This is the core trust issue discussed earlier. In the traditional BTP Store model, the customer subscribes in their own subaccount and Cloud Connector stays within their trust boundary.

### When it still works

- Customers who already use BTP and understand Cloud Connector
- Customers with an existing trust relationship with you
- Smaller companies with less rigid security policies
- Proof-of-concept / pilot engagements

### Customer setup steps

1. Install SAP Cloud Connector on their network
2. Connect Cloud Connector to your BTP subaccount (requires subaccount ID and your permission)
3. Expose the SAP system's OData endpoints in Cloud Connector (virtual host mapping)
4. You create a Destination in your BTP cockpit pointing to the virtual host

---

## Option 3: RFC via Cloud Connector

### How it works

Same tunnel as Option 2, but uses SAP's native RFC protocol instead of OData. Calls BAPIs directly (e.g., `BAPI_ALM_NOTIF_GET_DETAIL`). Requires the `pyrfc` library and SAP NW RFC SDK on the BTP application.

```
PM Analyzer (BTP + pyrfc)  -->  Connectivity Service  -->  [TLS Tunnel]  -->  Cloud Connector  -->  SAP ECC (RFC)
```

### Current implementation

Supported in `sap_integration_service.py` via `ConnectionType.RFC`:

```python
from pyrfc import Connection
connection = Connection(
    ashost=config.ashost,
    sysnr=config.sysnr,
    client=config.client,
    user=config.user,
    passwd=config.passwd,
    lang=config.lang
)
result = connection.call('BAPI_ALM_NOTIF_GET_DETAIL', NOTIFICATION=notif_id)
```

### BAPIs used

| BAPI | Purpose |
|------|---------|
| BAPI_ALM_NOTIF_GET_DETAIL | Notification details with items, activities, tasks |
| BAPI_ALM_NOTIF_CREATE | Create new notification |
| BAPI_ALM_NOTIF_LIST | List notifications with selection criteria |
| BAPI_ALM_ORDER_GET_DETAIL | Work order details |
| BAPI_ALM_ORDER_MAINTAIN | Work order maintenance |
| BAPI_EQUI_GETDETAIL | Equipment master data |
| BAPI_TRANSACTION_COMMIT | Commit after write operations |
| CHANGEDOCUMENT_READ_ALL | Read change documents for audit trail |

### Pros

- Richest data access (BAPIs return more detail than OData in many cases)
- `CHANGEDOCUMENT_READ_ALL` only available via RFC (critical for audit trail)
- Well-established, mature interface
- Better performance for batch operations

### Cons

- Everything from Option 2 (Cloud Connector dependency), plus:
- `pyrfc` requires SAP NW RFC SDK (C library), which complicates the Docker/buildpack setup
- SAP NW RFC SDK has separate licensing
- RFC is not available on S/4HANA Cloud (only OData)
- Connection pooling is more complex than HTTP

### Suitability for direct-sales model

**Same trust issues as Option 2**, plus the added complexity of RFC SDK deployment. Only relevant for on-premise ECC customers who need deep data access (especially change documents).

---

## Option 4: SAP Integration Suite (Cloud Integration / CPI)

### How it works

SAP Integration Suite acts as middleware between your application and the customer's SAP system. The customer (or you) configures an integration flow (iFlow) in CPI that exposes a REST API. Your application calls CPI, and CPI connects to SAP using whatever method is available (OData, RFC, IDoc).

```
PM Analyzer (BTP)  --REST-->  SAP Integration Suite  --OData/RFC-->  Customer's SAP
```

### Architecture

This inverts the trust model. Instead of the customer connecting their Cloud Connector to your subaccount, the integration runs in the **customer's** Integration Suite tenant (or a shared one).

```
Your BTP Subaccount              Customer's BTP Subaccount
+-------------------+            +------------------------+
| PM Analyzer       |  --REST--> | Integration Suite      |
| (backend)         |            | (iFlow: PM Data API)   |
+-------------------+            +----------+-------------+
                                            |
                                  Cloud Connector / OData
                                            |
                                 +----------+-------------+
                                 | Customer's SAP System  |
                                 +------------------------+
```

### Pros

- **Solves the trust problem**: Cloud Connector stays in the customer's subaccount
- Customer controls what data is exposed through iFlow design
- Data transformation and filtering happen before data reaches your app
- Can aggregate data from multiple SAP systems
- Supports all SAP connectivity methods (OData, RFC, IDoc, JDBC)
- Integration Suite is a standard SAP product many enterprises already have

### Cons

- **Requires the customer to have SAP Integration Suite** (additional BTP subscription, ~EUR 3,000+/year)
- iFlow development and maintenance effort (either you provide a template or the customer builds it)
- Additional latency (extra hop through CPI)
- More complex troubleshooting (three systems instead of two)
- Not implemented in the current codebase

### Suitability for direct-sales model

**Very good, if the customer has Integration Suite.** This is the enterprise-grade answer to the trust problem. You provide a standard iFlow package, the customer deploys it in their tenant, and your app calls their CPI endpoint. Each customer's CPI URL is stored as a per-tenant configuration.

### Implementation effort

Medium. You would need to:
1. Build a standard iFlow (SAP Integration Suite content package) that exposes PM data as a REST API
2. Add a new connection type in `sap_integration_service.py` for CPI endpoints
3. Document the customer-side iFlow deployment process

---

## Option 5: SAP API Management

### How it works

The customer exposes their SAP APIs through SAP API Management (part of Integration Suite or standalone). API Management provides rate limiting, API key authentication, monitoring, and a standardized endpoint.

```
PM Analyzer (BTP)  --REST/OData-->  API Management (customer)  -->  SAP System
```

### Pros

- Customer controls API access through policies (rate limits, IP filtering, quotas)
- API keys are simpler than OAuth/Cloud Connector setup
- Built-in monitoring so the customer sees exactly what your app accesses
- Can proxy both cloud and on-premise SAP systems
- Works well with the direct-sales model (customer gives you an API key)

### Cons

- Requires the customer to have SAP API Management
- Does not fundamentally change the connectivity to the SAP backend (still needs OData/RFC underneath)
- API Management adds latency
- Not implemented in the current codebase

### Suitability for direct-sales model

**Good.** Gives the customer full visibility and control over API access. Your application just receives an API endpoint URL and an API key during onboarding. Simpler trust conversation than Cloud Connector.

### Implementation effort

Low. The existing OData code path works unchanged -- only the base URL and auth header differ. Add support for API key authentication in the destination configuration.

---

## Option 6: Customer-Hosted API Proxy

### How it works

For customers who don't have SAP Integration Suite or API Management, they can deploy a lightweight API proxy on their own infrastructure (or their own BTP subaccount). This proxy exposes a REST API that your application calls.

Options for the proxy:
- A simple Node.js or Python app deployed in the customer's BTP subaccount
- An nginx reverse proxy in the customer's DMZ
- An API gateway (Kong, AWS API Gateway, Azure APIM) in the customer's cloud

```
PM Analyzer (BTP)  --REST-->  Customer's API Proxy  -->  Customer's SAP System
```

### Pros

- Customer maintains full control over their data and network
- No dependency on SAP Integration Suite licensing
- You can provide a pre-built proxy application for easy deployment
- Works with any SAP system version

### Cons

- Additional component for the customer to deploy and maintain
- You need to build and maintain the proxy application
- No SAP support for the proxy layer
- Varying security postures depending on what the customer chooses

### Suitability for direct-sales model

**Good for cost-sensitive customers.** You could provide a turnkey "SAP PM Data Bridge" application that the customer deploys in their own BTP free-tier subaccount or on their own server. This keeps the trust boundary clean without requiring Integration Suite licensing.

### Implementation effort

Medium-High. You would need to:
1. Build a standalone proxy application with SAP connectivity (OData + optional RFC)
2. Package it for easy customer deployment (MTA, Docker, or standalone)
3. Define the REST API contract between PM Analyzer and the proxy
4. Handle authentication between your app and the proxy (mTLS, API keys, or OAuth)

---

## Option 7: File / Batch Export

### How it works

Instead of real-time API connectivity, the customer exports PM notification data from SAP as files (CSV, JSON, or IDoc/XML) and uploads them to the PM Notification Analyzer.

```
SAP System  --manual/scheduled export-->  File (CSV/JSON)  --upload-->  PM Analyzer
```

This could be:
- Manual upload through the PM Analyzer UI
- Scheduled ABAP job that writes to a shared location (SFTP, S3, Azure Blob)
- SAP standard IDoc output to a file interface

### Pros

- **Zero network connectivity** between your app and the customer's SAP system
- Works with any SAP version, any network topology
- No trust or security concerns -- the customer decides exactly what data to export
- Simplest option for pilots and proof-of-concept
- No Cloud Connector, Integration Suite, or API exposure required
- Works for customers with air-gapped or highly restricted SAP systems

### Cons

- Not real-time (batch only, typically daily or weekly)
- Customer must run the export process (unless automated via ABAP job)
- File format standardization required
- No interactive features (chat assistant can't query SAP live)
- Data freshness depends on export frequency
- Requires building a file import/upload feature (not yet implemented)

### Suitability for direct-sales model

**Excellent for getting started.** This is the lowest-barrier option. A customer can export 6 months of notification data as CSV, upload it, and immediately see the AI analysis, quality scoring, and reliability dashboards. No connectivity discussion needed. It can serve as the entry point before the customer commits to a real-time integration.

### Implementation effort

Medium. You would need to:
1. Define a standard CSV/JSON import format for notifications, equipment, and work orders
2. Build a file upload endpoint with validation and mapping
3. Add an SAP transaction or ABAP report for data export (provide to customers)
4. Optional: SFTP/S3 polling for automated scheduled imports

---

## Recommendation by Customer Profile

| Customer Profile | Recommended Option | Fallback |
|------------------|--------------------|----------|
| S/4HANA Cloud | **Option 1** (OData over Internet) | Option 5 (API Management) |
| S/4HANA on-premise, has Integration Suite | **Option 4** (Integration Suite) | Option 2 (Cloud Connector) |
| S/4HANA on-premise, no Integration Suite | **Option 6** (Customer API Proxy) | Option 7 (File Export) |
| ECC on-premise, has BTP experience | **Option 2** (Cloud Connector) | Option 7 (File Export) |
| ECC on-premise, no BTP | **Option 7** (File Export) | Option 6 (Customer API Proxy) |
| Pilot / Proof of Concept (any system) | **Option 7** (File Export) | Option 1 if cloud |
| Air-gapped / Highly regulated | **Option 7** (File Export) | Only option |

---

## Recommendation for Direct-Sales Development Priority

Given the direct-sales model (you operate the BTP subaccount), here is the recommended implementation priority:

### Priority 1: Already implemented

- **Option 1** (OData over Internet) -- works today via `sap_integration_service.py`
- **Option 2/3** (Cloud Connector) -- works today but has trust limitations

### Priority 2: Build next

- **Option 7** (File/Batch Import) -- removes the connectivity barrier entirely. Enables any customer to try the product with their real data in minutes. This is the single most impactful feature for direct-sales adoption.

### Priority 3: Build for enterprise customers

- **Option 4** (Integration Suite iFlow package) -- provides the trust-clean real-time connectivity that enterprise customers expect. Deliver this as a downloadable content package.

### Priority 4: Nice to have

- **Option 5** (API Management) -- minimal code change, just add API key auth support
- **Option 6** (Customer API Proxy) -- build if demand warrants it

---

## Current Implementation Status

| Component | File | Status |
|-----------|------|--------|
| OData connectivity | `backend/app/services/sap_integration_service.py` | Complete |
| RFC connectivity | `backend/app/services/sap_integration_service.py` | Complete (requires pyrfc) |
| BTP Destination Service | `backend/app/btp_config.py` | Complete |
| Cloud Connector proxy routing | `backend/app/btp_config.py:286-290` | Complete |
| Approuter SAP route | `approuter/xs-app.json` | Complete |
| Destination config in MTA | `mta.yaml:138-158` | Complete |
| Connectivity Service in MTA | `mta.yaml:160-165` | Complete |
| File/batch import | -- | Not implemented |
| Integration Suite iFlow | -- | Not implemented |
| API key authentication | -- | Not implemented |
| Per-tenant SAP destinations | -- | Not implemented (single destination only) |

### Key gap: Per-tenant destination management

The current architecture uses a single `SAP_PM_SYSTEM` destination shared across the application. For the direct-sales multi-tenant model, each tenant needs its own SAP connection configuration. This requires:

1. A tenant-level SAP configuration store (database table)
2. Onboarding flow that captures SAP connection details per tenant
3. Runtime destination resolution based on tenant context
4. Credential encryption at rest for stored SAP credentials

This is the most important infrastructure change needed regardless of which connectivity option a customer uses.
