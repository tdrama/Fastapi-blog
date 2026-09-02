import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from app.core.config import settings


def send_email(
    to_email: str,
    subject: str,
    message: str,
) -> bool:
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = settings.BREVO_API_KEY

    api_client = sib_api_v3_sdk.ApiClient(configuration)
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

    sender = sib_api_v3_sdk.SendSmtpEmailSender(
        name=settings.EMAIL_FROM_NAME,
        email=settings.EMAIL_ADDRESS,
    )

    email = sib_api_v3_sdk.SendSmtpEmail(
        sender=sender,
        to=[{"email": to_email}],
        subject=subject,
        text_content=message,
    )

    try:
        api_instance.send_transac_email(email)
        return True

    except ApiException as e:
        print(f"Brevo email error: {e}")
        return False
