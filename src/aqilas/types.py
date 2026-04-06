from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


class AqilasError(Exception):
    """Base exception for Aqilas client errors."""


class AqilasValidationError(AqilasError, ValueError):
    """Raised when caller input is invalid."""


class AqilasNotInitializedError(AqilasError, RuntimeError):
    """Raised when the shared module-level client is not initialized."""


class AqilasNetworkError(AqilasError):
    """Raised when the HTTP request to the Aqilas API fails."""

    def __init__(self, message: str, *, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.original_exception = original_exception


class AqilasResponseError(AqilasError):
    """Raised when the Aqilas API returns an error or invalid payload."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        payload: Optional[object] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass
class CreditSuccess:
    success: bool = True
    credit: Optional[int] = None
    currency: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SendSmsSuccess:
    success: bool = True
    message: Optional[str] = None
    bulk_id: Optional[str] = None
    cost: Optional[float] = None
    currency: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SmsStatusItem:
    id: str
    to: str
    updated_at: Optional[str]
    send_at: Optional[str]
    status: Optional[str]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SmsStatusSuccess:
    success: bool = True
    results: List[SmsStatusItem] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)
