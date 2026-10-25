from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentItem


DEFAULT_CONTENT = [
    ("program", "programming-tech", {"title": "Programming & Tech", "description": "Learn Python, SQL, and core programming concepts tailored for scientific research and data analysis.", "icon": "fa-code", "accent": "blue"}),
    ("program", "bioinformatics-data", {"title": "Bioinformatics & Data", "description": "Merge biology with data science. Master GeoPandas, Matplotlib, and computational biology tools.", "icon": "fa-dna", "accent": "emerald"}),
    ("program", "biological-sciences", {"title": "Biological Sciences", "description": "Workshops focusing on One Health, epidemiology, nanomedicine, and advanced veterinary sciences.", "icon": "fa-microscope", "accent": "purple"}),
    ("program", "ielts-preparation", {"title": "IELTS Preparation", "description": "Comprehensive guidance and practice sessions to achieve your target band score for studying abroad.", "icon": "fa-language", "accent": "red"}),
    ("program", "scholarship-guidance", {"title": "Scholarship Guidance", "description": "End-to-end support for higher education, application strategies, and finding global research opportunities.", "icon": "fa-graduation-cap", "accent": "yellow"}),
    ("program", "training-workshops", {"title": "Training & Workshops", "description": "Join practical workshops that turn research ideas into confident, hands-on skills.", "icon": "fa-chalkboard-teacher", "accent": "cyan"}),
    ("program", "custom-training", {"title": "Custom Training", "description": "Need specific research methodology or software training?", "icon": "fa-wand-magic-sparkles", "accent": "primary"}),
    ("program", "ai-research-vibe-coding", {"title": "AI-Powered Research & Vibe Coding", "description": "Master ethical AI integration for academic research, data analytics, prompt engineering, and Vibe Coding to build tech tools without traditional programming.", "icon": "fa-brain", "accent": "indigo"}),
    ("stat", "research-projects", {"value": "15+", "label": "Research Projects"}),
    ("stat", "active-students", {"value": "500+", "label": "Active Students"}),
    ("stat", "tech-workshops", {"value": "20+", "label": "Tech Workshops"}),
    ("stat", "innovation-focus", {"value": "100%", "label": "Innovation Focus"}),
]


def seed_default_content(db: Session) -> None:
    for kind, slug, payload in DEFAULT_CONTENT:
        exists = db.scalar(select(ContentItem.id).where(ContentItem.kind == kind, ContentItem.slug == slug))
        if exists is None:
            db.add(ContentItem(kind=kind, slug=slug, payload=payload))
    db.commit()
