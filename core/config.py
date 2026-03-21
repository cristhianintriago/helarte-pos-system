import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///helarte.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "helarte_secret_key")
    DEFAULT_ROOT_USERNAME = os.environ.get("DEFAULT_ROOT_USERNAME", "root")
    DEFAULT_ROOT_PASSWORD = os.environ.get("DEFAULT_ROOT_PASSWORD")


def normalize_database_url(database_url):
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url
