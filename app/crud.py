from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models


def get_or_create_hcp(db: Session, name: str) -> models.HCP:
    hcp = db.query(models.HCP).filter(models.HCP.name.ilike(name.strip())).first()
    if hcp:
        return hcp
    hcp = models.HCP(name=name.strip())
    db.add(hcp)
    db.commit()
    db.refresh(hcp)
    return hcp


def search_hcps(db: Session, query: str, limit: int = 10) -> List[models.HCP]:
    q = db.query(models.HCP)
    if query:
        like = f"%{query}%"
        q = q.filter(
            or_(
                models.HCP.name.ilike(like),
                models.HCP.specialty.ilike(like),
                models.HCP.institution.ilike(like),
            )
        )
    return q.order_by(models.HCP.name).limit(limit).all()


def create_interaction(db: Session, data: dict, source: str = "form") -> models.Interaction:
    hcp = get_or_create_hcp(db, data["hcp_name"])
    interaction = models.Interaction(
        hcp_id=hcp.id,
        interaction_type=data.get("interaction_type", "Meeting"),
        date=data.get("date"),
        time=data.get("time"),
        attendees=data.get("attendees") or [],
        topics_discussed=data.get("topics_discussed"),
        materials_shared=data.get("materials_shared") or [],
        samples_distributed=data.get("samples_distributed") or [],
        sentiment=data.get("sentiment", "Neutral"),
        outcomes=data.get("outcomes"),
        follow_up_actions=data.get("follow_up_actions"),
        ai_summary=data.get("ai_summary"),
        raw_input=data.get("raw_input"),
        source=source,
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def update_interaction(db: Session, interaction_id: str, updates: dict) -> Optional[models.Interaction]:
    interaction = db.query(models.Interaction).filter(models.Interaction.id == interaction_id).first()
    if not interaction:
        return None
    for key, value in updates.items():
        if value is not None and hasattr(interaction, key):
            setattr(interaction, key, value)
    db.commit()
    db.refresh(interaction)
    return interaction


def get_interaction(db: Session, interaction_id: str) -> Optional[models.Interaction]:
    return db.query(models.Interaction).filter(models.Interaction.id == interaction_id).first()


def list_interactions(db: Session, hcp_name: Optional[str] = None, limit: int = 20) -> List[models.Interaction]:
    q = db.query(models.Interaction).join(models.HCP)
    if hcp_name:
        q = q.filter(models.HCP.name.ilike(f"%{hcp_name}%"))
    return q.order_by(models.Interaction.created_at.desc()).limit(limit).all()


def create_follow_up(db: Session, interaction_id: str, description: str, due_date: Optional[str]) -> models.FollowUp:
    follow_up = models.FollowUp(interaction_id=interaction_id, description=description, due_date=due_date)
    db.add(follow_up)
    db.commit()
    db.refresh(follow_up)
    return follow_up


def interaction_to_dict(interaction: models.Interaction) -> dict:
    return {
        "id": interaction.id,
        "hcp_id": interaction.hcp_id,
        "hcp_name": interaction.hcp.name if interaction.hcp else None,
        "interaction_type": interaction.interaction_type.value if hasattr(interaction.interaction_type, "value") else interaction.interaction_type,
        "date": interaction.date,
        "time": interaction.time,
        "attendees": interaction.attendees or [],
        "topics_discussed": interaction.topics_discussed,
        "materials_shared": interaction.materials_shared or [],
        "samples_distributed": interaction.samples_distributed or [],
        "sentiment": interaction.sentiment.value if hasattr(interaction.sentiment, "value") else interaction.sentiment,
        "outcomes": interaction.outcomes,
        "follow_up_actions": interaction.follow_up_actions,
        "ai_summary": interaction.ai_summary,
        "source": interaction.source.value if hasattr(interaction.source, "value") else interaction.source,
        "created_at": interaction.created_at,
        "updated_at": interaction.updated_at,
    }


def save_chat_message(db: Session, session_id: str, role: str, content: str) -> models.ChatMessage:
    msg = models.ChatMessage(session_id=session_id, role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
