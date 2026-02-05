# PM Notification Analyzer - Administrator Guide

## Overview

This guide covers deployment, configuration, tenant management, security, monitoring, and GDPR compliance for administrators operating the PM Notification Analyzer on SAP BTP.

---

## Table of Contents

1. [Deployment](#deployment)
2. [Configuration](#configuration)
3. [Tenant Management](#tenant-management)
4. [Security Administration](#security-administration)
5. [Monitoring & Health Checks](#monitoring--health-checks)
6. [GDPR Compliance](#gdpr-compliance)
7. [Database Administration](#database-administration)
8. [Alert Management](#alert-management)
9. [QMS Integration](#qms-integration)
10. [Troubleshooting](#troubleshooting)

---

## Deployment

### Prerequisites

- SAP BTP subaccount with Cloud Foundry enabled
- CF CLI installed and authenticated
- MTA Build Tool (mbt) installed
- Required BTP entitlements:
  - XSUAA (application plan)
  - PostgreSQL (trial or standard)
  - Destination Service
  - Connectivity Service
  - HTML5 Application Repository
  - SAP Build Work Zone (standard)
  - SaaS Provisioning Service (application plan)

### Build & Deploy

```bash
# Build the MTA archive
cd pm-analyzer
mbt build -p=cf

# Deploy to BTP
cf login -a <api-endpoint> -o <org> -s <space>
cf deploy mta_archives/pm-notification-analyzer_2.1.0.mtar
```

### Post-Deployment

1. **Create Destination**: Configure `SAP_PM_SYSTEM` destination in BTP cockpit
2. **Assign Role Collections**: Assign `PM_Analyzer_Viewer`, `PM_Analyzer_Editor`, `PM_Analyzer_Auditor`, or `PM_Analyzer_Admin` to users
3. **Verify Health**: Check `https://<app-url>/health/deep`

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_TYPE` | `sqlite` or `postgresql` | Auto-detected |
| `DATABASE_URL` | PostgreSQL connection string | From VCAP_SERVICES |
| `PG_POOL_MAX` | Max PostgreSQL connections | `10` |
| `FLASK_DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARN, ERROR) | `INFO` |
| `LOG_FORMAT` | `text` or `json` (SAP Application Logging) | `text` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `*` |
| `AUTH_ENABLED` | Enable authentication | `true` |
| `CLERK_SECRET_KEY` | Clerk authentication key | - |
| `GOOGLE_API_KEY` | Google Gemini API key for AI analysis | - |
| `ENTITLEMENT_ENFORCEMENT` | Enable plan enforcement | `true` |
| `SAP_ODATA_URL` | SAP system OData endpoint | From destination |
| `SAP_CONNECTION_TYPE` | `odata`, `rfc`, or `rest` | `odata` |
| `QMS_PROVIDER` | QMS connector (`veeva_vault`, `mastercontrol`, `sharepoint`, `sap_qm`) | - |
| `TENANT_ID` | Default tenant ID for dev mode | - |

### SAP Destination Configuration

In the BTP cockpit, create a destination named `SAP_PM_SYSTEM`:

| Property | Value |
|----------|-------|
| **Name** | SAP_PM_SYSTEM |
| **Type** | HTTP |
| **URL** | https://your-sap-system:port/sap/opu/odata/sap/API_MAINTNOTIFICATION |
| **Authentication** | BasicAuthentication (or OAuth2SAMLBearerAssertion) |
| **ProxyType** | Internet (or OnPremise for Cloud Connector) |

---

## Tenant Management

### Subscription Plans

| Plan | Users | Notifications/mo | Features |
|------|-------|-------------------|----------|
| **Basic** | 10 | 5,000 | Analysis, Quality Scoring |
| **Professional** | 50 | 25,000 | + Reliability, Reporting, Alerts |
| **Enterprise** | Unlimited | Unlimited | + FDA Compliance, QMS, API Access |

### API Endpoints

```bash
# List all tenants
GET /api/tenants

# Get tenant details with usage
GET /api/tenants/{tenant_id}

# Update tenant plan
PUT /api/tenants/{tenant_id}/plan
Body: { "plan": "professional" }

# Get tenant usage and entitlements
GET /api/tenants/{tenant_id}/usage
```

### SaaS Registry Callbacks

These are called automatically by SAP BTP:

| Callback | Method | Path |
|----------|--------|------|
| Subscribe | PUT | `/api/tenant/callback/{tenantId}` |
| Unsubscribe | DELETE | `/api/tenant/callback/{tenantId}` |
| Dependencies | GET | `/api/tenant/callback/dependencies` |

---

## Security Administration

### Role Collections

| Role Collection | Scopes | Use Case |
|----------------|--------|----------|
| `PM_Analyzer_Viewer` | Read | View-only access to dashboards |
| `PM_Analyzer_Editor` | Read, Write | Create/update notifications, run analysis |
| `PM_Analyzer_Auditor` | Read, AuditRead | Access audit trail and compliance |
| `PM_Analyzer_Admin` | Read, Write, Admin | Full system administration |

### Rate Limiting

Default limits per user/IP per minute:

| Endpoint Pattern | Limit |
|-----------------|-------|
| `/api/analyze` | 10 req/min |
| `/api/chat` | 20 req/min |
| `/api/*` (general) | 100 req/min |

Override via environment:
```bash
RATE_LIMIT_DEFAULT=100
RATE_LIMIT_ANALYZE=10
```

### API Key Management

```bash
# List API keys
GET /api/security/api-keys

# Create new API key
POST /api/security/api-keys
Body: { "name": "integration-key", "scopes": ["read", "analyze"] }

# Revoke API key
DELETE /api/security/api-keys/{key_id}
```

### IP Whitelisting

```bash
# List whitelist entries
GET /api/security/ip-whitelist

# Add IP range
POST /api/security/ip-whitelist
Body: { "ip": "10.0.0.0/8", "description": "Corporate network" }

# Remove IP
DELETE /api/security/ip-whitelist/{entry_id}
```

### Security Audit Log

```bash
# Query security events
GET /api/security/audit-log?event_type=auth.login.failure&limit=100
```

---

## Monitoring & Health Checks

### Health Endpoints

| Endpoint | Purpose | Auth Required |
|----------|---------|--------------|
| `GET /health` | Basic health (load balancer) | No |
| `GET /health/live` | Liveness probe (is process alive?) | No |
| `GET /health/ready` | Readiness probe (can serve traffic?) | No |
| `GET /health/deep` | Deep check (DB, SAP, QMS, LLM) | No |

### Deep Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2026-02-05T12:00:00Z",
  "version": "2.1.0",
  "checks": {
    "database": { "status": "healthy", "latency_ms": 2.5, "type": "postgresql" },
    "llm": { "status": "configured", "provider": "google_generativeai" },
    "sap": { "status": "configured", "connection_type": "odata" },
    "qms": { "status": "not_configured" }
  }
}
```

### Request Metrics

```bash
GET /api/monitoring/metrics
```

Returns:
- Total requests and error rate
- Requests per second
- Status code distribution
- Per-endpoint latency (avg, min, max)
- Top endpoints by request count

### Structured Logging

Set `LOG_FORMAT=json` for SAP Application Logging Service compatibility. Each log entry includes:
- Timestamp, level, message
- Correlation ID (for request tracing)
- Tenant ID
- BTP instance information

---

## GDPR Compliance

### Data Subject Requests

```bash
# Create a data subject request
POST /api/gdpr/requests
Body: { "request_type": "access", "subject_email": "user@example.com" }

# List pending requests
GET /api/gdpr/requests?status=pending

# Execute a request (access export or erasure)
POST /api/gdpr/requests/{id}/execute
```

### Request Types

| Type | GDPR Article | Action |
|------|-------------|--------|
| `access` | Art. 15 | Export all personal data as JSON |
| `erasure` | Art. 17 | Pseudonymize personal identifiers |
| `portability` | Art. 20 | Export data as CSV |
| `rectification` | Art. 16 | Update incorrect data |
| `restriction` | Art. 18 | Restrict processing of data |

### Self-Service Export

Users can export their own data:
```bash
GET /api/gdpr/export              # JSON format
GET /api/gdpr/export?format=csv   # CSV format
```

### Consent Management

```bash
# Record consent
POST /api/gdpr/consent
Body: { "purpose": "ai_analysis", "granted": true }

# View consent records
GET /api/gdpr/consent

# Revoke consent
POST /api/gdpr/consent/ai_analysis/revoke
```

### Data Retention Policies

```bash
# Set retention policy
POST /api/gdpr/retention
Body: { "data_type": "security_audit_log", "retention_days": 365, "auto_delete": true }

# View policies
GET /api/gdpr/retention
```

### Personal Data Inventory

```bash
GET /api/gdpr/data-inventory
```

Returns a map of all tables and columns containing personal data.

### Erasure Process

When processing an erasure request:
1. Personal identifiers (usernames, IDs) are replaced with pseudonyms (`ERASED-xxxxxxxx`)
2. Technical maintenance data is preserved (referential integrity maintained)
3. Consent records are deleted
4. Security audit log references are pseudonymized
5. An audit entry is created documenting the erasure

---

## Database Administration

### Migration Management

```bash
cd pm-analyzer/backend

# Check current migration state
alembic current

# Run pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Generate new migration
alembic revision --autogenerate -m "description"
```

### PostgreSQL Connection

The app auto-detects PostgreSQL from:
1. `DATABASE_URL` environment variable
2. `VCAP_SERVICES` (BTP service binding)
3. Individual `PG_HOST`, `PG_PORT`, `PG_DATABASE`, `PG_USER`, `PG_PASSWORD` variables

Connection pooling is configured with `PG_POOL_MAX` (default: 10 connections).

### SQLite (Development Only)

For local development, the app uses SQLite at `backend/data/sap_pm.db`. Seed test data:
```bash
python scripts/seed_data.py
python scripts/seed_compliance_data.py
```

---

## Alert Management

### Predefined Rules

| Rule ID | Condition | Severity |
|---------|-----------|----------|
| `critical_quality` | Quality score < 50% | Critical |
| `low_quality` | Quality score 50-70% | High |
| `critical_reliability` | Reliability score < 40% | Critical |
| `high_failure_probability` | Failure probability > 70% | High |
| `overdue_maintenance` | Days overdue > 0 | High |
| `critical_equipment_down` | Type M1 + Priority 1 | Critical |
| `alcoa_violation` | ALCOA+ score < 80% | High |

### Custom Rules

```bash
POST /api/alert-rules
Body: {
  "id": "custom_pump_failure",
  "name": "Pump Failure Alert",
  "alert_type": "equipment_failure",
  "severity": "high",
  "conditions": [
    { "field": "equipment_type", "operator": "eq", "value": "PUMP" },
    { "field": "notification_type", "operator": "eq", "value": "M2" }
  ],
  "match_all": true,
  "actions": ["send_email"],
  "recipients": ["maintenance@example.com"]
}
```

### Test a Rule

```bash
POST /api/alert-rules/{rule_id}/test
Body: { "quality_score": 45, "equipment_id": "PUMP-001" }
```

---

## QMS Integration

### Configuration

Set the QMS provider and credentials:

```bash
# Veeva Vault
QMS_PROVIDER=veeva_vault
VEEVA_VAULT_URL=https://your-vault.veevavault.com
VEEVA_VAULT_USERNAME=api_user
VEEVA_VAULT_PASSWORD=********

# MasterControl
QMS_PROVIDER=mastercontrol
MASTERCONTROL_URL=https://your-instance.mastercontrol.com
MASTERCONTROL_API_KEY=********

# SharePoint
QMS_PROVIDER=sharepoint
SHAREPOINT_SITE_URL=https://tenant.sharepoint.com/sites/QMS
SHAREPOINT_CLIENT_ID=********
SHAREPOINT_CLIENT_SECRET=********

# SAP QM
QMS_PROVIDER=sap_qm
SAP_QM_ENABLED=true
```

### API Endpoints

```bash
GET  /api/qms/status                  # Connection status
POST /api/qms/test-connection         # Test connectivity
GET  /api/qms/sops                    # Search SOPs
GET  /api/qms/sops/for-notification   # Get SOPs for notification context
GET  /api/qms/documents/{id}          # Get document metadata
GET  /api/qms/documents/{id}/content  # Get document content
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|---------|
| 503 on /health/ready | Database unreachable | Check PostgreSQL binding in BTP cockpit |
| 403 TENANT_NOT_FOUND | SaaS Registry not configured | Verify saas-registry service binding |
| 403 FEATURE_NOT_AVAILABLE | Plan limit reached | Upgrade tenant plan |
| 429 USAGE_LIMIT_EXCEEDED | Notification quota exceeded | Upgrade plan or wait for reset |
| LLM analysis fails | Missing API key | Set GOOGLE_API_KEY environment variable |
| SAP data not syncing | Destination misconfigured | Verify SAP_PM_SYSTEM destination in BTP |

### Log Analysis

```bash
# View recent logs in CF
cf logs pm-analyzer-backend --recent

# Stream logs in real time
cf logs pm-analyzer-backend

# Filter for errors (with structured logging)
cf logs pm-analyzer-backend --recent | grep '"level":"ERROR"'
```

### Database Diagnostics

```bash
# Check database type and connection
curl https://<app-url>/health/deep | jq '.checks.database'

# Run migrations manually
cf ssh pm-analyzer-backend -c "cd app && python -m alembic upgrade head"
```

---

*PM Notification Analyzer v2.1.0 | Last updated: February 2026*
