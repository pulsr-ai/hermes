import asyncio
import email
from email.message import EmailMessage
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as SMTPServer
from datetime import datetime
import json
import uuid
from typing import Optional
from app.core.database import SessionLocal
from app.models.email import Email, EmailStatus
from app.services.webhook import trigger_webhook
import logging

logger = logging.getLogger(__name__)


class EmailHandler:
    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        try:
            message_data = envelope.content.decode('utf8', errors='replace')
            msg = email.message_from_string(message_data)
            
            from_email = envelope.mail_from
            to_emails = envelope.rcpt_tos
            
            message_id = msg.get('Message-ID', str(uuid.uuid4()))
            subject = msg.get('Subject', 'No Subject')
            
            html_content = None
            text_content = None
            attachments = []
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    
                    if "attachment" in content_disposition:
                        attachments.append({
                            'filename': part.get_filename(),
                            'content_type': content_type,
                            'size': len(part.get_payload())
                        })
                    elif content_type == "text/plain":
                        text_content = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    elif content_type == "text/html":
                        html_content = part.get_payload(decode=True).decode('utf-8', errors='replace')
            else:
                content_type = msg.get_content_type()
                payload = msg.get_payload(decode=True)
                if payload:
                    content = payload.decode('utf-8', errors='replace')
                    if content_type == "text/html":
                        html_content = content
                    else:
                        text_content = content
            
            headers = {}
            for key, value in msg.items():
                if key.lower() not in ['from', 'to', 'subject', 'message-id']:
                    headers[key] = value
            
            db = SessionLocal()
            try:
                for to_email in to_emails:
                    email_record = Email(
                        message_id=f"{message_id}-{to_email}",
                        from_email=from_email,
                        to_email=to_email,
                        subject=subject,
                        html_content=html_content,
                        text_content=text_content,
                        raw_content=message_data,
                        headers=headers,
                        attachments=attachments if attachments else None,
                        status=EmailStatus.RECEIVED,
                        direction="inbound",
                        received_at=datetime.utcnow()
                    )
                    db.add(email_record)
                    db.commit()
                    db.refresh(email_record)
                    
                    await trigger_webhook(db, "email.received", email_record)
                    
                    logger.info(f"Email received from {from_email} to {to_email}")
            finally:
                db.close()
            
            return '250 Message accepted for delivery'
            
        except Exception as e:
            logger.error(f"Error processing email: {str(e)}")
            return '554 Transaction failed'


class SMTPServerManager:
    def __init__(self, host: str = "0.0.0.0", port: int = 2525):
        self.host = host
        self.port = port
        self.controller = None
    
    def start(self):
        handler = EmailHandler()
        self.controller = Controller(
            handler,
            hostname=self.host,
            port=self.port
        )
        self.controller.start()
        logger.info(f"SMTP server started on {self.host}:{self.port}")
    
    def stop(self):
        if self.controller:
            self.controller.stop()
            logger.info("SMTP server stopped")


smtp_server = SMTPServerManager()