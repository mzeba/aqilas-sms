import unittest
from unittest.mock import Mock

from aqilas import (
    AqilasClient,
    CreditSuccess,
    SendSmsSuccess,
    SmsStatusItem,
    SmsStatusSuccess,
)


class TestAqilasClient(unittest.TestCase):
    def test_get_credit_returns_dataclass(self):
        client = AqilasClient(token="tok", base_url="https://api.test/")

        # Mock session.get to return an object with json()
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.ok = True
        mock_resp.json = Mock(return_value={"credit": 42, "currency": "EUR"})
        client.session.get = Mock(return_value=mock_resp)

        result = client.get_credit()
        self.assertIsInstance(result, CreditSuccess)
        self.assertEqual(result.credit, 42)
        self.assertEqual(result.currency, "EUR")

    def test_send_sms_returns_dataclass(self):
        client = AqilasClient(token="tok", base_url="https://api.test/")

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.ok = True
        mock_resp.json = Mock(return_value={"bulk_id": "abc123", "message": "ok"})
        client.session.post = Mock(return_value=mock_resp)

        res = client.send_sms(sender="App", receivers=["+331234"], content="hi")
        client.session.post.assert_called_once()
        self.assertIsInstance(res, SendSmsSuccess)
        self.assertEqual(res.bulk_id, "abc123")
        self.assertEqual(res.message, "ok")

    def test_get_sms_status_returns_items(self):
        client = AqilasClient(token="tok", base_url="https://api.test/")

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.ok = True
        mock_resp.json = Mock(
            return_value=[
                {
                    "id": "1",
                    "to": "+331234",
                    "status": "delivered",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "send_at": "2025-01-01T00:00:00Z",
                }
            ]
        )
        client.session.get = Mock(return_value=mock_resp)

        res = client.get_sms_status("bulk-1")
        client.session.get.assert_called_once()
        self.assertIsInstance(res, SmsStatusSuccess)
        self.assertIsInstance(res.results, list)
        self.assertEqual(len(res.results), 1)
        item = res.results[0]
        self.assertIsInstance(item, SmsStatusItem)
        self.assertEqual(item.status, "delivered")
        self.assertEqual(item.to, "+331234")


if __name__ == "__main__":
    unittest.main()
