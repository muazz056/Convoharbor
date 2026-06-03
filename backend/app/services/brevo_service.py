import requests
from flask import current_app


class BrevoService:
    def __init__(self, app):
        self.api_key = app.config.get('BREVO_API_KEY')
        if not self.api_key:
            raise ValueError("BREVO_API_KEY is not configured")
        self.sender_email = app.config.get('BREVO_SENDER_EMAIL')
        self.sender_name = app.config.get('BREVO_SENDER_NAME', 'ConvoPilot')
        self.base_url = 'https://api.brevo.com/v3'
        self.session = requests.Session()
        self.session.headers.update({
            'api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def send_transactional_email(self, to_email, subject, html_content, to_name=None):
        payload = {
            'sender': {
                'name': self.sender_name,
                'email': self.sender_email
            },
            'to': [
                {
                    'email': to_email,
                    'name': to_name or to_email
                }
            ],
            'subject': subject,
            'htmlContent': html_content
        }
        response = self.session.post(f'{self.base_url}/smtp/email', json=payload)
        response.raise_for_status()
        return response.json()

    def get_smtp_status(self):
        response = self.session.get(f'{self.base_url}/account')
        return response.json()


def send_email_brevo(subject, recipients, html_body, text_body=None):
    app = current_app._get_current_object()
    brevo = BrevoService(app)
    recipients_list = recipients if isinstance(recipients, list) else [recipients]
    for recipient in recipients_list:
        brevo.send_transactional_email(
            to_email=recipient,
            subject=subject,
            html_content=html_body
        )
