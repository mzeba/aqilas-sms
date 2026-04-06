import unittest
from unittest.mock import Mock
import os

import requests

from aqilas import (
    AqilasClient,
    AqilasNetworkError,
    AqilasNotInitializedError,
    AqilasResponseError,
    AqilasValidationError,
    get_credit,
    get_sms_status,
    send_sms,
)
from aqilas.base import CreditSuccess, SendSmsSuccess, SmsStatusItem, SmsStatusSuccess
from aqilas.main import close_client, init_client

from aqilas.utils import BASE_URL
from dotenv import load_dotenv

load_dotenv()

AQILAS_SMS_BASE_URL = os.environ.get("AQILAS_SMS_URL", BASE_URL)
AQILAS_SMS_TOKEN = os.environ.get("AQILAS_SMS_TOKEN")
AQILAS_SMS_SENDER = os.environ.get("AQILAS_SMS_SENDER", "AQILAS")
AQILAS_SMS_RECEIVER = os.environ.get("AQILAS_SMS_RECEIVER")


def make_response(*, ok=True, status_code=200, json_data=None, json_exc=None, text=""):
    response = Mock()
    response.ok = ok
    response.status_code = status_code
    response.text = text
    if json_exc is not None:
        response.json = Mock(side_effect=json_exc)
    else:
        response.json = Mock(return_value=json_data)
    return response


class TestAqilasClient(unittest.TestCase):
    def tearDown(self):
        close_client()

    def test_get_credit_returns_dataclass(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)

        client.session.get = Mock(
            return_value=make_response(
                json_data={"success": True, "credit": 12800, "currency": "XOF"}
            )
        )

        result = client.get_credit()
        self.assertIsInstance(result, CreditSuccess)
        self.assertEqual(result.credit, 12800)
        self.assertEqual(result.currency, "XOF")

    def test_get_credit_api_error_raises_response_exception(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.get = Mock(
            return_value=make_response(
                json_data={"success": False, "message": "Token invalide"}
            )
        )

        with self.assertRaises(AqilasResponseError) as ctx:
            client.get_credit()
        self.assertIn("Token invalide", str(ctx.exception))

    def test_get_credit_requires_success_field(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.get = Mock(
            return_value=make_response(json_data={"credit": 12800, "currency": "XOF"})
        )

        with self.assertRaises(AqilasResponseError):
            client.get_credit()

    def test_send_sms_returns_dataclass(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)

        client.session.post = Mock(
            return_value=make_response(
                json_data={
                    "success": True,
                    "message": "SMS ENVOYÉS",
                    "bulk_id": "3a63ac57-83db-49d2-abee-d720fadb017f",
                    "cost": 40,
                    "currency": "XOF",
                }
            )
        )

        res = client.send_sms(
            sender=AQILAS_SMS_SENDER,
            receivers=[AQILAS_SMS_RECEIVER],
            content="hi",
        )
        client.session.post.assert_called_once()
        self.assertIsInstance(res, SendSmsSuccess)
        self.assertEqual(res.bulk_id, "3a63ac57-83db-49d2-abee-d720fadb017f")
        self.assertEqual(res.message, "SMS ENVOYÉS")
        self.assertEqual(res.cost, 40.0)
        self.assertEqual(res.currency, "XOF")

    def test_get_sms_status_returns_items(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)

        client.session.get = Mock(
            return_value=make_response(
                json_data=[
                    {
                        "id": "90c102d7-2080-458e-8eae-7fce5a183d5d",
                        "to": "+22679989738",
                        "updated_at": None,
                        "send_at": "2021-04-29 08:52:10",
                        "status": "DELIVERY_SUCCESS",
                    },
                    {
                        "id": "660e60b2-5c55-4540-8325-1fd88baeb8b5",
                        "to": "+22690140954",
                        "updated_at": None,
                        "send_at": "2021-04-29 08:52:10",
                        "status": "DELIVERY_SUCCESS",
                    },
                ]
            )
        )

        res = client.get_sms_status("90c102d7-2080-458e-8eae-7fce5a183d5d")
        client.session.get.assert_called_once()
        self.assertIsInstance(res, SmsStatusSuccess)
        self.assertIsInstance(res.results, list)
        self.assertEqual(len(res.results), 2)
        item = res.results[0]
        self.assertIsInstance(item, SmsStatusItem)
        self.assertEqual(item.id, "90c102d7-2080-458e-8eae-7fce5a183d5d")
        self.assertEqual(item.to, "+22679989738")
        self.assertIsNone(item.updated_at)
        self.assertEqual(item.send_at, "2021-04-29 08:52:10")
        self.assertEqual(item.status, "DELIVERY_SUCCESS")

    def test_client_rejects_invalid_sender(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)

        with self.assertRaises(AqilasValidationError):
            client.send_sms(
                sender="bad!sender",
                receivers=[AQILAS_SMS_RECEIVER],
                content="hello",
            )

    def test_client_rejects_invalid_receiver(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)

        with self.assertRaises(AqilasValidationError):
            client.send_sms(
                sender=AQILAS_SMS_SENDER,
                receivers=["70000000"],
                content="hello",
            )

    def test_client_rejects_invalid_bulkid(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)

        with self.assertRaises(AqilasValidationError):
            client.get_sms_status("x")

    def test_network_errors_raise_specific_exception(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.get = Mock(side_effect=requests.ConnectionError("boom"))

        with self.assertRaises(AqilasNetworkError):
            client.get_credit()

    def test_api_errors_raise_response_exception(self):
        # Real Aqilas API returns HTTP 200 with success:false for application errors
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.post = Mock(
            return_value=make_response(
                ok=True,
                status_code=200,
                json_data={"success": False, "message": "Solde insuffisant"},
            )
        )

        with self.assertRaises(AqilasResponseError) as ctx:
            client.send_sms(
                sender=AQILAS_SMS_SENDER,
                receivers=[AQILAS_SMS_RECEIVER],
                content="hello",
            )
        self.assertIn("Solde insuffisant", str(ctx.exception))

    def test_server_errors_raise_response_exception(self):
        # HTTP 4xx/5xx from the server (not an application error) should also raise
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.post = Mock(
            return_value=make_response(
                ok=False,
                status_code=500,
                json_data={"message": "Internal Server Error"},
                text="Internal Server Error",
            )
        )

        with self.assertRaises(AqilasResponseError):
            client.send_sms(
                sender=AQILAS_SMS_SENDER,
                receivers=[AQILAS_SMS_RECEIVER],
                content="hello",
            )

    def test_invalid_json_raises_response_exception(self):
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.get = Mock(
            return_value=make_response(
                json_exc=ValueError("invalid json"),
                text="not json",
            )
        )

        with self.assertRaises(AqilasResponseError):
            client.get_credit()

    def test_send_sms_requires_success_field(self):
        # Response with no 'success' field should raise
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.post = Mock(
            return_value=make_response(
                json_data={"bulk_id": "abc-123", "message": "ok"}
            )
        )

        with self.assertRaises(AqilasResponseError):
            client.send_sms(
                sender="AQILAS",
                receivers=["+22670000000"],
                content="hello",
            )

    def test_send_sms_requires_bulk_id_in_success_payload(self):
        # success:true but missing bulk_id should raise
        client = AqilasClient(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.post = Mock(
            return_value=make_response(
                json_data={
                    "success": True,
                    "message": "SMS ENVOYÉS",
                    "cost": 40,
                    "currency": "XOF",
                }
            )
        )

        with self.assertRaises(AqilasResponseError):
            client.send_sms(
                sender="AQILAS",
                receivers=["+22670000000"],
                content="hello",
            )

    def test_get_credit_helper_uses_shared_client(self):
        client = init_client(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL)
        client.session.get = Mock(
            return_value=make_response(
                json_data={"success": True, "credit": 18, "currency": "XOF"}
            )
        )

        result = get_credit()

        self.assertEqual(result.credit, 18)
        self.assertEqual(result.currency, "XOF")

    def test_send_sms_helper_uses_temporary_client(self):
        original_send = AqilasClient.send_sms

        try:
            AqilasClient.send_sms = Mock(
                return_value=SendSmsSuccess(message="ok", bulk_id="bulk-123")
            )
            result = send_sms(
                sender=AQILAS_SMS_SENDER,
                receivers=[AQILAS_SMS_RECEIVER],
                content="hello",
                token=AQILAS_SMS_TOKEN,
                base_url=AQILAS_SMS_BASE_URL,
            )
        finally:
            AqilasClient.send_sms = original_send

        self.assertEqual(result.bulk_id, "bulk-123")

    def test_get_sms_status_helper_raises_when_client_not_initialized(self):
        with self.assertRaises(AqilasNotInitializedError):
            get_sms_status("bulk-123")


if __name__ == "__main__":
    unittest.main()
