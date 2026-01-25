from importlib.metadata import version

from .base import APIError, AqilasClient
from .main import get_credit, get_sms_status, send_sms

__version__ = version("aqilas")
__all__ = [
    "AqilasClient",
    # Exceptions
    "APIError",
    # Functions
    "get_credit",
    "send_sms",
    "get_sms_status",
]
