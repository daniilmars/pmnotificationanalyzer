import json
import os
import time
from functools import wraps
from urllib.request import urlopen

from flask import request, jsonify
from jose import jwt

# Load Auth0 configuration from environment variables for better security and flexibility.
# Ensure these are set in your environment (e.g., in a .env file loaded by your run script).
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
API_AUDIENCE = os.environ.get("API_AUDIENCE")
ALGORITHMS = ["RS256"]

if not AUTH0_DOMAIN or not API_AUDIENCE:
    raise RuntimeError("AUTH0_DOMAIN and API_AUDIENCE must be set as environment variables.")

# --- Caching for JWKS ---
jwks_cache = {
    "keys": None,
    "expiry": 0
}
CACHE_LIFETIME_SECONDS = 3600 # Cache keys for 1 hour

def get_jwks():
    """
    Retrieves the JSON Web Key Set from Auth0, caching it to avoid excessive requests.
    """
    now = time.time()
    if jwks_cache["keys"] and jwks_cache["expiry"] > now:
        return jwks_cache["keys"]

    jsonurl = urlopen(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
    new_jwks = json.loads(jsonurl.read())
    jwks_cache["keys"] = new_jwks
    jwks_cache["expiry"] = now + CACHE_LIFETIME_SECONDS
    return new_jwks

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
            jwt.decode(token, rsa_key, algorithms=ALGORITHMS, audience=API_AUDIENCE, issuer=f"https://{AUTH0_DOMAIN}/")
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

        return f(*args, **kwargs)
    return decorated