from fastapi_mail import FastMail, MessageSchema
from app.core.mail import conf
import smtplib
from app.core.config import settings
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_ADDRESS = "yourgmail@gmail.com"
EMAIL_PASSWORD = "your_app_password"


async def send_login_email(email: str, ip: str):
    message = MessageSchema(
        subject="Admin Login Alert 🔐",
        recipients="tbamidele021@gmail.com",
        body=f"""
        Your admin account was just accessed.

        IP Address: {ip}

        If this was not you, please change your password immediately.
        """,
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)


def send_email(to_email: str, subject: str, message: str):

    msg = MIMEMultipart()
    msg["From"] = settings.EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(message, "plain"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()

    server.login(
        settings.EMAIL_ADDRESS,
        settings.EMAIL_PASSWORD
    )

    server.sendmail(
        settings.EMAIL_ADDRESS,
        to_email,
        msg.as_string()
    )

    server.quit()
