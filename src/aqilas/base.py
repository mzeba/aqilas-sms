from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .types import (
    AqilasError,
    AqilasNetworkError,
    AqilasResponseError,
    AqilasValidationError,
    CreditSuccess,
    SendSmsSuccess,
    SmsStatusItem,
    SmsStatusSuccess,
)
from .utils import BASE_URL


class AqilasClient:
    """Client for the Aqilas SMS API.

    Improvements in this implementation:
    - Context manager support (``with AqilasClient(...) as client:``)
    - Simple retry/backoff strategy for transient failures
    - Centralized response mapping to typed dataclasses
    - Logging for debug/troubleshooting
    """

    _SENDER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{1,10}$")
    _PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
    _BULK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")

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
        self._validate_token(token)
        self._validate_base_url(base_url)
        self._validate_timeout(timeout)
        self._validate_retry_options(retries, backoff_factor, status_forcelist)

        # Normalize base_url to always end with a single '/'
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token.strip()
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

    @classmethod
    def _validate_token(cls, token: str) -> None:
        if not isinstance(token, str) or not token.strip():
            raise AqilasValidationError("token must be a non-empty string")

    @classmethod
    def _validate_base_url(cls, base_url: str) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise AqilasValidationError("base_url must be a non-empty string")
        if not re.match(r"^https?://", base_url.strip()):
            raise AqilasValidationError("base_url must start with http:// or https://")

    @classmethod
    def _validate_timeout(cls, timeout: Optional[float]) -> None:
        if timeout is None:
            return
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise AqilasValidationError("timeout must be a positive number or None")

    @classmethod
    def _validate_retry_options(
        cls,
        retries: int,
        backoff_factor: float,
        status_forcelist: Iterable[int],
    ) -> None:
        if not isinstance(retries, int) or retries < 0:
            raise AqilasValidationError("retries must be a non-negative integer")
        if not isinstance(backoff_factor, (int, float)) or backoff_factor < 0:
            raise AqilasValidationError("backoff_factor must be a non-negative number")
        if not isinstance(status_forcelist, Iterable):
            raise AqilasValidationError("status_forcelist must be an iterable of ints")

        normalized = tuple(status_forcelist)
        if not normalized or not all(
            isinstance(status_code, int) and 100 <= status_code <= 599
            for status_code in normalized
        ):
            raise AqilasValidationError(
                "status_forcelist must contain valid HTTP status codes"
            )

    @classmethod
    def _validate_sender(cls, sender: str) -> None:
        if not isinstance(sender, str) or not sender.strip():
            raise AqilasValidationError("sender must be a non-empty string")
        normalized_sender = sender.strip()
        if len(normalized_sender) > 11:
            raise AqilasValidationError("sender must be at most 11 characters long")
        if not cls._SENDER_PATTERN.fullmatch(normalized_sender):
            raise AqilasValidationError(
                "sender must contain only letters, digits, spaces, hyphens, or underscores"
            )

    @classmethod
    def _validate_receivers(cls, receivers: List[str]) -> List[str]:
        if not isinstance(receivers, list) or not receivers:
            raise AqilasValidationError(
                "receivers must be a non-empty list of phone numbers"
            )

        normalized_receivers: List[str] = []
        for receiver in receivers:
            if not isinstance(receiver, str) or not receiver.strip():
                raise AqilasValidationError(
                    "each receiver must be a non-empty phone number string"
                )
            normalized_receiver = receiver.strip()
            if not cls._PHONE_PATTERN.fullmatch(normalized_receiver):
                raise AqilasValidationError(
                    "receivers must use an international phone format, for example +22670000000"
                )
            normalized_receivers.append(normalized_receiver)

        return normalized_receivers

    @classmethod
    def _validate_content(cls, content: str) -> None:
        if not isinstance(content, str) or not content.strip():
            raise AqilasValidationError("content must be a non-empty string")
        if len(content) > 1600:
            raise AqilasValidationError("content must be at most 1600 characters long")

    @classmethod
    def _validate_bulk_id(cls, bulk_id: str) -> str:
        if not isinstance(bulk_id, str) or not bulk_id.strip():
            raise AqilasValidationError("bulk_id must be a non-empty string")
        normalized_bulk_id = bulk_id.strip()
        if not cls._BULK_ID_PATTERN.fullmatch(normalized_bulk_id):
            raise AqilasValidationError(
                "bulk_id must be 3 to 128 characters and contain only letters, digits, dots, hyphens, or underscores"
            )
        return normalized_bulk_id

    @staticmethod
    def _extract_error_message(data: Any, fallback: str) -> str:
        if isinstance(data, dict):
            for key in ("message", "error", "detail"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return fallback

    @staticmethod
    def _raise_network_error(operation: str, exc: requests.RequestException) -> None:
        raise AqilasNetworkError(
            f"network error during {operation}: {exc}",
            original_exception=exc,
        ) from exc

    @staticmethod
    def _parse_json(resp: requests.Response, *, operation: str) -> Any:
        try:
            return resp.json()
        except ValueError as exc:
            if not resp.ok:
                raise AqilasResponseError(
                    f"Aqilas API returned HTTP {resp.status_code} during {operation}",
                    status_code=resp.status_code,
                    payload=resp.text,
                ) from exc
            raise AqilasResponseError(
                f"invalid JSON returned by Aqilas API during {operation}",
                status_code=resp.status_code,
                payload=resp.text,
            ) from exc

    @staticmethod
    def _require_success_response(
        resp: requests.Response,
        data: Any,
        *,
        operation: str,
    ) -> None:
        if resp.ok:
            return

        message = AqilasClient._extract_error_message(
            data,
            resp.text
            or f"Aqilas API returned HTTP {resp.status_code} during {operation}",
        )
        raise AqilasResponseError(
            message,
            status_code=resp.status_code,
            payload=data,
        )

    @staticmethod
    def _require_mapping(data: Any, *, operation: str) -> dict:
        if not isinstance(data, dict):
            raise AqilasResponseError(
                f"invalid response payload for {operation}: expected a JSON object",
                payload=data,
            )
        return data

    @staticmethod
    def _require_non_empty_string(
        value: Any, *, field_name: str, operation: str
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AqilasResponseError(
                f"invalid response payload for {operation}: missing {field_name}",
                payload={field_name: value},
            )
        return value.strip()

    @staticmethod
    def _coerce_optional_float(
        value: Any, *, field_name: str, operation: str
    ) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        raise AqilasResponseError(
            f"invalid response payload for {operation}: {field_name} must be numeric",
            payload={field_name: value},
        )

    @staticmethod
    def _coerce_optional_int(
        value: Any, *, field_name: str, operation: str
    ) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        raise AqilasResponseError(
            f"invalid response payload for {operation}: {field_name} must be an integer",
            payload={field_name: value},
        )

    @staticmethod
    def _format_error(exc: AqilasError) -> str:
        if isinstance(exc, AqilasResponseError):
            if exc.status_code is not None:
                return f"[HTTP {exc.status_code}] {exc}"
            return f"[erreur API] {exc}"
        if isinstance(exc, AqilasNetworkError):
            return f"[reseau] {exc}"
        if isinstance(exc, AqilasValidationError):
            return f"[validation] {exc}"
        return f"[erreur] {exc}"

    def _to_safe_result(self, operation: str, fn, *args, **kwargs) -> Dict[str, Any]:
        try:
            result = fn(*args, **kwargs)
        except AqilasError as exc:
            error: Dict[str, Any] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "formatted": self._format_error(exc),
            }
            if isinstance(exc, AqilasResponseError):
                error["status_code"] = exc.status_code
                error["payload"] = exc.payload
            return {"ok": False, "operation": operation, "error": error}

        if hasattr(result, "to_dict"):
            data = result.to_dict()
        else:
            data = result
        return {"ok": True, "operation": operation, "data": data}

    def safe_get_credit(self) -> Dict[str, Any]:
        """Get credit and always return a serializable dict result."""
        return self._to_safe_result("get_credit", self.get_credit)

    def safe_send_sms(
        self,
        sender: str,
        receivers: List[str],
        content: str,
    ) -> Dict[str, Any]:
        """Send SMS and always return a serializable dict result."""
        return self._to_safe_result(
            "send_sms", self.send_sms, sender, receivers, content
        )

    def safe_get_sms_status(self, bulk_id: str) -> Dict[str, Any]:
        """Get SMS status and always return a serializable dict result."""
        return self._to_safe_result("get_sms_status", self.get_sms_status, bulk_id)

    def get_credit(self) -> CreditSuccess:
        """Fetch account credit and return a typed dataclass."""
        try:
            resp = self.session.get(self._url("credit"), timeout=self.timeout)
        except requests.RequestException as exc:
            self.logger.debug("network error in get_credit: %s", exc)
            self._raise_network_error("get_credit", exc)

        return self._map_credit_response(resp)

    def _map_credit_response(self, resp: requests.Response) -> CreditSuccess:
        data = self._parse_json(resp, operation="get_credit")
        self._require_success_response(resp, data, operation="get_credit")
        payload = self._require_mapping(data, operation="get_credit")

        success = payload.get("success")
        if not isinstance(success, bool):
            raise AqilasResponseError(
                "invalid response payload for get_credit: missing or non-boolean 'success' field",
                status_code=resp.status_code,
                payload=payload,
            )

        if not success:
            raise AqilasResponseError(
                self._extract_error_message(payload, "credit request failed"),
                status_code=resp.status_code,
                payload=payload,
            )

        if "credit" not in payload:
            raise AqilasResponseError(
                "invalid response payload for get_credit: missing credit",
                status_code=resp.status_code,
                payload=payload,
            )

        credit = self._coerce_optional_int(
            payload.get("credit"),
            field_name="credit",
            operation="get_credit",
        )
        currency = payload.get("currency")
        if currency is not None and not isinstance(currency, str):
            raise AqilasResponseError(
                "invalid response payload for get_credit: currency must be a string",
                status_code=resp.status_code,
                payload=payload,
            )

        return CreditSuccess(credit=credit, currency=currency)

    def send_sms(
        self, sender: str, receivers: List[str], content: str
    ) -> SendSmsSuccess:
        """Send an SMS and return a typed response.

        Args:
            sender: sender id
            receivers: list of phone numbers
            content: message text
        """
        self._validate_sender(sender)
        normalized_receivers = self._validate_receivers(receivers)
        self._validate_content(content)

        payload = {"from": sender.strip(), "to": normalized_receivers, "text": content}
        try:
            resp = self.session.post(
                self._url("sms"), json=payload, timeout=self.timeout
            )
        except requests.RequestException as exc:
            self.logger.debug("network error in send_sms: %s", exc)
            self._raise_network_error("send_sms", exc)

        return self._map_send_response(resp)

    def _map_send_response(self, resp: requests.Response) -> SendSmsSuccess:
        data = self._parse_json(resp, operation="send_sms")
        self._require_success_response(resp, data, operation="send_sms")
        payload = self._require_mapping(data, operation="send_sms")

        success = payload.get("success")
        if not isinstance(success, bool):
            raise AqilasResponseError(
                "invalid response payload for send_sms: missing or non-boolean 'success' field",
                status_code=resp.status_code,
                payload=payload,
            )

        if not success:
            raise AqilasResponseError(
                self._extract_error_message(payload, "send_sms failed"),
                status_code=resp.status_code,
                payload=payload,
            )

        bulk_id = self._require_non_empty_string(
            payload.get("bulk_id"),
            field_name="bulk_id",
            operation="send_sms",
        )
        message = payload.get("message")
        if message is not None and not isinstance(message, str):
            raise AqilasResponseError(
                "invalid response payload for send_sms: message must be a string",
                status_code=resp.status_code,
                payload=payload,
            )

        currency = payload.get("currency")
        if currency is not None and not isinstance(currency, str):
            raise AqilasResponseError(
                "invalid response payload for send_sms: currency must be a string",
                status_code=resp.status_code,
                payload=payload,
            )

        return SendSmsSuccess(
            message=message,
            bulk_id=bulk_id,
            cost=self._coerce_optional_float(
                payload.get("cost"),
                field_name="cost",
                operation="send_sms",
            ),
            currency=currency,
        )

    def get_sms_status(self, bulk_id: str) -> SmsStatusSuccess:
        """Return delivery/status information for a bulk SMS identified by bulk_id."""
        normalized_bulk_id = self._validate_bulk_id(bulk_id)

        try:
            resp = self.session.get(
                self._url(f"sms/{normalized_bulk_id}"),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            self.logger.debug("network error in get_sms_status: %s", exc)
            self._raise_network_error("get_sms_status", exc)

        return self._map_status_response(resp)

    def _map_status_response(self, resp: requests.Response) -> SmsStatusSuccess:
        data = self._parse_json(resp, operation="get_sms_status")
        self._require_success_response(resp, data, operation="get_sms_status")

        if not isinstance(data, list):
            raise AqilasResponseError(
                "invalid response payload for get_sms_status: expected a JSON array",
                status_code=resp.status_code,
                payload=data,
            )

        return SmsStatusSuccess(results=self._map_status_items(data))

    def _map_status_items(self, raw_list: Any) -> List[SmsStatusItem]:
        results: List[SmsStatusItem] = []
        if not isinstance(raw_list, list):
            raise AqilasResponseError(
                "invalid response payload for get_sms_status: results must be a list",
                payload=raw_list,
            )

        for item in raw_list:
            if not isinstance(item, dict):
                raise AqilasResponseError(
                    "invalid response payload for get_sms_status: each result must be an object",
                    payload=item,
                )

            status_id = self._require_non_empty_string(
                item.get("id"),
                field_name="id",
                operation="get_sms_status",
            )
            recipient = self._require_non_empty_string(
                item.get("to"),
                field_name="to",
                operation="get_sms_status",
            )

            updated_at = item.get("updated_at")
            if updated_at is not None and not isinstance(updated_at, str):
                raise AqilasResponseError(
                    "invalid response payload for get_sms_status: updated_at must be a string",
                    payload=item,
                )

            send_at = item.get("send_at")
            if send_at is not None and not isinstance(send_at, str):
                raise AqilasResponseError(
                    "invalid response payload for get_sms_status: send_at must be a string",
                    payload=item,
                )

            status = item.get("status")
            if status is not None and not isinstance(status, str):
                raise AqilasResponseError(
                    "invalid response payload for get_sms_status: status must be a string",
                    payload=item,
                )

            results.append(
                SmsStatusItem(
                    id=status_id,
                    to=recipient,
                    updated_at=updated_at,
                    send_at=send_at,
                    status=status,
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
