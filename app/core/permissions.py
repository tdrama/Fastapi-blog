from fastapi import (
    Request,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):

    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Login required"
        )

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:
        request.session.clear()

        raise HTTPException(
            status_code=401,
            detail="Invalid session"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account disabled"
        )

    return user


def require_login(
    current_user: User = Depends(get_current_user)
):
    return current_user


def require_admin(
    current_user: User = Depends(get_current_user)
):

    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return current_user


def require_super_admin(
    current_user: User = Depends(get_current_user)
):

    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=403,
            detail="Super Admin required"
        )

    return current_user
# =========================
# BROWSER ADMIN CHECK (NEW ADDITION)
# =========================
def browser_admin_required(request: Request, db: Session):

    user_id = request.session.get("user_id")

    if not user_id:
        return RedirectResponse("/auth/login", status_code=303)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        request.session.clear()
        return RedirectResponse("/auth/login", status_code=303)

    if not user.is_active or not user.is_admin:
        return RedirectResponse("/auth/login", status_code=303)

    return user
