from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    HTTPException
)

from fastapi.templating import Jinja2Templates
from fastapi.responses import (
    RedirectResponse,
    JSONResponse
)
import re

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.subscriber import Subscriber

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

# =========================================
# ADMIN SUBSCRIBERS PAGE
# =========================================

@router.get("/dashboard/subscribers")
def subscribers_page(
    request: Request,
    db: Session = Depends(get_db)
):

    subscribers = db.query(Subscriber)\
        .order_by(Subscriber.id.desc())\
        .all()

    return templates.TemplateResponse(
        "dashboard/subscribers/index.html",
        {
            "request": request,
            "subscribers": subscribers
        }
    )

# =========================================
# FRONTEND SUBSCRIBE API
# =========================================

@router.post("/subscribe")
def subscribe(
    email: str = Form(...),
    db: Session = Depends(get_db)
):

    # REMOVE SPACES
    email = email.strip().lower()

    # LENGTH CHECK
    if len(email) > 255:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Invalid email"
            }
        )

    # EMAIL VALIDATION
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if not re.match(pattern, email):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Invalid email address"
            }
        )

    # CHECK EXISTING
    existing = db.query(Subscriber)\
        .filter(Subscriber.email == email)\
        .first()

    if existing:
        return RedirectResponse(
            url="/?message=already_subscribed",
            status_code=303

        )

    # CREATE SUBSCRIBER
    subscriber = Subscriber(
        email=email
    )

    db.add(subscriber)
    db.commit()

    return RedirectResponse(
        url="/?subscribed=1",
            status_code=303

    )

# =========================================
# DELETE SUBSCRIBER
# =========================================

@router.get("/dashboard/subscribers/delete/{subscriber_id}")
def delete_subscriber(
    subscriber_id: int,
    db: Session = Depends(get_db)
):

    subscriber = db.query(Subscriber)\
        .filter(Subscriber.id == subscriber_id)\
        .first()

    if not subscriber:

        raise HTTPException(
            status_code=404,
            detail="Subscriber not found"
        )

    db.delete(subscriber)

    db.commit()

    return RedirectResponse(
        "/dashboard/subscribers",
        status_code=302
    )
