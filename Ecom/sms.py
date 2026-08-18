import logging
import requests

from django.conf import settings

logger = logging.getLogger(__name__)


class SMSService:

    BASE_URL = "https://2factor.in/API/V1"

    @staticmethod
    def format_phone(phone):
        """
        Convert phone numbers to 10-digit Indian format.
        Examples:
        +919988889905 -> 9988889905
        919988889905  -> 9988889905
        9988889905    -> 9988889905
        """

        phone = str(phone).strip()

        phone = phone.replace(" ", "")
        phone = phone.replace("-", "")
        phone = phone.replace("+", "")

        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]

        return phone

    @staticmethod
    def send_otp(phone, otp):

        if not settings.SMS_ENABLED:
            print("SMS DISABLED")
            return True

        phone = str(phone).strip()
        phone = phone.replace("+", "")
        phone = phone.replace("-", "")
        phone = phone.replace(" ", "")

        if phone.startswith("91") and len(phone) == 12:
            phone = phone[2:]

        url = f"{SMSService.BASE_URL}/{settings.TWO_FACTOR_API_KEY}/SMS/{phone}/{otp}"

       
        try:

            response = requests.get(url, timeout=20)

           
            data = response.json()

            if data.get("Status") == "Success":
                print("SMS SENT SUCCESSFULLY")
                return True

            print("SMS FAILED:", data)
            logger.error(data)
            return False

        except Exception as e:

            print("SMS ERROR:", str(e))
            logger.exception(e)
            return False

    @staticmethod
    def send_sms(phone, message):

        if not settings.SMS_ENABLED:
            return True

        phone = SMSService.format_phone(phone)

        url = (
            f"{SMSService.BASE_URL}/"
            f"{settings.TWO_FACTOR_API_KEY}/ADDON_SERVICES/SEND/TSMS"
        )

        payload = {
            "From": "HYZORA",
            "To": phone,
            "Msg": message,
        }

        try:

            response = requests.post(
                url,
                json=payload,
                timeout=20
            )

           
            data = response.json()

            if data.get("Status") == "Success":
                return True

            logger.error(data)
            return False

        except Exception as e:

            logger.exception(e)
            return False