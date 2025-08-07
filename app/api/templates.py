from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.email import EmailTemplate
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse
)
from app.services.template_engine import template_engine

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.post("/", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(EmailTemplate).filter(
        EmailTemplate.name == template.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template with name '{template.name}' already exists"
        )
    
    try:
        template_engine.validate_template(
            html_content=template.html_content,
            text_content=template.text_content,
            subject=template.subject,
            test_variables=template.example_variables
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template validation failed: {str(e)}"
        )
    
    db_template = EmailTemplate(**template.dict())
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    return db_template


@router.get("/", response_model=List[EmailTemplateResponse])
def list_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    templates = db.query(EmailTemplate).offset(skip).limit(limit).all()
    return templates


@router.get("/{template_id}", response_model=EmailTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found"
        )
    
    return template


@router.get("/name/{template_name}", response_model=EmailTemplateResponse)
def get_template_by_name(
    template_name: str,
    db: Session = Depends(get_db)
):
    template = db.query(EmailTemplate).filter(
        EmailTemplate.name == template_name
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with name '{template_name}' not found"
        )
    
    return template


@router.patch("/{template_id}", response_model=EmailTemplateResponse)
def update_template(
    template_id: int,
    template_update: EmailTemplateUpdate,
    db: Session = Depends(get_db)
):
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found"
        )
    
    update_data = template_update.dict(exclude_unset=True)
    
    if update_data:
        try:
            template_engine.validate_template(
                html_content=update_data.get('html_content', template.html_content),
                text_content=update_data.get('text_content', template.text_content),
                subject=update_data.get('subject', template.subject),
                test_variables=update_data.get('example_variables', template.example_variables)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template validation failed: {str(e)}"
            )
        
        for field, value in update_data.items():
            setattr(template, field, value)
        
        db.commit()
        db.refresh(template)
    
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found"
        )
    
    db.delete(template)
    db.commit()
    
    return None


@router.post("/{template_id}/preview")
def preview_template(
    template_id: int,
    variables: dict = {},
    db: Session = Depends(get_db)
):
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with id {template_id} not found"
        )
    
    try:
        subject, html_content, text_content = template_engine.render_template(
            db=db,
            template_name=template.name,
            variables=variables
        )
        
        return {
            "subject": subject,
            "html_content": html_content,
            "text_content": text_content
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template rendering failed: {str(e)}"
        )