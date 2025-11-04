from __future__ import annotations

from typing import Any, Iterable, List, Optional, Union
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sms.types import (
    CreditSuccess,
    SendSmsSuccess,
    SmsStatusItem,
    SmsStatusSuccess,
    APIError,
)
from sms.utils import BASE_URL


class AqilasClient:
    """Client for the Aqilas SMS API.

    Improvements in this implementation:
    - Context manager support (``with AqilasClient(...) as client:``)
    - Simple retry/backoff strategy for transient failures
    - Centralized response mapping to typed dataclasses
    - Logging for debug/troubleshooting
    """

    def __init__(
        self,
        token: str,
        base_url: str = BASE_URL,
        timeout: Optional[float] = 10.0,
        *,
        retries: int = 2,
        backoff_factor: float = 0.3,
        status_forcelist: Iterable[int] = (429, 500, 502, 503, 504),
    ) -> None:
        if not token or not isinstance(token, str):
            raise ValueError("token must be a non-empty string")

        # Normalize base_url to always end with a single '/'
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token
        self.timeout = timeout

        # Use a Session for connection pooling and default headers
        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "X-AUTH-TOKEN": self.token}
        )

        # Configure retry strategy
        retry_strategy = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=tuple(status_forcelist),
            allowed_methods=frozenset(["GET", "POST"]),
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.logger = logging.getLogger(__name__)

    def _url(self, endpoint: str) -> str:
        return self.base_url + endpoint.lstrip("/")

    def get_credit(self) -> "Union[CreditSuccess, APIError]":
        """Fetch account credit and return a typed dataclass.

        Returns:
            CreditSuccess or APIError
        """
        try:
            resp = self.session.get(self._url("credit"), timeout=self.timeout)
        except requests.RequestException as exc:
            self.logger.debug("network error in get_credit: %s", exc)
            return APIError(message=str(exc))

        return self._map_credit_response(resp)

    def _map_credit_response(
        self, resp: requests.Response
    ) -> "Union[CreditSuccess, APIError]":
        try:
            data = resp.json()
        except ValueError:
            if resp.ok:
                return CreditSuccess(credit=None, currency=None)
            return APIError(message=resp.text or "Unknown error")

        if resp.ok:
            if isinstance(data, dict) and data.get("success") is not None:
                if data.get("success"):
                    return CreditSuccess(
                        credit=data.get("credit"), currency=data.get("currency")
                    )
                return APIError(message=data.get("message") or "")

            credit = data.get("credit") if isinstance(data, dict) else None
            currency = data.get("currency") if isinstance(data, dict) else None
            return CreditSuccess(credit=credit, currency=currency)

        message = (
            data.get("message")
            if isinstance(data, dict)
            else resp.text or "Unknown error"
        )
        return APIError(message=message)

    def send_sms(
        self, sender: str, receivers: List[str], content: str
    ) -> "Union[SendSmsSuccess, APIError]":
        """Send an SMS and return a typed response.

        Args:
            sender: sender id
            receivers: list of phone numbers
            content: message text
        """
        if not isinstance(receivers, list) or not receivers:
            raise ValueError("receivers must be a non-empty list of phone numbers")

        payload = {"from": sender, "to": receivers, "text": content}
        try:
            resp = self.session.post(
                self._url("sms"), json=payload, timeout=self.timeout
            )
        except requests.RequestException as exc:
            self.logger.debug("network error in send_sms: %s", exc)
            return APIError(message=str(exc))

        return self._map_send_response(resp)

    def _map_send_response(
        self, resp: requests.Response
    ) -> "Union[SendSmsSuccess, APIError]":
        try:
            data = resp.json()
        except ValueError:
            if resp.ok:
                return SendSmsSuccess(
                    message=None, bulk_id=None, cost=None, currency=None
                )
            return APIError(message=resp.text or "Unknown error")

        if isinstance(data, dict) and data.get("success") is not None:
            if data.get("success"):
                return SendSmsSuccess(
                    message=data.get("message"),
                    bulk_id=data.get("bulk_id"),
                    cost=data.get("cost"),
                    currency=data.get("currency"),
                )
            return APIError(message=data.get("message") or "")

        if resp.ok:
            message = data.get("message") if isinstance(data, dict) else None
            bulk_id = data.get("bulk_id") if isinstance(data, dict) else None
            cost = data.get("cost") if isinstance(data, dict) else None
            currency = data.get("currency") if isinstance(data, dict) else None
            return SendSmsSuccess(
                message=message, bulk_id=bulk_id, cost=cost, currency=currency
            )

        message = (
            data.get("message")
            if isinstance(data, dict)
            else resp.text or "Unknown error"
        )
        return APIError(message=message)

    def get_sms_status(self, bulkid: str) -> "Union[SmsStatusSuccess, APIError]":
        """Return delivery/status information for a bulk SMS identified by `bulkid`.

        Returns either SmsStatusSuccess (with a list of SmsStatusItem) or APIError.
        """
        if not bulkid:
            raise ValueError("bulkid must be provided")

        try:
            resp = self.session.get(self._url(f"sms/{bulkid}"), timeout=self.timeout)
        except requests.RequestException as exc:
            self.logger.debug("network error in get_sms_status: %s", exc)
            return APIError(message=str(exc))

        return self._map_status_response(resp)

    def _map_status_response(
        self, resp: requests.Response
    ) -> "Union[SmsStatusSuccess, APIError]":
        try:
            data = resp.json()
        except ValueError:
            if resp.ok:
                return SmsStatusSuccess(results=[])
            return APIError(message=resp.text or "Unknown error")

        if resp.ok:
            if isinstance(data, dict) and data.get("success") is not None:
                if data.get("success"):
                    raw = data.get("results") or data.get("data") or []
                    return SmsStatusSuccess(results=self._map_status_items(raw))
                return APIError(message=data.get("message") or "")

            if isinstance(data, list):
                return SmsStatusSuccess(results=self._map_status_items(data))

            return SmsStatusSuccess(results=[])

        message = (
            data.get("message")
            if isinstance(data, dict)
            else resp.text or "Unknown error"
        )
        return APIError(message=message)

    def _map_status_items(self, raw_list: Any) -> "List[SmsStatusItem]":
        results: "List[SmsStatusItem]" = []
        if not isinstance(raw_list, list):
            return results

        for item in raw_list:
            if not isinstance(item, dict):
                continue
            results.append(
                SmsStatusItem(
                    id=item.get("id"),
                    to=item.get("to"),
                    updated_at=item.get("updated_at"),
                    send_at=item.get("send_at"),
                    status=item.get("status"),
                )
            )

        return results

    def __enter__(self) -> "AqilasClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        """Close the underlying HTTP session."""
        try:
            self.session.close()
        except Exception:
            pass
        # Non-2xx: try to extract message
