# SAP Testing Options

This guide covers all options for testing SAP connectivity, from mock servers to real systems.

## Quick Comparison

| Option | Cost | Realism | Setup Time | Best For |
|--------|------|---------|------------|----------|
| Local Mock Server | Free | Low | 5 min | Development, CI/CD |
| SAP API Hub Sandbox | Free | High | 15 min | Integration testing |
| SAP CAL Trial | ~$50-100/day | Very High | 2-4 hours | Full system testing |
| SAP BTP Trial | Free | High | 1-2 hours | Cloud deployment |
| IDES/Training System | License needed | Very High | N/A | Enterprise testing |

---

## Option 1: Local Mock Server (Easiest)

**Best for:** Development, offline testing, CI/CD pipelines

```bash
# Terminal 1: Start mock server
cd pm-analyzer/backend
python tests/mock_sap_server.py

# Terminal 2: Configure and test
export SAP_ENABLED=true
export SAP_ODATA_URL=http://localhost:8080
export SAP_ODATA_PATH=/sap/opu/odata/sap/
export SAP_USER=TESTUSER
export SAP_PASSWORD=testpass

python tests/test_sap_integration.py --interactive
```

---

## Option 2: SAP API Business Hub Sandbox (Recommended)

**Best for:** Testing with real SAP API structure and sample data

### Step 1: Get Your API Key

1. Go to [https://api.sap.com](https://api.sap.com)
2. Click **Log On** → Create free account (or use SAP Universal ID)
3. Search for **"Maintenance Notification"**
4. Click the API → Go to **"Try Out"** tab
5. Click **"Show API Key"** → Copy the key

### Step 2: Set Environment Variable

```bash
export SAP_API_KEY="your-api-key-here"
```

### Step 3: Run Tests

```bash
cd pm-analyzer/backend

# Full test suite
python tests/test_sap_sandbox.py

# Quick connectivity test
python tests/test_sap_sandbox.py --quick

# Compare with local mock
python tests/test_sap_sandbox.py --compare
```

### Available Sandbox APIs

| API | Description | Entity Set |
|-----|-------------|------------|
| API_MAINTNOTIFICATION | PM Notifications | MaintenanceNotification |
| API_MAINTENANCEORDER | Work Orders | MaintenanceOrder |
| API_EQUIPMENT | Equipment Master | Equipment |
| API_FUNCTIONALLOCATION | Functional Locations | FunctionalLocation |
| API_MEASURINGPOINT | Measuring Points | MeasuringPoint |

### Sample API Calls

```bash
# Get notifications
curl -H "APIKey: $SAP_API_KEY" \
  "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_MAINTNOTIFICATION/MaintenanceNotification?\$top=5"

# Get equipment
curl -H "APIKey: $SAP_API_KEY" \
  "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_EQUIPMENT/Equipment?\$top=5"
```

---

## Option 3: SAP Cloud Appliance Library (CAL)

**Best for:** Testing with a full SAP S/4HANA system

### What You Get
- Full SAP S/4HANA system running on AWS/Azure/GCP
- Pre-configured demo data (IDES-like)
- All PM transactions available (IW21, IW31, IE01, etc.)

### Setup Steps

1. Go to [https://cal.sap.com](https://cal.sap.com)
2. Log in with SAP account
3. Choose **"SAP S/4HANA Fully-Activated Appliance"**
4. Select cloud provider (AWS, Azure, GCP)
5. Configure instance size and schedule
6. Launch (takes 1-2 hours)

### Cost
- ~$1-2 per hour for small instance
- Auto-suspend saves costs
- First-time users may get trial credits

### Connect Your App

```bash
export SAP_ENABLED=true
export SAP_CONNECTION_TYPE=odata
export SAP_ODATA_URL=https://your-cal-instance.sap.com
export SAP_ODATA_PATH=/sap/opu/odata/sap/
export SAP_USER=BPINST
export SAP_PASSWORD=Welcome1
export SAP_CLIENT=100
```

---

## Option 4: SAP BTP Trial

**Best for:** Testing cloud-native deployment with SAP integration

### Setup Steps

1. Go to [https://www.sap.com/products/technology-platform/trial.html](https://www.sap.com/products/technology-platform/trial.html)
2. Create free trial account
3. Access BTP Cockpit
4. Create destinations to SAP systems

### Features
- Free trial for 90 days
- Cloud Foundry environment
- Destination service for SAP connectivity
- Can connect to SAP API Hub sandbox

---

## Option 5: SAP Learning Hub / Training Systems

**Best for:** Teams with SAP Learning Hub subscriptions

SAP provides access to training systems (GR1, GR2, etc.) through:
- SAP Learning Hub subscription
- SAP partner access
- SAP PartnerEdge program

---

## Testing Strategy

### Development Phase
```
Local Mock Server → Fast iteration, offline capable
```

### Integration Testing
```
SAP API Hub Sandbox → Real API structure, free
```

### System Testing
```
SAP CAL Trial → Full SAP system, pay-per-use
```

### Production Validation
```
Customer's SAP System → Real data, requires access
```

---

## Environment Configuration by Scenario

### Local Development
```bash
export SAP_ENABLED=true
export SAP_ODATA_URL=http://localhost:8080
export SAP_ODATA_PATH=/sap/opu/odata/sap/
export SAP_USER=TESTUSER
export SAP_PASSWORD=testpass
```

### SAP API Hub Sandbox
```bash
export SAP_ENABLED=true
export SAP_ODATA_URL=https://sandbox.api.sap.com/s4hanacloud
export SAP_ODATA_PATH=/sap/opu/odata/sap/
export SAP_API_KEY=your-api-key
# Note: Uses API Key auth instead of user/pass
```

### SAP CAL / Real System
```bash
export SAP_ENABLED=true
export SAP_ODATA_URL=https://your-sap-system.com
export SAP_ODATA_PATH=/sap/opu/odata/sap/
export SAP_USER=your-user
export SAP_PASSWORD=your-password
export SAP_CLIENT=100
```

### SAP BTP with Destination
```bash
export SAP_ENABLED=true
export SAP_CONNECTION_TYPE=odata
# Credentials come from BTP Destination Service
# Configure destination "SAP_PM_SYSTEM" in BTP Cockpit
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: SAP Integration Tests

on: [push, pull_request]

jobs:
  test-mock:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Start mock server
        run: |
          python tests/mock_sap_server.py &
          sleep 5

      - name: Run tests
        env:
          SAP_ENABLED: true
          SAP_ODATA_URL: http://localhost:8080
        run: pytest tests/test_sap_integration.py -v

  test-sandbox:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3

      - name: Run sandbox tests
        env:
          SAP_API_KEY: ${{ secrets.SAP_API_KEY }}
        run: python tests/test_sap_sandbox.py
```

---

## Troubleshooting

### "401 Unauthorized" from SAP API Hub
- Check API key is correct
- Ensure key is passed in `APIKey` header (not `Authorization`)
- Some APIs require specific permissions

### "404 Not Found" for entities
- Entity names are case-sensitive
- Check the API documentation for exact entity set names
- Use `$metadata` to see available entities

### Connection timeout
- SAP CAL instances may be suspended (check CAL console)
- Cloud Connector may be required for on-premise systems
- Check firewall rules

### Empty results
- Sandbox may have limited data
- Try different filter criteria
- Check if entity requires expand for related data
