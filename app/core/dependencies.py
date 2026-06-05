from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User


# =========================
# GET CURRENT USER
# =========================
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")

    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


# =========================
# LOGIN REQUIRED
# =========================
def login_required(
    request: Request,
    db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user:
        raise NotAuthenticated()

    return user

# =========================
# ADMIN REQUIRED
# =========================
def admin_required(
    request: Request,
    db: Session = Depends(get_db)
):
    user = login_required(request, db)

    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")

    return user


# =========================
# SUPER ADMIN REQUIRED
# =========================
def super_admin_required(
    request: Request,
    db: Session = Depends(get_db)
):
    user = login_required(request, db)

    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin only")

    return user
