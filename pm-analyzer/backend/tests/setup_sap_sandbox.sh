#!/bin/bash
# ============================================================
# SAP API Business Hub Sandbox Setup Script
# ============================================================

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       SAP API Business Hub Sandbox Setup                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if API key is already set
if [ -n "$SAP_API_KEY" ]; then
    echo "✓ SAP_API_KEY is already set: ${SAP_API_KEY:0:8}...${SAP_API_KEY: -4}"
    echo ""
    read -p "Use this key? (Y/n): " use_existing
    if [[ "$use_existing" =~ ^[Nn] ]]; then
        unset SAP_API_KEY
    fi
fi

# Prompt for API key if not set
if [ -z "$SAP_API_KEY" ]; then
    echo ""
    echo "To get your API key:"
    echo "  1. Go to: https://api.sap.com"
    echo "  2. Log in (create free account if needed)"
    echo "  3. Search: 'Maintenance Notification'"
    echo "  4. Click API → 'Try Out' tab → 'Show API Key'"
    echo ""
    read -p "Paste your API key: " SAP_API_KEY
    export SAP_API_KEY
fi

if [ -z "$SAP_API_KEY" ]; then
    echo "❌ No API key provided. Exiting."
    exit 1
fi

echo ""
echo "Testing connection to SAP API Hub..."
echo ""

# Test the connection
response=$(curl -s -w "\n%{http_code}" -H "APIKey: $SAP_API_KEY" \
    "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/API_MAINTNOTIFICATION/MaintenanceNotification?\$top=1&\$format=json")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo "✓ Connection successful! (HTTP $http_code)"
    echo ""
    echo "Sample notification data:"
    echo "$body" | python3 -m json.tool 2>/dev/null | head -20
    echo "..."
    echo ""
    echo "════════════════════════════════════════════════════════════"
    echo ""
    echo "✓ Your SAP API Hub Sandbox is ready!"
    echo ""
    echo "To use in this session:"
    echo "  export SAP_API_KEY='$SAP_API_KEY'"
    echo ""
    echo "To run the full test suite:"
    echo "  python tests/test_sap_sandbox.py"
    echo ""
    echo "To test with the main app:"
    echo "  export SAP_ENABLED=true"
    echo "  export SAP_ODATA_URL=https://sandbox.api.sap.com/s4hanacloud"
    echo "  python -m flask run --port 5001"
    echo ""
else
    echo "❌ Connection failed (HTTP $http_code)"
    echo ""
    if [ "$http_code" = "401" ]; then
        echo "The API key appears to be invalid."
        echo "Please check your key at https://api.sap.com"
    elif [ "$http_code" = "403" ]; then
        echo "Access forbidden. The API key may not have permission."
        echo "Try regenerating your key at https://api.sap.com"
    else
        echo "Response: $body"
    fi
    exit 1
fi
