# --- Convenience shared client helpers ---
# module-level default client and lock for thread-safety
import threading
from typing import Any, Dict, List, Optional

from .base import AqilasClient
from .types import AqilasNotInitializedError
from .utils import BASE_URL

_default_client: Optional["AqilasClient"] = None
_client_lock = threading.RLock()


def init_client(
    token: str,
    base_url: Optional[str] = None,
    timeout: Optional[float] = 10.0,
    force: bool = False,
) -> "AqilasClient":
    """Initialize and return a module-level shared AqilasClient.

    If a client already exists and `force` is False the existing client is returned.
    If `force` is True the existing client is closed and replaced.
    """
    global _default_client
    with _client_lock:
        if _default_client is not None and not force:
            return _default_client

        if _default_client is not None and force:
            try:
                _default_client.close()
            except Exception:
                pass

        client = AqilasClient(
            token=token,
            base_url=base_url or BASE_URL,
            timeout=timeout,
        )
        _default_client = client
        return client


def get_client() -> "AqilasClient":
    """Return the shared client or raise if it has not been initialized."""
    with _client_lock:
        if _default_client is None:
            raise AqilasNotInitializedError(
                "AqilasClient is not initialized. Call init_client(token, ...) first."
            )
        return _default_client


def close_client() -> None:
    """Close and unset the module-level shared client."""
    global _default_client
    with _client_lock:
        if _default_client is not None:
            try:
                _default_client.close()
            except Exception:
                pass
            _default_client = None


def get_credit(
    token: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Convenience function: get credit using shared client or a temporary client if token is provided.

    If `token` is provided a temporary client is used for the call and closed afterwards.
    Otherwise the module-level shared client is used (must be initialized with `init_client`).
    """
    if token:
        # Use context manager so the session is closed automatically
        with AqilasClient(
            token=token,
            base_url=base_url or BASE_URL,
            timeout=timeout,
        ) as client:
            return client.safe_get_credit()

    client = get_client()
    return client.safe_get_credit()


def send_sms(
    sender: str,
    receivers: List[str],
    content: str,
    token: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Convenience function to send an SMS via shared client or temporary client if token given."""
    if token:
        # Use context manager so the session is closed automatically
        with AqilasClient(
            token=token,
            base_url=base_url or BASE_URL,
            timeout=timeout,
        ) as client:
            return client.safe_send_sms(
                sender=sender, receivers=receivers, content=content
            )

    client = get_client()
    return client.safe_send_sms(sender=sender, receivers=receivers, content=content)


def get_sms_status(
    bulk_id: str,
    token: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Convenience function to get SMS status via shared client or temporary client if token given."""
    if token:
        # Use context manager so the session is closed automatically
        with AqilasClient(
            token=token,
            base_url=base_url or BASE_URL,
            timeout=timeout,
        ) as client:
            return client.safe_get_sms_status(bulk_id=bulk_id)

    client = get_client()
    return client.safe_get_sms_status(bulk_id=bulk_id)
