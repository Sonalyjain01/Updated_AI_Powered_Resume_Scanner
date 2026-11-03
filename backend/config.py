import logging
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')


def configure_logging() -> None:
    from request_context import install_log_record_factory
    install_log_record_factory()  # adds request_id to every log record
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
    )


def get_cors_origins() -> List[str]:
    """Allowed origins from CORS_ORIGINS (comma separated); '*' when unset"""
    raw = os.getenv('CORS_ORIGINS', '*')
    return [origin.strip() for origin in raw.split(',') if origin.strip()] or ['*']


# Secrets must come from the environment (or a local .env that is not committed).
# They have no defaults on purpose: a missing value stops startup with a clear message.
REQUIRED_SECRETS = {
    'EMERGENT_LLM_KEY': 'API key for the AI provider',
}


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing"""


def mask_secret(value: str) -> str:
    """Show only enough of a secret to recognise it in logs"""
    if not value:
        return '(not set)'
    if len(value) <= 8:
        return '***'
    return f'{value[:4]}...{value[-2:]}'


def validate_settings() -> None:
    """Fail fast if a required secret is missing; warn about risky settings"""
    logger = logging.getLogger(__name__)

    missing = [f'{name} ({why})' for name, why in REQUIRED_SECRETS.items() if not os.getenv(name, '').strip()]
    if missing:
        raise ConfigError(
            'Missing required environment variables: ' + ', '.join(missing) +
            '. Copy backend/.env.example to backend/.env and fill them in.'
        )

    for name in REQUIRED_SECRETS:
        logger.info(f'{name} loaded: {mask_secret(os.getenv(name, ""))}')

    auth_on = os.getenv('AUTH_REQUIRED', 'false').lower() == 'true'
    if auth_on and len(os.getenv('JWT_SECRET', '')) < 32:
        raise ConfigError(
            'AUTH_REQUIRED=true needs JWT_SECRET of at least 32 characters. '
            'Make one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    if not auth_on:
        logger.warning(
            "AUTH_REQUIRED is not 'true': anyone who can reach this API uses it as one shared organisation. "
            "Set AUTH_REQUIRED=true and JWT_SECRET before exposing it."
        )
    if float(os.getenv('BACKUP_INTERVAL_HOURS', '0')) > 0 and not os.getenv('BACKUP_ENCRYPTION_KEY'):
        logger.warning("BACKUP_ENCRYPTION_KEY is not set: scheduled backups would hold personal data unencrypted.")

    if os.getenv('STORAGE_BACKEND', 'local').lower() == 's3' and not os.getenv('S3_BUCKET', '').strip():
        raise ConfigError('STORAGE_BACKEND=s3 needs S3_BUCKET (and S3_ENDPOINT_URL for MinIO or R2).')

    if get_cors_origins() == ['*']:
        logger.warning("CORS_ORIGINS is '*'. Set an explicit list of origins before deploying.")
