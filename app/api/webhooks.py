from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.email import Webhook, WebhookDelivery
from app.schemas.email import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookDeliveryResponse
)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    webhook: WebhookCreate,
    db: Session = Depends(get_db)
):
    db_webhook = Webhook(**webhook.dict())
    db.add(db_webhook)
    db.commit()
    db.refresh(db_webhook)
    
    return db_webhook


@router.get("/", response_model=List[WebhookResponse])
def list_webhooks(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(Webhook)
    
    if active_only:
        query = query.filter(Webhook.active == True)
    
    webhooks = query.offset(skip).limit(limit).all()
    return webhooks


@router.get("/{webhook_id}", response_model=WebhookResponse)
def get_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found"
        )
    
    return webhook


@router.patch("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: int,
    webhook_update: WebhookUpdate,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found"
        )
    
    update_data = webhook_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(webhook, field, value)
    
    db.commit()
    db.refresh(webhook)
    
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found"
        )
    
    db.delete(webhook)
    db.commit()
    
    return None


@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliveryResponse])
def get_webhook_deliveries(
    webhook_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found"
        )
    
    deliveries = db.query(WebhookDelivery).filter(
        WebhookDelivery.webhook_id == webhook_id
    ).order_by(
        WebhookDelivery.created_at.desc()
    ).offset(skip).limit(limit).all()
    
    return deliveries


@router.post("/{webhook_id}/test", response_model=dict)
async def test_webhook(
    webhook_id: int,
    db: Session = Depends(get_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with id {webhook_id} not found"
        )
    
    from app.models.email import Email, EmailStatus
    from app.services.webhook import webhook_service
    from datetime import datetime
    import uuid
    
    test_email = Email(
        message_id=f"test-{uuid.uuid4()}",
        from_email="test@example.com",
        to_email="recipient@example.com",
        subject="Test Webhook Email",
        html_content="<p>This is a test email for webhook testing</p>",
        text_content="This is a test email for webhook testing",
        status=EmailStatus.SENT,
        direction="outbound",
        created_at=datetime.utcnow(),
        sent_at=datetime.utcnow()
    )
    
    db.add(test_email)
    db.commit()
    
    try:
        delivery = await webhook_service.send_webhook(db, webhook, test_email)
        
        return {
            "success": delivery.status.value == "success",
            "status": delivery.status.value,
            "response_status": delivery.response_status,
            "response_body": delivery.response_body,
            "error_message": delivery.error_message
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test webhook: {str(e)}"
        )
    finally:
        db.delete(test_email)
        db.commit()