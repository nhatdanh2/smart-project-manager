"""Aggregate import for all SQLAlchemy models.

Importing this module ensures every model is registered with Base.metadata
before create_all() or Alembic autogenerate runs.
"""
from app.models.user import User
from app.models.project import Project, ProjectMember
from app.models.task import Task, TaskHistory
from app.models.meeting import Meeting, ExtractedTask, AIReport
from app.models.contribution import ContributionScore
from app.models.digest import DigestEmail
from app.models.notification import Notification
from app.models.comment import TaskComment
from app.models.gdpr_audit import GDPRAuditLog
from app.models.webhook import WebhookSubscription, WebhookDelivery
from app.models.saml import SAMLSettings, SAMLAssertionLog
from app.models.push import PushDevice

__all__ = [
    "User",
    "Project",
    "ProjectMember",
    "Task",
    "TaskHistory",
    "Meeting",
    "ExtractedTask",
    "AIReport",
    "ContributionScore",
    "DigestEmail",
    "Notification",
    "TaskComment",
    "GDPRAuditLog",
    "WebhookSubscription",
    "WebhookDelivery",
    "SAMLSettings",
    "SAMLAssertionLog",
    "PushDevice",
]
