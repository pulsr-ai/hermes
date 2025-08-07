import httpx
import hmac
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.email import Email, Webhook, WebhookDelivery, WebhookStatus
import asyncio
import logging

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self):
        self.max_retries = 3
        self.timeout = 30
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    async def send_webhook(
        self,
        db: Session,
        webhook: Webhook,
        email: Email
    ) -> WebhookDelivery:
        
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            email_id=email.id,
            status=WebhookStatus.PENDING,
            created_at=datetime.utcnow()
        )
        db.add(delivery)
        db.commit()
        
        payload = {
            "event": webhook.event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "email": {
                "id": email.id,
                "message_id": email.message_id,
                "from": email.from_email,
                "to": email.to_email,
                "subject": email.subject,
                "status": email.status.value,
                "direction": email.direction,
                "created_at": email.created_at.isoformat() if email.created_at else None,
                "html_content": email.html_content,
                "text_content": email.text_content,
                "attachments": email.attachments
            }
        }
        
        payload_json = json.dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Email-Service/1.0"
        }
        
        if webhook.headers:
            headers.update(webhook.headers)
        
        if webhook.secret_key:
            headers["X-Webhook-Signature"] = self._generate_signature(
                payload_json,
                webhook.secret_key
            )
        
        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_retries):
                delivery.attempts = attempt + 1
                
                try:
                    response = await client.post(
                        webhook.url,
                        content=payload_json,
                        headers=headers,
                        timeout=self.timeout
                    )
                    
                    delivery.response_status = response.status_code
                    delivery.response_body = response.text[:1000]
                    
                    if 200 <= response.status_code < 300:
                        delivery.status = WebhookStatus.SUCCESS
                        delivery.delivered_at = datetime.utcnow()
                        db.commit()
                        logger.info(f"Webhook delivered successfully to {webhook.url}")
                        return delivery
                    
                    if attempt == self.max_retries - 1:
                        delivery.status = WebhookStatus.FAILED
                        delivery.error_message = f"HTTP {response.status_code}: {response.text[:500]}"
                        db.commit()
                        logger.error(f"Webhook delivery failed after {self.max_retries} attempts")
                        return delivery
                    
                except Exception as e:
                    delivery.error_message = str(e)
                    
                    if attempt == self.max_retries - 1:
                        delivery.status = WebhookStatus.FAILED
                        db.commit()
                        logger.error(f"Webhook delivery failed: {e}")
                        return delivery
                
                await asyncio.sleep(2 ** attempt)
        
        return delivery


webhook_service = WebhookService()


async def trigger_webhook(db: Session, event_type: str, email: Email):
    webhooks = db.query(Webhook).filter(
        Webhook.event_type == event_type,
        Webhook.active == True
    ).all()
    
    for webhook in webhooks:
        try:
            await webhook_service.send_webhook(db, webhook, email)
        except Exception as e:
            logger.error(f"Error triggering webhook {webhook.id}: {e}")