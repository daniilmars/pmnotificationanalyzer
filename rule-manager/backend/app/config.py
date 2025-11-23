import os

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_default_secret_key')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    DEBUG = False
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # Use SQLite for simple local development to start
    db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI', 'sqlite:///' + os.path.join(db_dir, 'rules.db'))

class ProductionConfig(Config):
    """Production configuration."""
    # In production, this should point to a PostgreSQL database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI')

config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
