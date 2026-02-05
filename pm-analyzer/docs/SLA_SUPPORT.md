# PM Notification Analyzer - Service Level Agreement & Support

**Version**: 1.0
**Effective Date**: February 2026

---

## 1. Service Level Objectives

### 1.1 Availability

| Plan | Monthly Uptime Target | Max Downtime/Month |
|------|----------------------|-------------------|
| **Basic** | 99.5% | ~3.6 hours |
| **Professional** | 99.7% | ~2.2 hours |
| **Enterprise** | 99.9% | ~43 minutes |

**Measurement**: Availability is measured by monitoring the `/health` endpoint from multiple regions at 1-minute intervals. A failed check is a check that returns a non-200 status code or does not respond within 10 seconds.

**Exclusions**:
- Scheduled maintenance windows (announced 48 hours in advance)
- SAP BTP platform-wide outages (covered by SAP BTP SLA)
- Force majeure events
- Customer-caused issues (misconfiguration, exceeded quotas)

### 1.2 Performance

| Metric | Target | Measurement |
|--------|--------|------------|
| **API response time (p95)** | < 500ms | All `/api/*` endpoints excluding `/api/analyze` and `/api/chat` |
| **AI analysis response** | < 15s | `/api/analyze` endpoint |
| **Chat response** | < 10s | `/api/chat` endpoint |
| **Dashboard load** | < 3s | Frontend initial page load |
| **PDF report generation** | < 10s | All `/api/reports/*/pdf` endpoints |

### 1.3 Data Durability

| Metric | Target |
|--------|--------|
| **Data durability** | 99.99% (provided by SAP BTP managed PostgreSQL) |
| **Backup frequency** | Daily automated backups |
| **Backup retention** | 14 days (Basic), 30 days (Professional/Enterprise) |
| **Recovery Point Objective (RPO)** | 24 hours |
| **Recovery Time Objective (RTO)** | 4 hours (Basic), 2 hours (Professional), 1 hour (Enterprise) |

---

## 2. Incident Classification

### 2.1 Severity Levels

| Severity | Definition | Examples |
|----------|-----------|---------|
| **P1 - Critical** | Service completely unavailable, no workaround | Application down, database unreachable, data loss |
| **P2 - High** | Major feature unavailable, limited workaround | AI analysis failing, reports not generating, SAP sync broken |
| **P3 - Medium** | Minor feature unavailable, workaround exists | Export function slow, one dashboard widget error |
| **P4 - Low** | Cosmetic issue, feature request, documentation | UI alignment, i18n missing translation, enhancement request |

### 2.2 Response Times

| Severity | Basic | Professional | Enterprise |
|----------|-------|-------------|-----------|
| **P1** | 4 business hours | 2 business hours | 1 hour (24/7) |
| **P2** | 8 business hours | 4 business hours | 2 business hours |
| **P3** | 2 business days | 1 business day | 4 business hours |
| **P4** | 5 business days | 3 business days | 2 business days |

### 2.3 Resolution Targets

| Severity | Target Resolution |
|----------|------------------|
| **P1** | 4 hours |
| **P2** | 1 business day |
| **P3** | 5 business days |
| **P4** | Next release cycle |

**Business hours**: Monday-Friday, 08:00-18:00 CET (excluding German public holidays)
**Enterprise 24/7**: P1 incidents only, all days including weekends/holidays

---

## 3. Support Channels

### 3.1 Channel Overview

| Channel | Availability | Response |
|---------|-------------|---------|
| **Support Portal** | 24/7 (ticket creation) | Per severity SLA |
| **Email** | 24/7 (ticket creation) | Per severity SLA |
| **Phone** | Business hours (Enterprise: 24/7 for P1) | Immediate |
| **SAP BTP Support** | Via SAP support ticket (S-user) | SAP SLA |

### 3.2 Support Portal

- URL: Provided during onboarding
- Features: Ticket creation, status tracking, knowledge base, release notes
- Authentication: SSO via SAP XSUAA

### 3.3 Escalation Path

```
Level 1: Support Engineer (initial triage and resolution)
    ↓ (if unresolved within response SLA)
Level 2: Senior Engineer (deep technical investigation)
    ↓ (if unresolved within 2x response SLA)
Level 3: Engineering Lead (architecture-level issues)
    ↓ (P1 only, if unresolved within 4 hours)
Level 4: CTO / Incident Commander (executive escalation)
```

---

## 4. Maintenance Windows

### 4.1 Scheduled Maintenance

| Type | Frequency | Duration | Notice |
|------|-----------|----------|--------|
| **Minor updates** | Bi-weekly | < 15 min | 48 hours |
| **Major releases** | Monthly | < 1 hour | 7 days |
| **Infrastructure** | Quarterly | < 2 hours | 14 days |
| **Emergency patches** | As needed | < 30 min | Best effort |

### 4.2 Maintenance Window

- **Preferred window**: Saturday 02:00-06:00 CET
- **Communication**: Email notification to tenant administrators
- **Zero-downtime**: Minor updates use rolling deployment (no downtime expected)

---

## 5. Service Credits

### 5.1 Credit Calculation

If the monthly uptime falls below the SLA target:

| Uptime Achieved | Credit (% of monthly fee) |
|-----------------|--------------------------|
| 99.0% - SLA target | 10% |
| 98.0% - 99.0% | 25% |
| 95.0% - 98.0% | 50% |
| Below 95.0% | 100% |

### 5.2 Claiming Credits

1. Submit a service credit request within 30 days of the incident
2. Include the affected time period and impact description
3. Credits are applied to the next billing cycle
4. Maximum credit: 100% of monthly fee for the affected month

---

## 6. Customer Responsibilities

| Responsibility | Details |
|---------------|---------|
| **Access management** | Assign appropriate role collections to users |
| **SAP Destination** | Maintain SAP_PM_SYSTEM destination configuration |
| **API keys** | Rotate API keys periodically, revoke unused keys |
| **GDPR** | Process data subject requests within legal deadlines |
| **Upgrades** | Apply recommended upgrades within 30 days |
| **Reporting** | Report issues promptly via support channels |

---

## 7. Disaster Recovery

### 7.1 Strategy

| Component | DR Approach |
|-----------|------------|
| **Application** | Cloud Foundry auto-restart, multi-instance deployment |
| **Database** | SAP-managed PostgreSQL with automated backups |
| **Frontend** | Served from HTML5 Application Repository (CDN-cached) |
| **Configuration** | Stored in BTP service bindings (platform-managed) |

### 7.2 Recovery Procedures

| Scenario | Action | Target |
|----------|--------|--------|
| Instance crash | Auto-restart by CF health monitor | < 2 minutes |
| Multi-instance failure | Auto-scaling triggers new instances | < 5 minutes |
| Database failover | Managed service automatic failover | Per SAP BTP PostgreSQL SLA |
| Region outage | Manual failover to secondary region | RTO per plan |
| Data corruption | Point-in-time restore from backup | RPO: 24 hours |

---

## 8. Reporting

### 8.1 Uptime Reports

- **Frequency**: Monthly, delivered by 5th business day
- **Contents**: Uptime percentage, incident summary, resolution times
- **Format**: PDF via support portal
- **Enterprise**: Additional weekly operational reviews available

### 8.2 Security Reports

- **Frequency**: Quarterly
- **Contents**: Security audit summary, vulnerability scan results, access review
- **Enterprise**: Monthly security posture reviews

---

## 9. Agreement Review

This SLA is reviewed annually. Changes are communicated 30 days in advance. Customers on Enterprise plans may negotiate custom SLA terms.

---

*PM Notification Analyzer | Service Level Agreement v1.0*
