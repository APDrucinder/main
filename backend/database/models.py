from __future__ import annotations

import uuid

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from .connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    subscription_tier = Column(String, default="free", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    platform_credentials = Column(JSONB, default=dict, nullable=True)


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    raw_text = Column(Text)
    parsed_data = Column(JSON)
    file_url = Column(String, nullable=True)
    uploaded_at = Column(DateTime, server_default=func.now(), nullable=False)


class JobPreference(Base):
    __tablename__ = "job_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    target_roles = Column(ARRAY(String), default=list)
    locations = Column(ARRAY(String), default=list)
    experience_years = Column(Integer, default=0)
    salary_min = Column(Integer, default=0)
    remote_ok = Column(Boolean, default=False, nullable=False)
    auto_apply_threshold = Column(Integer, default=75, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    salary_range = Column(String)
    apply_url = Column(String, unique=True, nullable=False)
    source = Column(String)
    posted_date = Column(DateTime)
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, index=True)
    match_score = Column(Integer)
    matched_skills = Column(ARRAY(String), default=list)
    missing_skills = Column(ARRAY(String), default=list)
    reasoning = Column(Text)
    status = Column(String, default="matched", nullable=False)
    platform = Column(String(50), nullable=True)
    manual_apply_url = Column(Text)
    applied_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    user_feedback = Column(String)


class UserApplicationStats(Base):
    __tablename__ = "user_application_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(DateTime, server_default=func.now(), nullable=False)
    applications_count = Column(Integer, default=0, nullable=False)
