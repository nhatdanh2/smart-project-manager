"""Users router: minimal endpoints needed by the frontend (search)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserOut
from app.services.auth_service import get_current_user


router = APIRouter(prefix=f"{settings.API_PREFIX}/users", tags=["users"])


@router.get("/search", response_model=List[UserOut])
def search_users(
    q: Optional[str] = None,
    limit: int = 20,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[UserOut]:
    """Search users by name or email.  Used by the project invite flow."""
    query = db.query(User)
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                User.name.ilike(like),
                User.email.ilike(like),
            )
        )
    rows = query.order_by(User.name.asc()).limit(max(1, min(limit, 50))).all()
    return [UserOut.model_validate(u) for u in rows]
