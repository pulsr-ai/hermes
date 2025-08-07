from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.email import EmailStatus, WebhookStatus


class EmailTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    html_content: str
    text_content: Optional[str] = None
    example_variables: Optional[Dict[str, Any]] = None


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    example_variables: Optional[Dict[str, Any]] = None


class EmailTemplateResponse(EmailTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class EmailSend(BaseModel):
    to_email: EmailStr
    from_email: Optional[EmailStr] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    subject: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


class EmailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    message_id: str
    from_email: str
    to_email: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    status: EmailStatus
    direction: str
    template_id: Optional[int] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    error_message: Optional[str] = None


class EmailListResponse(BaseModel):
    emails: List[EmailResponse]
    total: int
    page: int = 1
    per_page: int = 50


class EmailFilter(BaseModel):
    to_email: Optional[EmailStr] = None
    from_email: Optional[EmailStr] = None
    status: Optional[EmailStatus] = None
    direction: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class WebhookBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=500)
    event_type: str = Field(..., pattern="^(email.received|email.sent|email.failed)$")
    active: bool = True
    secret_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=500)
    event_type: Optional[str] = Field(None, pattern="^(email.received|email.sent|email.failed)$")
    active: Optional[bool] = None
    secret_key: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


class WebhookResponse(WebhookBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    webhook_id: int
    email_id: int
    status: WebhookStatus
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    attempts: int
    created_at: datetime
    delivered_at: Optional[datetime] = None