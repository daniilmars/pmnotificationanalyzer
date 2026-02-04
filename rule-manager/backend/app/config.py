import os
import secrets
import logging

logger = logging.getLogger(__name__)


class Config:
    """Base configuration."""
    # SECRET_KEY is required in production - generate a default only for development
    SECRET_KEY = os.environ.get('SECRET_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    DEBUG = False
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CORS configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    @classmethod
    def validate(cls):
        """Validate configuration and warn about issues."""
        if not cls.SECRET_KEY:
            logger.warning("SECRET_KEY not set - using generated key (not suitable for production)")
        if not cls.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY not set - SOP Assistant will not work")


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # Generate a random secret key for development if not provided
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    # Use SQLite for simple local development
    db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///' + os.path.join(db_dir, 'rules.db'))


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

    # In production, SECRET_KEY must be explicitly set
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # In production, this should point to a PostgreSQL database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')

    @classmethod
    def validate(cls):
        """Validate production configuration."""
        super().validate()
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set in production")
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URI environment variable must be set in production")


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
