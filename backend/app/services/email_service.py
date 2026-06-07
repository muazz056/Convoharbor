from flask import current_app
from flask_mail import Mail, Message
from threading import Thread
import os

mail = Mail()


def _get_app_name():
    """Get the app name from env, config, or fallback."""
    return (
        os.environ.get('APP_NAME')
        or current_app.config.get('APP_NAME')
        or 'Convoharbor'
    )


def send_email(subject, recipients, html_body, text_body=None):
    app = current_app._get_current_object()

    # Try Brevo REST API first
    try:
        from .brevo_service import send_email_brevo
        send_email_brevo(
            subject=subject,
            recipients=recipients,
            html_body=html_body,
            text_body=text_body
        )
        return
    except Exception as e:
        current_app.logger.warning(f"Brevo email failed, falling back to SMTP: {e}")

    # Fall back to Flask-Mail SMTP
    sender = (
        current_app.config.get('MAIL_USERNAME')
        or current_app.config.get('MAIL_DEFAULT_SENDER')
        or current_app.config.get('BREVO_SENDER_EMAIL')
    )
    if not sender:
        current_app.logger.error(
            "No email sender configured. Set BREVO_SENDER_EMAIL in .env"
        )
        return
    msg = Message(
        subject=subject,
        sender=sender,
        recipients=recipients if isinstance(recipients, list) else [recipients],
        html=html_body,
        body=text_body
    )

    Thread(
        target=_send_async,
        args=(app, msg)
    ).start()


def _send_async(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            current_app.logger.info("Email sent successfully")
        except Exception as e:
            current_app.logger.error(f"Email send error: {str(e)}")


def send_confirmation_email(user, confirmation_token):
    app_name = _get_app_name()
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000')
    confirmation_link = f"{frontend_url}/confirm-email?token={confirmation_token}"

    subject = f"Welcome to {app_name} - Please Confirm Your Email"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h2 {{
                color: #2c3e50;
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                margin-bottom: 30px;
            }}
            .button {{
                display: inline-block;
                padding: 14px 28px;
                background-color: #4CAF50;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 4px;
                font-weight: bold;
                text-align: center;
                margin: 20px 0;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eeeeee;
                color: #666666;
            }}
            .warning {{
                font-size: 12px;
                color: #666666;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Welcome to {app_name}!</h2>
            </div>
            <div class="content">
                <p>Thank you for registering with {app_name}. To complete your registration and activate your account,
                please click the button below:</p>
                <div style="text-align: center;">
                    <a href="{confirmation_link}" class="button">Confirm Email</a>
                </div>
                <p>Or copy and paste this link in your browser:</p>
                <p class="link">{confirmation_link}</p>
                <p class="warning">This link will expire in 24 hours.</p>
                <p>If you did not register for a {app_name} account, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>Best regards,<br>The {app_name} Team</p>
            </div>
        </div>
    </body>
    </html>
    """

    send_email(
        subject=subject,
        recipients=[user.email],
        html_body=html_body
    )


def send_password_reset_email(user, reset_code):
    """Send a 6-digit password reset code to the user's email."""
    app_name = _get_app_name()
    subject = f"Password Reset Code - {app_name}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                margin: 0;
                padding: 20px;
                background-color: #f4f4f7;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .header h2 {{
                color: #2c3e50;
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                margin-bottom: 30px;
            }}
            .code-box {{
                background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
                color: #ffffff;
                font-size: 32px;
                font-weight: bold;
                letter-spacing: 8px;
                text-align: center;
                padding: 20px;
                border-radius: 8px;
                margin: 24px 0;
                font-family: 'Courier New', monospace;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eeeeee;
                color: #666666;
                font-size: 14px;
            }}
            .warning {{
                font-size: 12px;
                color: #666666;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Password Reset Request</h2>
            </div>
            <div class="content">
                <p>Hi {user.first_name or 'there'},</p>
                <p>We received a request to reset the password for your {app_name} account. Use the verification code below to continue the reset process:</p>
                <div class="code-box">{reset_code}</div>
                <p>Enter this code on the password reset page to set a new password.</p>
                <p class="warning">This code will expire in 15 minutes. If you did not request a password reset, please ignore this email and your password will remain unchanged.</p>
            </div>
            <div class="footer">
                <p>Best regards,<br>The {app_name} Team</p>
            </div>
        </div>
    </body>
    </html>
    """

    send_email(
        subject=subject,
        recipients=[user.email],
        html_body=html_body
    )
