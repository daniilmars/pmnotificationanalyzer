import json
import os
import time
from functools import wraps
from urllib.request import urlopen

from flask import request, jsonify
from jose import jwt

# --- Load XSUAA configuration from VCAP_SERVICES ---
# VCAP_SERVICES is an environment variable provided by Cloud Foundry
# that contains details of bound services.
vcap_services = json.loads(os.getenv('VCAP_SERVICES', '{}'))

# Find the XSUAA service binding by its offering name or name from mta.yaml
XSUAA_CREDENTIALS = None
if 'xsuaa' in vcap_services:
    for service in vcap_services['xsuaa']:
        # Match the service name defined in mta.yaml for the binding
        if service.get('name') == 'pm-analyzer-uaa-binding':
            XSUAA_CREDENTIALS = service['credentials']
            break

if not XSUAA_CREDENTIALS:
    # Fallback for local development or if XSUAA is not bound
    # In local development, you might still use .env for Auth0 details
    AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
    API_AUDIENCE = os.environ.get("API_AUDIENCE")
    if not AUTH0_DOMAIN or not API_AUDIENCE:
        raise RuntimeError("CRITICAL: XSUAA service not bound and Auth0 environment variables not set. Cannot proceed with authentication.")
    else:
        # Use Auth0 details for local testing if XSUAA is not available
        print("WARNING: XSUAA service not found in VCAP_SERVICES. Falling back to Auth0 environment variables for local development.")
        XSUAA_ISSUER = f"https://{AUTH0_DOMAIN}/"
        XSUAA_AUDIENCE = API_AUDIENCE
        JWKS_URI = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
else:
    # Use XSUAA credentials from BTP
    XSUAA_ISSUER = XSUAA_CREDENTIALS.get("url") # XSUAA's URL is the issuer
    XSUAA_AUDIENCE = XSUAA_CREDENTIALS.get("xsappname") # xsappname is the audience for XSUAA tokens
    JWKS_URI = f"{XSUAA_ISSUER}/.well-known/jwks.json" # JWKS endpoint from XSUAA URL

ALGORITHMS = ["RS256"]

# --- Caching for JWKS ---
jwks_cache = {
    "keys": None,
    "expiry": 0
}
CACHE_LIFETIME_SECONDS = 3600 # Cache keys for 1 hour

def get_jwks():
    """
    Retrieves the JSON Web Key Set from the configured JWKS_URI, caching it.
    """
    now = time.time()
    if jwks_cache["keys"] and jwks_cache["expiry"] > now:
        return jwks_cache["keys"]

    try:
        jsonurl = urlopen(JWKS_URI)
        new_jwks = json.loads(jsonurl.read())
        jwks_cache["keys"] = new_jwks
        jwks_cache["expiry"] = now + CACHE_LIFETIME_SECONDS
        return new_jwks
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve JWKS from {JWKS_URI}: {e}")

# Decorator to protect endpoints
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            return jsonify({
                "error": {"code": "AUTH_HEADER_MISSING", "message": "Authorization header is missing"}
            }), 401

        parts = auth_header.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify({
                "error": {"code": "INVALID_AUTH_HEADER", "message": "Authorization header must be a Bearer token"}
            }), 401

        token = parts[1]

        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.JWTError:
            return jsonify({
                "error": {"code": "INVALID_TOKEN_HEADER", "message": "Invalid token header"}
            }), 401

        jwks = get_jwks()
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if not rsa_key:
            return jsonify({
                "error": {"code": "SIGNING_KEY_NOT_FOUND", "message": "Unable to find appropriate key for this token"}
            }), 401

        try:
            # Validate the token using XSUAA's issuer and xsappname as audience
            jwt.decode(token, rsa_key, algorithms=ALGORITHMS, audience=XSUAA_AUDIENCE, issuer=XSUAA_ISSUER)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": {"code": "TOKEN_EXPIRED", "message": "Token is expired"}
            }), 401
        except (jwt.JWTClaimsError, jwt.JWTError) as e:
            return jsonify({
                "error": {
                    "code": "INVALID_TOKEN_CLAIMS",
                    "message": f"Invalid token claims: {str(e)}"
                }
            }), 401
        except Exception as e:
            return jsonify({
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": f"Authentication failed: {str(e)}"
                }
            }), 401

        return f(*args, **kwargs)
    return decorated
