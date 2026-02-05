# PM Notification Analyzer - Security & Architecture Whitepaper

**Version**: 2.1.0
**Classification**: Customer-Facing
**Last Updated**: February 2026

---

## Executive Summary

The PM Notification Analyzer is an AI-powered SaaS application deployed on SAP Business Technology Platform (BTP) that analyzes SAP Plant Maintenance notifications for data quality, equipment reliability, and regulatory compliance. This document describes the security architecture, data protection measures, and compliance certifications relevant to enterprise procurement decisions.

---

## 1. Architecture Overview

### 1.1 Deployment Model

```
┌──────────────────────────────────────────────────────────────────┐
│                     SAP Business Technology Platform              │
│                          (Cloud Foundry)                         │
│                                                                  │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────┐   │
│  │  Approuter   │──│   Frontend    │  │  SAP Build Work    │   │
│  │  (Node.js)   │  │  (SAPUI5/     │  │  Zone Integration  │   │
│  │              │  │   Fiori)      │  │                    │   │
│  └──────┬───────┘  └───────────────┘  └────────────────────┘   │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────┐           │
│  │              Backend (Python/Flask)                │           │
│  │  ┌──────────┬──────────┬──────────┬────────────┐ │           │
│  │  │ Analysis │ Quality  │Reliabil. │ Compliance │ │           │
│  │  │ Service  │ Service  │ Service  │  Service   │ │           │
│  │  └──────────┴──────────┴──────────┴────────────┘ │           │
│  │  ┌──────────┬──────────┬──────────┬────────────┐ │           │
│  │  │ Security │Entitle.  │  GDPR    │ Monitoring │ │           │
│  │  │ Module   │Middleware│ Service  │  Module    │ │           │
│  │  └──────────┴──────────┴──────────┴────────────┘ │           │
│  └──────────────────────┬───────────────────────────┘           │
│                         │                                        │
│  ┌──────────┐  ┌───────┴────┐  ┌──────────────┐               │
│  │  XSUAA   │  │ PostgreSQL │  │  SaaS        │               │
│  │  (Auth)  │  │   (Data)   │  │  Registry    │               │
│  └──────────┘  └────────────┘  └──────────────┘               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │  SAP S/4HANA │   │  Google      │   │   QMS        │
   │  (PM/EAM)    │   │  Gemini AI   │   │  (Veeva,     │
   │              │   │              │   │   etc.)      │
   └──────────────┘   └──────────────┘   └──────────────┘
```

### 1.2 Component Responsibilities

| Component | Technology | Responsibility |
|-----------|-----------|---------------|
| **Approuter** | Node.js (@sap/approuter) | Authentication, CSRF protection, routing |
| **Frontend** | SAPUI5/Fiori | User interface, visualization |
| **Backend** | Python/Flask | Business logic, API layer |
| **PostgreSQL** | Managed service | Data persistence, tenant isolation |
| **XSUAA** | SAP service | Authentication, authorization, JWT tokens |
| **SaaS Registry** | SAP service | Multi-tenant subscription management |

---

## 2. Authentication & Authorization

### 2.1 Authentication Flow

```
User → Approuter → XSUAA (OAuth2) → JWT Token → Backend API
```

1. User accesses the application via browser
2. Approuter redirects to XSUAA for authentication
3. XSUAA authenticates against the configured IdP (SAP IAS, Azure AD, etc.)
4. JWT token issued with user identity, scopes, and tenant zone ID
5. Approuter forwards request with JWT to backend
6. Backend validates JWT signature and extracts claims

### 2.2 Authorization Model

**Role-Based Access Control (RBAC):**

| Role | Permissions |
|------|------------|
| **Viewer** | Read notifications, view dashboards |
| **Editor** | + Run analysis, create alerts, manage subscriptions |
| **Auditor** | + Access audit trail, export compliance reports |
| **Administrator** | + Manage tenants, users, security settings, GDPR requests |

**Scope Enforcement:**

```
$XSAPPNAME.Read           → Viewer
$XSAPPNAME.Write          → Editor
$XSAPPNAME.AuditRead      → Auditor
$XSAPPNAME.Admin          → Administrator
$XSAPPNAME.SAPIntegration → SAP system access
```

### 2.3 Token Security

- **Algorithm**: RS256 (RSA with SHA-256)
- **Token validity**: 12 hours (43200 seconds)
- **Verification**: Public key from XSUAA JWKS endpoint
- **Transport**: Bearer token in Authorization header over TLS

---

## 3. Data Protection

### 3.1 Encryption

| Layer | Method |
|-------|--------|
| **In transit** | TLS 1.2+ (enforced by Cloud Foundry) |
| **At rest** | AES-256 (PostgreSQL managed service encryption) |
| **API keys** | SHA-256 hashed (raw key never stored) |
| **Passwords** | Not stored (delegated to XSUAA/IdP) |

### 3.2 Multi-Tenant Data Isolation

- **Schema-per-tenant**: Each tenant gets a dedicated PostgreSQL schema
- **Tenant identification**: Zone ID extracted from JWT token
- **Cross-tenant access**: Prevented at middleware layer before reaching business logic
- **Tenant lifecycle**: Automated provisioning/deprovisioning via SaaS Registry callbacks

### 3.3 Personal Data Handling

Personal data is limited to:

| Table | Personal Fields | Purpose |
|-------|----------------|---------|
| QMEL | QMNAM (creator) | Notification attribution |
| CDHDR | USERNAME | Change document authorship |
| AFRU | ERNAM, ARBID | Time confirmation attribution |
| QMIH | ERNAM | Notification history authorship |

**GDPR measures:**
- Pseudonymization on erasure requests
- Self-service data export (JSON/CSV)
- Consent management with revocation support
- Configurable retention policies
- Personal data inventory endpoint

---

## 4. Network Security

### 4.1 Perimeter

- Application runs inside SAP BTP Cloud Foundry environment
- No direct internet-accessible database ports
- All traffic routed through Cloud Foundry router (TLS termination)
- CORS restricted to configured origins in production

### 4.2 SAP System Connectivity

| Path | Method |
|------|--------|
| **Cloud to on-premise** | SAP Cloud Connector + Connectivity Service |
| **Cloud to cloud** | Destination Service with OAuth2 tokens |
| **Authentication** | Basic Auth, OAuth2 SAML Bearer, or Principal Propagation |

### 4.3 API Security

| Protection | Implementation |
|-----------|---------------|
| **Rate limiting** | Sliding window per user/IP/endpoint |
| **IP whitelisting** | CIDR-based allowlist for admin endpoints |
| **API key auth** | For service-to-service communication |
| **CSRF protection** | Approuter CSRF token validation |
| **Input validation** | Server-side validation on all inputs |
| **SQL injection** | Parameterized queries (no string concatenation) |

---

## 5. Compliance

### 5.1 FDA 21 CFR Part 11

The application supports compliance with FDA 21 CFR Part 11 through:

| Requirement | Implementation |
|-------------|---------------|
| **Electronic signatures** | XSUAA-authenticated user identity on all changes |
| **Audit trail** | Complete change document history (CDHDR/CDPOS tables) |
| **Data integrity** | ALCOA+ quality scoring across all notifications |
| **Access control** | Role-based access with scope enforcement |
| **Record retention** | Configurable retention policies with auto-archival |

### 5.2 GDPR (EU General Data Protection Regulation)

| Article | Compliance Feature |
|---------|-------------------|
| Art. 6 | Consent management with purpose specification |
| Art. 7 | Consent withdrawal with immediate effect |
| Art. 13-14 | Personal data inventory and transparency |
| Art. 15 | Self-service data export endpoint |
| Art. 17 | Automated pseudonymization on erasure requests |
| Art. 20 | Data portability (JSON and CSV export) |
| Art. 25 | Privacy by design (data minimization) |
| Art. 28 | Tenant-level data processing agreements |
| Art. 30 | Processing activity records via audit log |
| Art. 32 | Encryption at rest and in transit |
| Art. 33 | Security audit logging for breach detection |

### 5.3 SOC 2 Alignment

The application's security controls align with SOC 2 Trust Services Criteria:

| Criteria | Controls |
|----------|---------|
| **Security** | XSUAA, RBAC, rate limiting, IP whitelisting, audit logging |
| **Availability** | Health checks, monitoring, auto-scaling capable |
| **Processing Integrity** | Input validation, data quality scoring, change tracking |
| **Confidentiality** | Tenant isolation, encryption, access controls |
| **Privacy** | GDPR compliance, consent management, data minimization |

---

## 6. AI/LLM Security

### 6.1 Data Sent to LLM

- Only notification text content and metadata is sent to Google Gemini
- No personal identifiers (usernames) are included in LLM prompts
- No credentials or security data is sent

### 6.2 AI Governance

| Control | Implementation |
|---------|---------------|
| **Usage logging** | All AI requests logged with governance module |
| **Rate limiting** | AI endpoints limited to prevent abuse |
| **Consent** | AI analysis requires explicit consent (GDPR Art. 6) |
| **Model configuration** | Temperature and model version controlled centrally |
| **Audit trail** | All AI interactions recorded for review |

---

## 7. Monitoring & Incident Response

### 7.1 Monitoring

| Metric | Collection |
|--------|-----------|
| **Request latency** | Per-endpoint p50/p95/p99 |
| **Error rates** | 4xx and 5xx status codes |
| **Database health** | Connection pool utilization, query latency |
| **Authentication failures** | Failed login attempts, expired tokens |
| **Tenant usage** | API calls, analyses performed, storage used |

### 7.2 Health Probes

| Probe | Endpoint | Purpose |
|-------|----------|---------|
| Liveness | `/health/live` | Is the process running? |
| Readiness | `/health/ready` | Can the app serve traffic? |
| Deep | `/health/deep` | Are all dependencies healthy? |

### 7.3 Security Audit Events

All security-relevant events are logged:
- Authentication successes and failures
- Authorization denials
- API key creation and revocation
- Rate limit violations
- GDPR request processing
- Configuration changes

### 7.4 Incident Response

1. **Detection**: Monitoring alerts on error rate spikes or health check failures
2. **Triage**: Correlation IDs enable full request tracing
3. **Containment**: IP blocking, session termination, rate limit adjustment
4. **Recovery**: Auto-scaling, database failover, deployment rollback
5. **Post-mortem**: Full audit trail for root cause analysis

---

## 8. Dependency Security

### 8.1 Supply Chain

| Measure | Implementation |
|---------|---------------|
| **Dependency scanning** | pip-audit in CI/CD pipeline |
| **SAST** | Bandit static analysis on every commit |
| **Version pinning** | Minimum versions specified in requirements.txt |
| **Runtime** | Python 3.12 (latest stable) |

### 8.2 Third-Party Services

| Service | Provider | Data Shared |
|---------|----------|------------|
| PostgreSQL | SAP BTP (managed) | All application data |
| XSUAA | SAP BTP (managed) | User identity tokens |
| Google Gemini | Google Cloud | Notification text (no PII) |
| QMS (optional) | Customer-selected | SOP queries |

---

## 9. Contact

For security inquiries or vulnerability reports, contact your SAP BTP subaccount administrator or the application support team.

---

*This document is intended for enterprise procurement and security review purposes.*
