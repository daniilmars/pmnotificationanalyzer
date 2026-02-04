# rule-manager/backend/app/__init__.py
import os
import logging
from flask import Flask
from flask_cors import CORS
from .config import config_by_name
from .database import init_db, seed_default_roles_and_permissions

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app(config_name='default'):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize database
    init_db(app.config['SQLALCHEMY_DATABASE_URI'])

    # CORS Configuration - restrict origins in production
    # Set CORS_ORIGINS env var to comma-separated list of allowed origins
    cors_origins = os.environ.get('CORS_ORIGINS', '*')
    if cors_origins != '*':
        cors_origins = [origin.strip() for origin in cors_origins.split(',')]
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})

    # Register blueprints here
    from .api import api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    # Register auth blueprint for authentication and authorization
    from .auth_api import auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/api/v1/auth')

    # Register validation export blueprint for compliance documentation
    from .validation_export import validation_blueprint
    app.register_blueprint(validation_blueprint, url_prefix='/api/v1/validation')

    # Initialize default roles and permissions on first run
    try:
        seed_default_roles_and_permissions()
        logger.info("Default roles and permissions initialized")
    except Exception as e:
        logger.warning(f"Could not initialize default roles: {e}")

    @app.route("/health")
    def health_check():
        return "OK"

    return app
