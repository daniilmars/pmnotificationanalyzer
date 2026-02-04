# SAP BTP Deployment Guide

This guide covers deploying the PM Notification Analyzer to SAP Business Technology Platform (BTP).

## Prerequisites

1. **SAP BTP Account** with Cloud Foundry environment enabled
2. **Cloud Foundry CLI** installed ([Download](https://github.com/cloudfoundry/cli))
3. **MTA Build Tool** (optional but recommended): `npm install -g mbt`
4. **Node.js** >= 18.x for the approuter

## Architecture on BTP

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAP BTP Subaccount                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────────┐     ┌─────────────┐ │
│  │   Approuter  │────>│  Backend (Flask) │────>│  PostgreSQL │ │
│  │   (Node.js)  │     │    Python 3.11   │     │   Database  │ │
│  └──────┬───────┘     └────────┬─────────┘     └─────────────┘ │
│         │                      │                                │
│         │              ┌───────┴───────┐                       │
│         │              │               │                       │
│  ┌──────┴──────┐  ┌────┴────┐  ┌──────┴──────┐                │
│  │    XSUAA   │  │Destination│  │Connectivity │                │
│  │   Service  │  │  Service  │  │   Service   │                │
│  └─────────────┘  └────┬─────┘  └──────┬──────┘                │
│                        │               │                        │
└────────────────────────┼───────────────┼────────────────────────┘
                         │               │
                         ▼               ▼
                  ┌─────────────┐  ┌──────────────┐
                  │ SAP S/4HANA │  │ Cloud        │
                  │ (OData/RFC) │  │ Connector    │
                  └─────────────┘  └──────────────┘
```

## Quick Start

### 1. Login to Cloud Foundry

```bash
# Login to your BTP subaccount
cf login -a https://api.cf.us10-001.hana.ondemand.com

# Or use SSO
cf login -a https://api.cf.us10-001.hana.ondemand.com --sso
```

### 2. Deploy Using Script

```bash
cd pm-analyzer

# Make script executable
chmod +x deploy-btp.sh

# Full deployment (creates services, builds, and deploys)
./deploy-btp.sh full

# Or step by step:
./deploy-btp.sh services  # Create services first
./deploy-btp.sh build     # Build MTA archive
./deploy-btp.sh deploy    # Deploy to BTP
```

### 3. Manual Deployment (Alternative)

```bash
# Create services
cf create-service xsuaa application pm-analyzer-uaa -c xs-security.json
cf create-service destination lite pm-analyzer-destination
cf create-service connectivity lite pm-analyzer-connectivity
cf create-service postgresql-db trial pm-analyzer-db

# Deploy backend
cd backend
cf push

# Deploy approuter
cd ../approuter
npm install
cf push
```

## Configuration

### SAP System Destination

After deployment, configure a destination to connect to your SAP system:

1. Go to **BTP Cockpit** > **Subaccount** > **Connectivity** > **Destinations**
2. Click **New Destination**
3. Configure:

| Property | Value |
|----------|-------|
| Name | `SAP_PM_SYSTEM` |
| Type | HTTP |
| URL | `https://your-sap-system.com/sap/opu/odata/sap/` |
| Proxy Type | Internet or OnPremise |
| Authentication | BasicAuthentication |
| User | `<SAP_USER>` |
| Password | `<SAP_PASSWORD>` |

4. Add Additional Properties:
   - `HTML5.DynamicDestination`: `true`
   - `WebIDEEnabled`: `true`
   - `sap-client`: `100` (your SAP client)

### For On-Premise SAP Systems

If your SAP system is on-premise:

1. Install and configure **SAP Cloud Connector**
2. Create a virtual mapping to your SAP system
3. Set Proxy Type to `OnPremise` in the destination

### Environment Variables

The backend automatically reads these from BTP services:

| Variable | Source | Description |
|----------|--------|-------------|
| `SAP_ODATA_URL` | Destination Service | SAP OData base URL |
| `SAP_USER` | Destination Service | SAP username |
| `SAP_PASSWORD` | Destination Service | SAP password |
| `DATABASE_URL` | PostgreSQL Service | Database connection |

## Security & Roles

The application uses XSUAA for authentication. Available roles:

| Role Collection | Description |
|-----------------|-------------|
| `PM_Analyzer_Viewer` | Read-only access |
| `PM_Analyzer_Editor` | Create/modify notifications |
| `PM_Analyzer_Auditor` | Access audit trail (FDA compliance) |
| `PM_Analyzer_Admin` | Full administrative access |

### Assign Roles to Users

1. Go to **BTP Cockpit** > **Security** > **Role Collections**
2. Select a role collection (e.g., `PM_Analyzer_Admin`)
3. Click **Edit** > **Users** > **Add User**
4. Enter the user email and save

## Monitoring

### View Logs

```bash
# Recent logs
cf logs pm-analyzer-backend --recent

# Stream logs
cf logs pm-analyzer-backend

# Approuter logs
cf logs pm-analyzer-approuter --recent
```

### Check Status

```bash
# Application status
cf apps

# Service bindings
cf services

# App details
cf app pm-analyzer-backend
```

## Troubleshooting

### Common Issues

1. **Service creation fails**
   ```bash
   # Check available service plans
   cf marketplace

   # For PostgreSQL, try different plans
   cf create-service postgresql-db development pm-analyzer-db
   ```

2. **Authentication errors**
   - Verify XSUAA service is bound
   - Check xs-security.json syntax
   - Ensure user has assigned roles

3. **SAP connection fails**
   - Verify destination configuration
   - Check Cloud Connector if on-premise
   - Test destination in BTP Cockpit

4. **Backend won't start**
   ```bash
   # Check logs for errors
   cf logs pm-analyzer-backend --recent

   # SSH into container for debugging
   cf ssh pm-analyzer-backend
   ```

### Health Checks

```bash
# Backend health
curl https://pm-analyzer-backend.cfapps.us10-001.hana.ondemand.com/health

# API status
curl https://pm-analyzer-backend.cfapps.us10-001.hana.ondemand.com/api/sap/status
```

## Scaling

```bash
# Scale horizontally
cf scale pm-analyzer-backend -i 3

# Scale vertically
cf scale pm-analyzer-backend -m 1G

# Auto-scaling (requires autoscaler service)
cf create-service autoscaler standard pm-analyzer-autoscaler
cf bind-service pm-analyzer-backend pm-analyzer-autoscaler
```

## Cleanup

```bash
# Remove everything
./deploy-btp.sh cleanup

# Or manually
cf delete pm-analyzer-approuter -f -r
cf delete pm-analyzer-backend -f -r
cf delete-service pm-analyzer-uaa -f
cf delete-service pm-analyzer-destination -f
cf delete-service pm-analyzer-connectivity -f
cf delete-service pm-analyzer-db -f
```

## Production Considerations

1. **Use paid service plans** for production workloads
2. **Enable logging service** for centralized log management
3. **Configure alerts** in BTP Alert Notification Service
4. **Set up CI/CD** with SAP Continuous Integration and Delivery
5. **Enable audit logging** for compliance requirements
6. **Use SAP HANA** instead of PostgreSQL for better SAP integration
