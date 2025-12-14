# rule-manager/backend/app/database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class Ruleset(Base):
    __tablename__ = 'rulesets'

    id = Column(String, primary_key=True, default=generate_uuid)
    group_id = Column(String, nullable=False) # ID shared between versions
    version = Column(Integer, nullable=False, default=1)
    name = Column(String(255), nullable=False)
    notification_type = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default='Draft')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String(255), nullable=False)

    rules = relationship("Rule", back_populates="ruleset", cascade="all, delete-orphan")

class Rule(Base):
    __tablename__ = 'rules'

    id = Column(String, primary_key=True, default=generate_uuid)
    ruleset_id = Column(String, ForeignKey('rulesets.id'), nullable=False)
    rule_type = Column(String(50), nullable=False, default='VALIDATION') # 'VALIDATION' or 'AI_GUIDANCE'
    name = Column(String(255), nullable=False)
    description = Column(Text)
    target_field = Column(String(50), nullable=False)
    condition = Column(String(50), nullable=False)
    value = Column(Text)
    score_impact = Column(Integer, nullable=False)
    feedback_message = Column(Text, nullable=False)

    ruleset = relationship("Ruleset", back_populates="rules")

class AuditLog(Base):
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    user_id = Column(String(255), nullable=False)
    action_type = Column(String(50), nullable=False)
    entity_changed = Column(String(255))
    old_value_json = Column(JSON)
    new_value_json = Column(JSON)
    reason_for_change = Column(Text)

# Placeholder models for future implementation
class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    role_id = Column(Integer, ForeignKey('roles.id'))
    role = relationship("Role")

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)

class ElectronicSignature(Base):
    __tablename__ = 'electronic_signatures'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    entity_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

engine = None
Session = None

def init_db(db_uri):
    global engine, Session
    engine = create_engine(db_uri)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
