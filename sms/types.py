from dataclasses import dataclass

from typing import List, Optional


@dataclass
class APIError:
    success: bool = False
    message: str = ""


@dataclass
class CreditSuccess:
    success: bool = True
    credit: Optional[int] = None
    currency: Optional[str] = None


@dataclass
class SendSmsSuccess:
    success: bool = True
    message: Optional[str] = None
    bulk_id: Optional[str] = None
    cost: Optional[float] = None
    currency: Optional[str] = None


@dataclass
class SmsStatusItem:
    id: str
    to: str
    updated_at: Optional[str]
    send_at: Optional[str]
    status: Optional[str]


@dataclass
class SmsStatusSuccess:
    success: bool = True
    results: List[SmsStatusItem] = None
