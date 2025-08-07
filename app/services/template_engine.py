from jinja2 import Template, Environment, BaseLoader, TemplateError
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.email import EmailTemplate
import logging

logger = logging.getLogger(__name__)


class DatabaseTemplateLoader(BaseLoader):
    def __init__(self, db: Session):
        self.db = db
    
    def get_source(self, environment, template_name):
        template = self.db.query(EmailTemplate).filter(
            EmailTemplate.name == template_name
        ).first()
        
        if not template:
            raise TemplateError(f"Template '{template_name}' not found")
        
        source = template.html_content
        mtime = template.updated_at.timestamp() if template.updated_at else 0
        
        def uptodate():
            current_template = self.db.query(EmailTemplate).filter(
                EmailTemplate.name == template_name
            ).first()
            if not current_template:
                return False
            current_mtime = current_template.updated_at.timestamp() if current_template.updated_at else 0
            return current_mtime == mtime
        
        return source, None, uptodate


class TemplateEngine:
    def __init__(self):
        self.environment = None
    
    def setup(self, db: Session):
        loader = DatabaseTemplateLoader(db)
        self.environment = Environment(
            loader=loader,
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def render_template(
        self,
        db: Session,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str, str]:
        
        template_record = db.query(EmailTemplate).filter(
            EmailTemplate.name == template_name
        ).first()
        
        if not template_record:
            raise ValueError(f"Template '{template_name}' not found")
        
        variables = variables or {}
        
        try:
            html_template = Template(template_record.html_content)
            html_content = html_template.render(**variables)
            
            text_content = None
            if template_record.text_content:
                text_template = Template(template_record.text_content)
                text_content = text_template.render(**variables)
            
            subject_template = Template(template_record.subject)
            subject = subject_template.render(**variables)
            
            return subject, html_content, text_content
            
        except Exception as e:
            logger.error(f"Error rendering template '{template_name}': {e}")
            raise TemplateError(f"Failed to render template: {e}")
    
    def validate_template(
        self,
        html_content: str,
        text_content: Optional[str] = None,
        subject: Optional[str] = None,
        test_variables: Optional[Dict[str, Any]] = None
    ) -> bool:
        
        try:
            test_vars = test_variables or {}
            
            Template(html_content).render(**test_vars)
            
            if text_content:
                Template(text_content).render(**test_vars)
            
            if subject:
                Template(subject).render(**test_vars)
            
            return True
            
        except Exception as e:
            logger.error(f"Template validation failed: {e}")
            raise TemplateError(f"Template validation failed: {e}")


template_engine = TemplateEngine()