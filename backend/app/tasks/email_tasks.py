from flask import current_app
from flask_mail import Message


def send_email_smtp(app, subject, recipients, html_body, text_body=None, sender=None):
    with app.app_context():
        try:
            from ..services.email_service import mail
            msg = Message(
                subject=subject,
                sender=sender or app.config['MAIL_USERNAME'],
                recipients=recipients if isinstance(recipients, list) else [recipients],
                html=html_body,
                body=text_body
            )
            mail.send(msg)
            current_app.logger.info(f"Email sent to {recipients}")
        except Exception as e:
            current_app.logger.error(f"Email send error: {str(e)}")
