import logging.config
import os

import dotenv
import streamlit as st
from streamlit.runtime.secrets import secrets_singleton


def init_logging():
    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "default",
            },
        },
        "loggers": {
            "langsmith": {
                "level": "DEBUG",
            },
            "apps": {
                "level": "INFO",
            },
            "root": {
                "level": "WARNING",
                "handlers": ["console"],
            },
        }
    }

    # Apply logging configuration
    logging.config.dictConfig(LOGGING_CONFIG)


def load_secrets():
    secrets_singleton._secrets = {
        "auth": {
            "redirect_uri": f"{get('WEBAPP_BASE_URL')}/oauth2callback",
            "cookie_secret": get("SESSION_COOKIE_SECRET"),
            "proconnect": {
                "client_id": get("PROCONNECT_CLIENT_ID"),
                "client_secret": get("PROCONNECT_CLIENT_SECRET"),
                "server_metadata_url": f"https://{get('PROCONNECT_DOMAIN')}/api/v2/.well-known/openid-configuration",
                "client_kwargs": {"prompt": "consent", "scope": "openid email given_name usual_name"},
            },
            "auth0": {
                "client_id": get("AUTH0_CLIENT_ID"),
                "client_secret": get("AUTH0_CLIENT_SECRET"),
                "server_metadata_url": f"https://{get('AUTH0_DOMAIN')}/.well-known/openid-configuration",
            },
        },
        "connections": {
            "default": {
                "url": get("DATABASE_URL", "").replace("postgres://", "postgresql+psycopg://"),
            },
        },
    }


def get(key, default=None):
    return os.getenv(key, default=default)


def init_config():
    global _conf
    dotenv.load_dotenv('.env', override=True)
    load_secrets()
    if not st.session_state.get('init'):
        init_logging()
        st.session_state['init'] = True

