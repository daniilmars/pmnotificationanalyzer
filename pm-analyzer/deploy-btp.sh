#!/bin/bash
# ==============================================================================
# SAP BTP Deployment Script for PM Notification Analyzer
# ==============================================================================
#
# Prerequisites:
#   1. Cloud Foundry CLI installed (cf --version)
#   2. MTA Build Tool installed (mbt --version)
#   3. Logged into CF (cf login)
#
# Usage:
#   ./deploy-btp.sh [command]
#
# Commands:
#   build     - Build MTA archive
#   deploy    - Deploy to BTP
#   full      - Build and deploy (default)
#   services  - Create required services only
#   status    - Check deployment status
#   logs      - View application logs
#   cleanup   - Remove all deployed apps and services
#
# ==============================================================================

set -e

# Configuration
APP_NAME="pm-notification-analyzer"
BACKEND_NAME="pm-analyzer-backend"
APPROUTER_NAME="pm-analyzer-approuter"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check CF CLI
    if ! command -v cf &> /dev/null; then
        print_error "Cloud Foundry CLI not found. Install from https://github.com/cloudfoundry/cli"
        exit 1
    fi
    print_success "Cloud Foundry CLI: $(cf --version)"

    # Check MBT
    if ! command -v mbt &> /dev/null; then
        print_warning "MTA Build Tool not found. Install with: npm install -g mbt"
        print_warning "Falling back to cf push for deployment"
        MBT_AVAILABLE=false
    else
        print_success "MTA Build Tool: $(mbt --version)"
        MBT_AVAILABLE=true
    fi

    # Check CF login
    if ! cf target &> /dev/null; then
        print_error "Not logged into Cloud Foundry. Run: cf login"
        exit 1
    fi
    print_success "Logged into CF: $(cf target | grep -E 'org|space' | tr '\n' ' ')"
}

create_services() {
    print_header "Creating BTP Services"

    # XSUAA
    echo "Creating XSUAA service..."
    cf create-service xsuaa application pm-analyzer-uaa -c xs-security.json 2>/dev/null || \
        cf update-service pm-analyzer-uaa -c xs-security.json 2>/dev/null || \
        print_warning "XSUAA service already exists"

    # Destination
    echo "Creating Destination service..."
    cf create-service destination lite pm-analyzer-destination 2>/dev/null || \
        print_warning "Destination service already exists"

    # Connectivity
    echo "Creating Connectivity service..."
    cf create-service connectivity lite pm-analyzer-connectivity 2>/dev/null || \
        print_warning "Connectivity service already exists"

    # Database (PostgreSQL)
    echo "Creating PostgreSQL database..."
    cf create-service postgresql-db trial pm-analyzer-db 2>/dev/null || \
        print_warning "Database service already exists or trial plan not available"

    # HTML5 Repository
    echo "Creating HTML5 App Repository..."
    cf create-service html5-apps-repo app-host pm-analyzer-html5-repo-host 2>/dev/null || \
        print_warning "HTML5 repo host already exists"
    cf create-service html5-apps-repo app-runtime pm-analyzer-html5-repo-runtime 2>/dev/null || \
        print_warning "HTML5 repo runtime already exists"

    print_success "All services created/updated"
}

build_mta() {
    print_header "Building MTA Archive"

    if [ "$MBT_AVAILABLE" = true ]; then
        mbt build -t ./mta_archives
        print_success "MTA archive built successfully"
    else
        print_warning "Skipping MTA build - mbt not available"
    fi
}

deploy_mta() {
    print_header "Deploying MTA to BTP"

    if [ "$MBT_AVAILABLE" = true ]; then
        # Find the latest mtar file
        MTAR_FILE=$(ls -t ./mta_archives/*.mtar 2>/dev/null | head -1)
        if [ -z "$MTAR_FILE" ]; then
            print_error "No MTAR file found. Run build first."
            exit 1
        fi

        cf deploy "$MTAR_FILE" -f
        print_success "MTA deployed successfully"
    else
        # Fallback to cf push
        print_warning "Using cf push instead of MTA deploy"
        deploy_cf_push
    fi
}

deploy_cf_push() {
    print_header "Deploying with cf push"

    # Deploy backend
    echo "Deploying backend..."
    cd backend
    cf push $BACKEND_NAME -f manifest.yml
    cd ..
    print_success "Backend deployed"

    # Deploy approuter
    echo "Deploying approuter..."
    cd approuter
    npm install --production
    cf push $APPROUTER_NAME
    cd ..
    print_success "Approuter deployed"
}

show_status() {
    print_header "Deployment Status"

    echo "Applications:"
    cf apps | grep -E "pm-analyzer|name" || echo "No apps found"

    echo -e "\nServices:"
    cf services | grep -E "pm-analyzer|name" || echo "No services found"

    echo -e "\nRoutes:"
    cf routes | grep -E "pm-analyzer|host" || echo "No routes found"
}

show_logs() {
    print_header "Application Logs"

    echo "Backend logs (last 100 lines):"
    cf logs $BACKEND_NAME --recent | tail -100
}

cleanup() {
    print_header "Cleanup - Removing Deployment"

    read -p "Are you sure you want to remove all apps and services? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi

    # Delete apps
    cf delete $APPROUTER_NAME -f -r 2>/dev/null || true
    cf delete $BACKEND_NAME -f -r 2>/dev/null || true
    cf delete pm-analyzer-html5-deployer -f 2>/dev/null || true

    # Delete services (order matters due to bindings)
    cf delete-service pm-analyzer-html5-repo-runtime -f 2>/dev/null || true
    cf delete-service pm-analyzer-html5-repo-host -f 2>/dev/null || true
    cf delete-service pm-analyzer-db -f 2>/dev/null || true
    cf delete-service pm-analyzer-connectivity -f 2>/dev/null || true
    cf delete-service pm-analyzer-destination -f 2>/dev/null || true
    cf delete-service pm-analyzer-uaa -f 2>/dev/null || true

    print_success "Cleanup complete"
}

configure_destination() {
    print_header "Configure SAP Destination"

    echo "To connect to your SAP system, create a destination in BTP Cockpit:"
    echo ""
    echo "1. Go to your BTP Subaccount > Connectivity > Destinations"
    echo "2. Create a new destination with these settings:"
    echo ""
    echo "   Name: SAP_PM_SYSTEM"
    echo "   Type: HTTP"
    echo "   URL: https://your-sap-system.com/sap/opu/odata/sap/"
    echo "   Proxy Type: Internet (or OnPremise for Cloud Connector)"
    echo "   Authentication: BasicAuthentication"
    echo "   User: <SAP_USER>"
    echo "   Password: <SAP_PASSWORD>"
    echo ""
    echo "   Additional Properties:"
    echo "   - HTML5.DynamicDestination: true"
    echo "   - WebIDEEnabled: true"
    echo "   - WebIDEUsage: odata_gen"
    echo ""
    echo "For On-Premise SAP systems, also configure Cloud Connector."
}

# Main script
COMMAND=${1:-full}

check_prerequisites

case $COMMAND in
    build)
        build_mta
        ;;
    deploy)
        deploy_mta
        ;;
    full)
        create_services
        build_mta
        deploy_mta
        show_status
        configure_destination
        ;;
    services)
        create_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    cleanup)
        cleanup
        ;;
    destination)
        configure_destination
        ;;
    *)
        echo "Usage: $0 {build|deploy|full|services|status|logs|cleanup|destination}"
        exit 1
        ;;
esac

print_header "Done!"
