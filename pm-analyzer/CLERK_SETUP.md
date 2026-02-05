# Clerk Authentication Setup Guide

This guide explains how to set up Clerk authentication for the PM Notification Analyzer.

## Why Clerk?

Clerk provides:
- 🔐 Secure authentication out of the box
- 👥 User management dashboard
- 🔑 Social logins (Google, Microsoft, etc.)
- 📱 Multi-factor authentication (MFA)
- 🏢 Organizations & teams
- 🎨 Pre-built UI components
- 📊 Analytics & audit logs

## Quick Setup (5 minutes)

### Step 1: Create Clerk Account

1. Go to [https://clerk.dev](https://clerk.dev)
2. Sign up for a free account
3. Create a new application

### Step 2: Get Your API Keys

In the Clerk Dashboard:
1. Go to **API Keys**
2. Copy your keys:
   - **Publishable Key** (starts with `pk_test_` or `pk_live_`)
   - **Secret Key** (starts with `sk_test_` or `sk_live_`)

### Step 3: Configure Backend

Set environment variables:

```bash
# Required
export CLERK_SECRET_KEY="sk_test_xxxxxxxxxxxxx"
export CLERK_PUBLISHABLE_KEY="pk_test_xxxxxxxxxxxxx"

# Optional
export CLERK_ENABLED="true"  # Default: true if CLERK_SECRET_KEY is set
```

### Step 4: Configure Frontend

Add Clerk script to `frontend/webapp/index.html`:

```html
<!-- Add before closing </head> tag -->
<script
  async
  crossorigin="anonymous"
  data-clerk-publishable-key="pk_test_xxxxxxxxxxxxx"
  src="https://cdn.jsdelivr.net/npm/@clerk/clerk-js@latest/dist/clerk.browser.js"
  type="text/javascript"
></script>
```

### Step 5: Start the Application

```bash
cd pm-analyzer/backend
python -m flask run --port 5001
```

---

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CLERK_SECRET_KEY` | Yes | Backend API key from Clerk |
| `CLERK_PUBLISHABLE_KEY` | Yes | Frontend key from Clerk |
| `CLERK_ENABLED` | No | Enable/disable auth (default: true) |
| `CLERK_WEBHOOK_SECRET` | No | For webhook signature verification |
| `CLERK_JWT_VERIFICATION_KEY` | No | Local JWT verification (optional) |

### Role Configuration

Default roles in the system:

| Role | Description | Permissions |
|------|-------------|-------------|
| `admin` | Administrator | Full access |
| `editor` | Editor | View + Edit notifications |
| `auditor` | Auditor | View + Audit trail access |
| `viewer` | Viewer | View only (default) |

---

## Setting Up User Roles

### Option 1: Via Clerk Dashboard

1. Go to Clerk Dashboard → Users
2. Select a user
3. Edit **Public Metadata**
4. Add: `{ "roles": ["admin"] }`

### Option 2: Via API

```bash
# Set user as admin
curl -X PUT http://localhost:5001/api/auth/users/{user_id}/roles \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["admin"]}'
```

### Option 3: Via Webhook

Configure a webhook to automatically assign roles on user creation:

1. In Clerk Dashboard → Webhooks
2. Add endpoint: `https://your-app.com/api/auth/webhook`
3. Select events: `user.created`
4. Handle the webhook to set default roles

---

## API Authentication

### Making Authenticated Requests

Include the Clerk session token in the Authorization header:

```javascript
// Frontend (using AuthService)
const authService = AuthService.getInstance();
const response = await authService.createAuthFetch()('/api/notifications', {
  method: 'GET'
});
```

```bash
# Backend/CLI
curl -H "Authorization: Bearer $CLERK_TOKEN" \
  http://localhost:5001/api/notifications
```

### Protected Endpoints

Endpoints are protected using decorators:

```python
from app.clerk_auth import require_auth, require_role, require_admin

@app.route('/api/protected')
@require_auth
def protected_route():
    user = get_current_user()
    return jsonify({'user': user.email})

@app.route('/api/admin-only')
@require_admin
def admin_route():
    return jsonify({'admin': True})

@app.route('/api/audit')
@require_role('auditor')
def audit_route():
    return jsonify({'audit': True})
```

---

## Auth Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/status` | GET | No | Get auth configuration |
| `/api/auth/me` | GET | Yes | Get current user |
| `/api/auth/users` | GET | Admin | List all users |
| `/api/auth/users/{id}` | GET | Admin | Get user by ID |
| `/api/auth/users/{id}/roles` | PUT | Admin | Set user roles |
| `/api/auth/webhook` | POST | No | Clerk webhook handler |

---

## Frontend Integration

### Initialize Auth Service

In your Component.js or controller:

```javascript
sap.ui.require(["pmanalyzer/service/AuthService"], function(AuthService) {
    var authService = AuthService.getInstance();

    // Initialize with your publishable key
    authService.initialize("pk_test_xxxxx").then(function(enabled) {
        if (enabled) {
            console.log("Auth enabled");
        }
    });
});
```

### Using Auth Model for UI Binding

```xml
<!-- Show/hide based on auth state -->
<Button text="Sign In" visible="{= !${auth>/isAuthenticated} }" press=".onSignIn" />
<Button text="Sign Out" visible="{= ${auth>/isAuthenticated} }" press=".onSignOut" />

<!-- Show admin-only content -->
<Panel visible="{= ${auth>/isAdmin} }">
    <Text text="Admin Panel" />
</Panel>
```

### Sign In/Out

```javascript
onSignIn: function() {
    AuthService.getInstance().signIn();
},

onSignOut: function() {
    AuthService.getInstance().signOut();
}
```

---

## Security Best Practices

### 1. Use HTTPS in Production

Always use HTTPS to protect tokens in transit.

### 2. Validate Webhooks

Enable webhook signature verification:

```python
# In clerk_auth.py webhook handler
import hmac
import hashlib

webhook_secret = os.environ.get('CLERK_WEBHOOK_SECRET')
signature = request.headers.get('svix-signature')

# Verify signature before processing
```

### 3. Rotate Keys Periodically

Regularly rotate your Clerk API keys, especially after:
- Team member changes
- Security incidents
- Production deployments

### 4. Use Organizations for Multi-tenant

For multi-tenant deployments, use Clerk Organizations:
- Isolate data by organization
- Assign org-specific roles
- Manage team invitations

---

## Troubleshooting

### "UNAUTHORIZED" Error

1. Check if token is being sent in Authorization header
2. Verify CLERK_SECRET_KEY is correct
3. Check if token has expired

### "FORBIDDEN" Error

1. User doesn't have required role
2. Check user's public metadata for roles
3. Verify role names match configuration

### Clerk Not Loading

1. Check publishable key in index.html
2. Verify Clerk script is loading (check browser console)
3. Check for CORS issues

### Token Verification Fails

1. Ensure CLERK_SECRET_KEY matches your Clerk app
2. Check clock sync between servers
3. Try clearing browser cache/cookies

---

## Testing Without Clerk

For local development without Clerk:

```bash
# Disable Clerk auth
export CLERK_ENABLED="false"

# Or simply don't set CLERK_SECRET_KEY
unset CLERK_SECRET_KEY
```

All endpoints will be accessible without authentication when disabled.

---

## Migrating from Other Auth Providers

### From Firebase Auth

1. Export users from Firebase
2. Import to Clerk via API
3. Update frontend SDK
4. Migrate user metadata

### From Auth0

1. Export users from Auth0
2. Import to Clerk
3. Update JWT verification
4. Update role claims mapping

---

## Cost

Clerk Pricing (as of 2024):

| Plan | MAU | Price |
|------|-----|-------|
| Free | Up to 10,000 | $0 |
| Pro | Unlimited | $0.02/MAU |
| Enterprise | Unlimited | Custom |

For MVP/development, the free tier is usually sufficient.
