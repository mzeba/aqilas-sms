from importlib.metadata import version

from .base import AqilasClient
from .main import (
    close_client,
    get_client,
    get_credit,
    get_sms_status,
    init_client,
    send_sms,
)
from .types import (
    AqilasError,
    AqilasNetworkError,
    AqilasNotInitializedError,
    AqilasResponseError,
    AqilasValidationError,
)

__version__ = version("aqilas")
__all__ = [
    "AqilasClient",
    "AqilasError",
    "AqilasValidationError",
    "AqilasNotInitializedError",
    "AqilasNetworkError",
    "AqilasResponseError",
    "init_client",
    "get_client",
    "close_client",
    "get_credit",
    "send_sms",
    "get_sms_status",
]
