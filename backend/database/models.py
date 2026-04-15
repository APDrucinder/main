from sqlalchemy import (
    Column, String, Integer, Boolean,
    DateTime, JSON, ForeignKey, ARRAY, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .connection import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    subscription_tier = Column(String, default="free")
    created_at = Column(DateTime, server_default=func.now())

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    raw_text = Column(Text)
    parsed_data = Column(JSON)
    file_url = Column(String, nullable=True)
    uploaded_at = Column(DateTime, server_default=func.now())

class JobPreference(Base):
    __tablename__ = "job_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_roles = Column(ARRAY(String))
    locations = Column(ARRAY(String))
    experience_years = Column(Integer)
    salary_min = Column(Integer)
    remote_ok = Column(Boolean, default=False)
    auto_apply_threshold = Column(Integer, default=75)
    is_active = Column(Boolean, default=True)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    salary_range = Column(String)
    apply_url = Column(String, unique=True)
    source = Column(String)
    posted_date = Column(DateTime)
    scraped_at = Column(DateTime, server_default=func.now())

class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    match_score = Column(Integer)
    matched_skills = Column(ARRAY(String))
    missing_skills = Column(ARRAY(String))
    reasoning = Column(Text)
    status = Column(String, default="applied")
    applied_at = Column(DateTime, server_default=func.now())
    user_feedback = Column(String)