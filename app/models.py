import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class InteractionType(str, enum.Enum):
    MEETING = "Meeting"
    CALL = "Call"
    EMAIL = "Email"
    CONFERENCE = "Conference"
    VIRTUAL = "Virtual"


class Sentiment(str, enum.Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"


class Source(str, enum.Enum):
    FORM = "form"
    CHAT = "chat"


class FollowUpStatus(str, enum.Enum):
    PENDING = "pending"
    DONE = "done"


class HCP(Base):
    __tablename__ = "hcps"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False, index=True)
    specialty = Column(String(255), nullable=True)
    institution = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    interactions = relationship("Interaction", back_populates="hcp", cascade="all, delete-orphan")


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    hcp_id = Column(String(36), ForeignKey("hcps.id"), nullable=False)

    interaction_type = Column(Enum(InteractionType), default=InteractionType.MEETING)
    date = Column(String(20), nullable=True)
    time = Column(String(10), nullable=True)
    attendees = Column(JSON, default=list)
    topics_discussed = Column(Text, nullable=True)
    materials_shared = Column(JSON, default=list)
    samples_distributed = Column(JSON, default=list)
    sentiment = Column(Enum(Sentiment), default=Sentiment.NEUTRAL)
    outcomes = Column(Text, nullable=True)
    follow_up_actions = Column(Text, nullable=True)

    ai_summary = Column(Text, nullable=True)
    raw_input = Column(Text, nullable=True)
    source = Column(Enum(Source), default=Source.FORM)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    hcp = relationship("HCP", back_populates="interactions")
    follow_ups = relationship("FollowUp", back_populates="interaction", cascade="all, delete-orphan")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    interaction_id = Column(String(36), ForeignKey("interactions.id"), nullable=False)
    description = Column(Text, nullable=False)
    due_date = Column(String(20), nullable=True)
    status = Column(Enum(FollowUpStatus), default=FollowUpStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    interaction = relationship("Interaction", back_populates="follow_ups")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
