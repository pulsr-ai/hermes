from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.models.email import Email, EmailTemplate, EmailStatus
from app.schemas.email import (
    EmailSend,
    EmailResponse,
    EmailListResponse,
    EmailFilter
)
from app.services.email_sender import email_sender
from app.services.template_engine import template_engine
from app.services.webhook import trigger_webhook
import asyncio

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.post("/send", response_model=EmailResponse, status_code=status.HTTP_201_CREATED)
async def send_email(
    email_data: EmailSend,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    subject = email_data.subject
    html_content = email_data.html_content
    text_content = email_data.text_content
    
    if email_data.template_name:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.name == email_data.template_name
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{email_data.template_name}' not found"
            )
        
        try:
            subject, html_content, text_content = template_engine.render_template(
                db=db,
                template_name=email_data.template_name,
                variables=email_data.template_variables
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template rendering failed: {str(e)}"
            )
        
        template_id = template.id
    else:
        template_id = None
        
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subject is required when not using a template"
            )
        
        if not html_content and not text_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either html_content or text_content is required"
            )
    
    try:
        email_record = email_sender.send_email(
            db=db,
            to_email=email_data.to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            from_email=email_data.from_email,
            cc=email_data.cc,
            bcc=email_data.bcc,
            attachments=email_data.attachments,
            template_id=template_id,
            template_variables=email_data.template_variables
        )
        
        if email_record.status == EmailStatus.SENT:
            background_tasks.add_task(
                trigger_webhook,
                db,
                "email.sent",
                email_record
            )
        else:
            background_tasks.add_task(
                trigger_webhook,
                db,
                "email.failed",
                email_record
            )
        
        return email_record
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}"
        )


@router.get("/", response_model=EmailListResponse)
def list_emails(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    to_email: Optional[str] = None,
    from_email: Optional[str] = None,
    status: Optional[EmailStatus] = None,
    direction: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Email)
    
    if to_email:
        query = query.filter(Email.to_email == to_email)
    
    if from_email:
        query = query.filter(Email.from_email == from_email)
    
    if status:
        query = query.filter(Email.status == status)
    
    if direction:
        query = query.filter(Email.direction == direction)
    
    if start_date:
        query = query.filter(Email.created_at >= start_date)
    
    if end_date:
        query = query.filter(Email.created_at <= end_date)
    
    total = query.count()
    
    emails = query.order_by(Email.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return EmailListResponse(
        emails=emails,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/received", response_model=EmailListResponse)
def list_received_emails(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    recipient: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Email).filter(Email.direction == "inbound")
    
    if recipient:
        query = query.filter(Email.to_email == recipient)
    
    if start_date:
        query = query.filter(Email.received_at >= start_date)
    
    if end_date:
        query = query.filter(Email.received_at <= end_date)
    
    total = query.count()
    
    emails = query.order_by(Email.received_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    return EmailListResponse(
        emails=emails,
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/{email_id}", response_model=EmailResponse)
def get_email(
    email_id: int,
    db: Session = Depends(get_db)
):
    email = db.query(Email).filter(Email.id == email_id).first()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )
    
    return email


@router.get("/message/{message_id}", response_model=EmailResponse)
def get_email_by_message_id(
    message_id: str,
    db: Session = Depends(get_db)
):
    email = db.query(Email).filter(Email.message_id == message_id).first()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with message_id '{message_id}' not found"
        )
    
    return email


@router.delete("/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email(
    email_id: int,
    db: Session = Depends(get_db)
):
    email = db.query(Email).filter(Email.id == email_id).first()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )
    
    db.delete(email)
    db.commit()
    
    return None


@router.post("/{email_id}/resend", response_model=EmailResponse)
async def resend_email(
    email_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    original_email = db.query(Email).filter(Email.id == email_id).first()
    
    if not original_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Email with id {email_id} not found"
        )
    
    if original_email.direction != "outbound":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only resend outbound emails"
        )
    
    try:
        email_record = email_sender.send_email(
            db=db,
            to_email=original_email.to_email,
            subject=original_email.subject,
            html_content=original_email.html_content,
            text_content=original_email.text_content,
            from_email=original_email.from_email,
            cc=original_email.cc,
            bcc=original_email.bcc,
            attachments=original_email.attachments,
            template_id=original_email.template_id,
            template_variables=original_email.template_variables
        )
        
        if email_record.status == EmailStatus.SENT:
            background_tasks.add_task(
                trigger_webhook,
                db,
                "email.sent",
                email_record
            )
        else:
            background_tasks.add_task(
                trigger_webhook,
                db,
                "email.failed",
                email_record
            )
        
        return email_record
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resend email: {str(e)}"
        )