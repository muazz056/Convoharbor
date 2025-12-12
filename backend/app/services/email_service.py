from flask import current_app
from flask_mail import Mail, Message
from threading import Thread

mail = Mail()

def send_async_email(app, msg):
    """Send email asynchronously."""
    with app.app_context():
        try:
            # Log email configuration
            current_app.logger.info(f"📧 Email Configuration:")
            current_app.logger.info(f"  Server: {app.config['MAIL_SERVER']}")
            current_app.logger.info(f"  Port: {app.config['MAIL_PORT']}")
            current_app.logger.info(f"  Username: {app.config['MAIL_USERNAME']}")
            current_app.logger.info(f"  TLS: {app.config['MAIL_USE_TLS']}")
            current_app.logger.info(f"  SSL: {app.config['MAIL_USE_SSL']}")
            
            # Log email details
            current_app.logger.info(f"📧 Sending email:")
            current_app.logger.info(f"  From: {msg.sender}")
            current_app.logger.info(f"  To: {msg.recipients}")
            current_app.logger.info(f"  Subject: {msg.subject}")
            
            # Attempt to send
            mail.send(msg)
            current_app.logger.info("✅ Email sent successfully!")
            
        except Exception as e:
            current_app.logger.error(f"❌ Error sending email: {str(e)}")
            current_app.logger.error(f"Error details:", exc_info=True)
            # In production, you might want to add retry logic or notify admins

def send_email(subject, recipients, html_body, text_body=None):
    """Send email with both HTML and plain text versions."""
    msg = Message(
        subject=subject,
        sender=current_app.config['MAIL_USERNAME'],  # Use configured email as sender
        recipients=recipients,
        html=html_body,
        body=text_body or html_body.replace('&lt;br&gt;', '\n').replace('&lt;/p&gt;', '\n\n')
    )
    
    # Send email asynchronously
    Thread(
        target=send_async_email,
        args=(current_app._get_current_object(), msg)
    ).start()

def send_confirmation_email(user, confirmation_token):
    """Send confirmation email to user."""
    confirmation_link = f"{current_app.config['FRONTEND_URL']}/confirm-email?token={confirmation_token}"
    
    subject = "Welcome to ConvoPilot - Please Confirm Your Email"
    
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
            .button:hover {{
                background-color: #45a049;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eeeeee;
                color: #666666;
            }}
            .link {{
                word-break: break-all;
                color: #2196F3;
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
                <h2>Welcome to ConvoPilot! 🚀</h2>
            </div>
            
            <div class="content">
                <p>Thank you for registering with ConvoPilot. To complete your registration and activate your account, 
                please click the button below:</p>
                
                <div style="text-align: center;">
                    <a href="{confirmation_link}" class="button">
                        Confirm Email
                    </a>
                </div>
                
                <p>Or copy and paste this link in your browser:</p>
                <p class="link">{confirmation_link}</p>
                
                <p class="warning">⚠️ This link will expire in 24 hours.</p>
                
                <p>If you did not register for a ConvoPilot account, please ignore this email.</p>
            </div>
            
            <div class="footer">
                <p>Best regards,<br>The ConvoPilot Team</p>
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
