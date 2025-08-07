import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import dkim
import dns.resolver
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
from pathlib import Path
from app.core.config import settings
from app.models.email import Email, EmailStatus
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self):
        self.smtp_host = settings.OUTBOUND_SMTP_HOST
        self.smtp_port = settings.OUTBOUND_SMTP_PORT
        self.smtp_user = settings.OUTBOUND_SMTP_USER
        self.smtp_password = settings.OUTBOUND_SMTP_PASSWORD
        self.use_tls = settings.OUTBOUND_SMTP_USE_TLS
        self.dkim_private_key_path = settings.DKIM_PRIVATE_KEY_PATH
        self.dkim_selector = settings.DKIM_SELECTOR
        self.domain = settings.SMTP_DOMAIN
    
    def _load_dkim_key(self) -> Optional[bytes]:
        if not self.dkim_private_key_path:
            return None
        
        try:
            key_path = Path(self.dkim_private_key_path)
            if key_path.exists():
                return key_path.read_bytes()
        except Exception as e:
            logger.warning(f"Could not load DKIM key: {e}")
        
        return None
    
    def _get_mx_records(self, domain: str) -> List[str]:
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            sorted_mx = sorted(mx_records, key=lambda x: x.preference)
            return [str(mx.exchange).rstrip('.') for mx in sorted_mx]
        except Exception as e:
            logger.error(f"Failed to get MX records for {domain}: {e}")
            return []
    
    def _send_direct(self, message: MIMEMultipart, from_email: str, recipients: List[str]):
        recipient_domains = {}
        for recipient in recipients:
            domain = recipient.split('@')[1]
            if domain not in recipient_domains:
                recipient_domains[domain] = []
            recipient_domains[domain].append(recipient)
        
        for domain, domain_recipients in recipient_domains.items():
            mx_servers = self._get_mx_records(domain)
            if not mx_servers:
                raise Exception(f"No MX records found for domain {domain}")
            
            sent = False
            last_error = None
            
            for mx_server in mx_servers:
                try:
                    with smtplib.SMTP(mx_server, 25, timeout=30) as server:
                        server.ehlo(self.domain)
                        server.starttls()
                        server.ehlo(self.domain)
                        server.send_message(message, from_email, domain_recipients)
                        sent = True
                        logger.info(f"Email sent directly to {mx_server} for domain {domain}")
                        break
                except Exception as e:
                    last_error = e
                    logger.warning(f"Failed to send to {mx_server}: {e}")
                    continue
            
            if not sent:
                raise Exception(f"Failed to send email to any MX server for {domain}: {last_error}")
    
    def _sign_message(self, message: MIMEMultipart) -> MIMEMultipart:
        dkim_key = self._load_dkim_key()
        if not dkim_key:
            return message
        
        try:
            message_string = message.as_string()
            signature = dkim.sign(
                message_string.encode(),
                self.dkim_selector.encode(),
                self.domain.encode(),
                dkim_key,
                include_headers=[b"From", b"To", b"Subject", b"Date", b"Message-ID"]
            )
            
            signature_header = signature.decode().replace("DKIM-Signature: ", "")
            message["DKIM-Signature"] = signature_header
            
        except Exception as e:
            logger.warning(f"Could not sign message with DKIM: {e}")
        
        return message
    
    def send_email(
        self,
        db: Session,
        to_email: str,
        subject: str,
        html_content: Optional[str] = None,
        text_content: Optional[str] = None,
        from_email: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        template_id: Optional[int] = None,
        template_variables: Optional[Dict[str, Any]] = None
    ) -> Email:
        
        if not from_email:
            from_email = self.smtp_user or f"noreply@{self.domain}"
        
        message_id = f"<{uuid.uuid4()}@{self.domain}>"
        
        email_record = Email(
            message_id=message_id,
            from_email=from_email,
            to_email=to_email,
            cc=cc,
            bcc=bcc,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            status=EmailStatus.PENDING,
            direction="outbound",
            template_id=template_id,
            template_variables=template_variables,
            created_at=datetime.utcnow()
        )
        db.add(email_record)
        db.commit()
        
        try:
            message = MIMEMultipart("alternative")
            message["From"] = from_email
            message["To"] = to_email
            message["Subject"] = subject
            message["Message-ID"] = message_id
            message["Date"] = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            if cc:
                message["Cc"] = ", ".join(cc)
            
            if text_content:
                part1 = MIMEText(text_content, "plain")
                message.attach(part1)
            
            if html_content:
                part2 = MIMEText(html_content, "html")
                message.attach(part2)
            
            if attachments:
                for attachment in attachments:
                    if "content" in attachment and "filename" in attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment["content"])
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename= {attachment['filename']}"
                        )
                        message.attach(part)
            
            message = self._sign_message(message)
            
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            if self.smtp_host:
                context = ssl.create_default_context()
                
                if self.use_tls:
                    with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                        server.starttls(context=context)
                        if self.smtp_user and self.smtp_password:
                            server.login(self.smtp_user, self.smtp_password)
                        server.send_message(message, from_email, recipients)
                else:
                    with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                        if self.smtp_user and self.smtp_password:
                            server.login(self.smtp_user, self.smtp_password)
                        server.send_message(message, from_email, recipients)
            else:
                self._send_direct(message, from_email, recipients)
            
            email_record.status = EmailStatus.SENT
            email_record.sent_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            email_record.status = EmailStatus.FAILED
            email_record.error_message = str(e)
            db.commit()
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise
        
        return email_record


email_sender = EmailSender()