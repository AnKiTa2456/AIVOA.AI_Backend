from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class HCPBase(BaseModel):
    name: str
    specialty: Optional[str] = None
    institution: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class HCPCreate(HCPBase):
    pass


class HCPOut(HCPBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class InteractionBase(BaseModel):
    hcp_name: str
    interaction_type: str = "Meeting"
    date: Optional[str] = None
    time: Optional[str] = None
    attendees: List[str] = []
    topics_discussed: Optional[str] = None
    materials_shared: List[str] = []
    samples_distributed: List[str] = []
    sentiment: str = "Neutral"
    outcomes: Optional[str] = None
    follow_up_actions: Optional[str] = None


class InteractionCreate(InteractionBase):
    pass


class InteractionUpdate(BaseModel):
    interaction_type: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    attendees: Optional[List[str]] = None
    topics_discussed: Optional[str] = None
    materials_shared: Optional[List[str]] = None
    samples_distributed: Optional[List[str]] = None
    sentiment: Optional[str] = None
    outcomes: Optional[str] = None
    follow_up_actions: Optional[str] = None


class InteractionOut(BaseModel):
    id: str
    hcp_id: str
    hcp_name: Optional[str] = None
    interaction_type: str
    date: Optional[str]
    time: Optional[str]
    attendees: List[str]
    topics_discussed: Optional[str]
    materials_shared: List[str]
    samples_distributed: List[str]
    sentiment: str
    outcomes: Optional[str]
    follow_up_actions: Optional[str]
    ai_summary: Optional[str]
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FollowUpOut(BaseModel):
    id: str
    interaction_id: str
    description: str
    due_date: Optional[str]
    status: str

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_calls: List[str] = []
    interaction: Optional[InteractionOut] = None
