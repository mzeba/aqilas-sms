import os
import json

from aqilas import send_sms, get_credit, get_sms_status

from aqilas.utils import BASE_URL
from dotenv import load_dotenv

load_dotenv()

AQILAS_SMS_BASE_URL = os.environ.get("AQILAS_SMS_URL", BASE_URL)
AQILAS_SMS_TOKEN = os.environ.get("AQILAS_SMS_TOKEN")
AQILAS_SMS_SENDER = os.environ.get("AQILAS_SMS_SENDER", "AQILAS")
AQILAS_SMS_RECEIVER = os.environ.get("AQILAS_SMS_RECEIVER")


print("Get credit with client safe mode...:")
print(get_credit(token=AQILAS_SMS_TOKEN, base_url=AQILAS_SMS_BASE_URL))

print("Check SMS status with client safe mode...:")
print(
    get_sms_status(
        bulk_id="3a63ac57-83db-49d2-abee-d720fadb017f",
        token=AQILAS_SMS_TOKEN,
        base_url=AQILAS_SMS_BASE_URL,
    )
)

print("Send SMS with client safe mode...:")
print(
    send_sms(
        sender=AQILAS_SMS_SENDER,
        receivers=[AQILAS_SMS_RECEIVER],
        content="Hello from Aqilas SMS!",
        token=AQILAS_SMS_TOKEN,
        base_url=AQILAS_SMS_BASE_URL,
    )
)
