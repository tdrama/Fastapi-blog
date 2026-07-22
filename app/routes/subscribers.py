import re
from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    Query,
    HTTPException,
    status
)
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

# Ensure correct base database engine and model tracking imports are assigned
from app.core.database import get_db
from app.models.subscriber import Subscriber
from app.models.user import User
from app.core.permissions import browser_admin_required

# ✅ PREFIX SYSTEM SYNCHRONIZATION: Kept empty to cleanly handle multiple distinct route branches
router = APIRouter(tags=["Subscribers Management"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard/subscribers")
async def subscribers_page(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required) # Keep your permission check if present
):
    # 1. Safely extract current page parameter out of browser URL query state
    try:
        page = int(request.query_params.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    per_page = 20  # Display 20 subscribers per layout page view
    offset = (page - 1) * per_page

    # 2. Query matching slice maps 
    subscribers = db.query(Subscriber).order_by(Subscriber.id.desc()).offset(offset).limit(per_page).all()
    
    # 3. Calculate pagination boundaries and total entries
    total = db.query(Subscriber).count()

    total_pages = (total + per_page - 1) // per_page
    if total_pages < 1:
        total_pages = 1

    has_prev = page > 1
    has_next = page < total_pages

    # ✅ SAFELY RENDER WITH EXPLICIT PARAMETER NAMES
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/subscribers/index.html",
        context={
            "subscribers": subscribers,
            "page": page,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": page - 1,
            "next_page": page + 1
        }
    )

@router.post("/subscribe")
async def subscribe(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    email = email.strip().lower()
    email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    # Strict string parsing input validation boundaries
    if len(email) > 255 or not re.match(email_regex, email):
        if "application/json" in request.headers.get("accept", "").lower():
            return JSONResponse(status_code=400, content={"success": False, "detail": "Invalid email address style configuration."})
        return RedirectResponse(url="/?message=invalid_email", status_code=303)

    existing = db.query(Subscriber).filter(Subscriber.email == email).first()
    if existing:
        if "application/json" in request.headers.get("accept", "").lower():
            return JSONResponse(status_code=400, content={"success": False, "detail": "This email profile is already registered."})
        return RedirectResponse(url="/?message=already_subscribed", status_code=303)

    try:
        subscriber = Subscriber(email=email)
        db.add(subscriber)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database write operation failure during subscriber creation.")

    if "application/json" in request.headers.get("accept", "").lower():
        return JSONResponse(status_code=201, content={"success": True, "detail": "Subscribed successfully."})
        
    return RedirectResponse(url="/?subscribed=1", status_code=303)


# ✅ FIXED PATHWAY: Aligned from /dashboard/subscribers/delete to match your HTML form action attribute perfectly
@router.post("/subscribers/delete/{subscriber_id}")
async def delete_subscriber(
    subscriber_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
):
    subscriber = db.query(Subscriber).filter(Subscriber.id == subscriber_id).first()
    if not subscriber:
        raise HTTPException(status_code=404, detail="Target subscriber tracking row not found.")

    try:
        db.delete(subscriber)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database dropping transaction failure encountered.")

    # ✅ HYBRID RESPONSE SYSTEM: If the request is a native form submission, redirect them safely
    if "application/x-www-form-urlencoded" in request.headers.get("content-type", "").lower():
        return RedirectResponse("/dashboard/subscribers", status_code=303)

    # For your optimized JavaScript fetch implementation, return a 200 OK block to drop the table row instantly
    return JSONResponse(
        status_code=200, 
        content={"success": True, "detail": "Subscriber profile dropped successfully."}
    )
@router.post("/api/v1/subscribe-ajax")
async def subscribe_ajax(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    # 1. Standard Input Form Cleaning & Sanitization
    email = email.strip().lower()
    email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    if len(email) > 255 or not re.match(email_regex, email):
        return JSONResponse(
            status_code=400, 
            content={"success": False, "detail": "Invalid email formatting style configuration."}
        )

    # 2. Duplicate Validation Checking Loop
    existing = db.query(Subscriber).filter(Subscriber.email == email).first()
    if existing:
        return JSONResponse(
            status_code=400, 
            content={"success": False, "detail": "This email profile is already registered."}
        )

    # 3. Database Write Transaction execution
    try:
        subscriber = Subscriber(email=email)
        db.add(subscriber)
        db.commit()
    except Exception:
        db.rollback()
        return JSONResponse(
            status_code=500, 
            content={"success": False, "detail": "Database error during subscription."}
        )

    return JSONResponse(
        status_code=201, 
        content={"success": True, "detail": "Subscribed successfully!"}
    )
