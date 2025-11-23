# rule-manager/backend/app/__init__.py
from flask import Flask
from flask_cors import CORS
from .config import config_by_name
from .database import init_db

def create_app(config_name='default'):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize database
    init_db(app.config['SQLALCHEMY_DATABASE_URI'])

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints here
    from .api import api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    @app.route("/health")
    def health_check():
        return "OK"

    return app
