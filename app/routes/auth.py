from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    File,
    UploadFile,
    HTTPException
)
from typing import Optional 
from pydantic import BaseModel, EmailStr
from app.models.login_log import LoginLog
from fastapi import BackgroundTasks
from app.services.email_service import send_login_email
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from datetime import datetime
from app.core.security import hash_password, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])
templates = Jinja2Templates(directory="app/templates")

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/register")
async def register_page(request: Request):
    return request.app.state.render_with_csrf(
        templates_instance=templates, 
        request=request, 
        template_name="auth/register.html")
# ====================================================
# SECURE FORM & OPTIONAL IMAGE REGISTRATION ROUTE
# ====================================================
@router.post("/register")
async def register_user(
    request: Request,
    db: Session = Depends(get_db)
):
    # SECURITY HANDLED: Global middleware already verified the X-CSRF-Token header cleanly!

    #  Extract variables straight from parsed form data cache
    form_data = await request.form()
    username = form_data.get("username")
    email = form_data.get("email")
    password = form_data.get("password")
    profile_image = form_data.get("profile_image") # Will be an UploadFile instance or None

    # Safety Validation: Enforce presence of required inputs
    if not username or not email or not password:
        return request.app.state.render_with_csrf(
            templates, request, "auth/register.html", context={"error": "All fields are required"}
        )

    clean_username = username.strip()
    clean_email = email.strip().lower()

    if db.query(User).filter(User.email == clean_email).first():
        return request.app.state.render_with_csrf(
            templates, request, "auth/register.html", context={"error": "Email already exists"}
        )

    if db.query(User).filter(User.username == clean_username).first():
        return request.app.state.render_with_csrf(
            templates, request, "auth/register.html", context={"error": "Username already exists"}
        )

    total_users = db.query(User).count()
    is_first_user = total_users == 0

    user = User(
        username=clean_username,
        email=clean_email,
        password=hash_password(password),
        is_admin=is_first_user,
        is_super_admin=is_first_user,
        is_active=True
    )

    db.add(user)
    db.commit()

    return RedirectResponse("/auth/login", status_code=303)
class LoginPayload(BaseModel):
    email: EmailStr
    password: str
    csrf_token: str
@router.get("/login")
async def login_page(request: Request):
    #  Adding named keyword arguments ensures the token generates perfectly
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="auth/login.html"
    )
@router.post("/login")
async def login_user(
    request: Request,
    background_tasks: BackgroundTasks, # 💥 FIXED: Corrected spelling typo by removing the 'j'
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    
    # ✅ FIXED JINJA2 KEYWORDS: Explicit parameter names prevent parameter mixing and 403 loops
    if not user or not verify_password(password, user.password):
        return request.app.state.render_with_csrf(
            templates_instance=templates,
            request=request,
            template_name="auth/login.html",
            context={"error": "Invalid email or password"}
        )

    if not user.is_active:
        return request.app.state.render_with_csrf(
            templates_instance=templates,
            request=request,
            template_name="auth/login.html",
            context={"error": "Account is disabled"}
        )

    # Establish secure session data trackers
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    request.session["is_super_admin"] = user.is_super_admin
    request.session["login_time"] = datetime.utcnow().isoformat()

    db.add(LoginLog(user_id=user.id, email=user.email, ip_address=request.client.host))
    db.commit()

    # 💥 FIXED NAME LOOKUP: Matches the parameter identifier exactly
    background_tasks.add_task(send_login_email, user.email, request.client.host)
    
    return RedirectResponse("/dashboard", status_code=303)

@router.post("/logout")
async def logout(
    request: Request,
):
    request.session.clear()
    response = RedirectResponse("/auth/login", status_code=303)
#    response.delete_cookie("access_token")
    response.delete_cookie(
        key="access_token",
        path="/",                          # Matches the path where cookie is valid
        domain=None,                       # Match your domain config if applicable
        httponly=True,                     # Match your original security flag
        secure=True,                       # Match your production HTTPS flag
        samesite="lax"                     # Match your CSRF protection flag
    )
    return response
@router.get("/user")
async def users_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    page = int(request.query_params.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page

    users = db.query(User).order_by(User.id.desc()).offset(offset).limit(per_page).all()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    disabled_users = db.query(User).filter(User.is_active == False).count()
    admins = db.query(User).filter(User.is_admin == True).count()

    # ✅ FIXED JINJA2 KEYWORDS & COMPLETE BLOCK: Explicit parameters bypass Starlette syntax crashes completely
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/users/index.html",
        context={
            "users": users,
            "total_users": total_users,
            "active_users": active_users,
            "disabled_users": disabled_users,
            "admins": admins,
            "current_user": current_user
        }
    )
@router.get("/edit/{user_id}")
async def edit_user_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # ✅ FIXED JINJA2 KEYWORDS: Explicitly named parameters prevent Starlette parameter mixing errors
    return request.app.state.render_with_csrf(
        templates_instance=templates,
        request=request,
        template_name="dashboard/users/edit.html",
        context={"user": user, "current_user": current_user}
    )
@router.post("/update/{user_id}")
async def update_user(
    user_id: int,
    request: Request,                  # Keep arguments without defaults ordered first
    db: Session = Depends(get_db),     # Moved default dependencies safely to the end
    current_user: User = Depends(require_admin)
):
    # SECURITY HANDLED: Global middleware already verified the X-CSRF-Token header cleanly!

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 💥 CRITICAL LIFE-CYCLE FIX: Extract data fields from the parsed form state data cache
    form_data = await request.form()	
    username = form_data.get("username")
    email = form_data.get("email")
    
    # Safely evaluate checkboxes / booleans from HTML form data strings
    is_admin = form_data.get("is_admin") == "true" or form_data.get("is_admin") == "on"
    is_super_admin = form_data.get("is_super_admin") == "true" or form_data.get("is_super_admin") == "on"
#    is_active = form_data.get("is_active") == "true" or form_data.get("is_active") == "on"
    if "is_active" in form_data:
        is_active = form_data.get("is_active") in ["true", "on"]
    else:
        is_active = user.is_active  # Keep its current database value if the field wasn't sent
    if not username or not email:
        raise HTTPException(status_code=400, detail="Username and Email are required fields")

    if user.id == current_user.id and not is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    user.username = username.strip()
    user.email = email.strip().lower()
    user.is_admin = is_admin
    user.is_super_admin = is_super_admin
    user.is_active = is_active

    db.commit()
    return RedirectResponse("/auth/user", status_code=303)


@router.post("/delete/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    # SECURITY HANDLED: Global middleware intercepts and verifies header X-CSRF-Token securely!

    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return RedirectResponse("/auth/user", status_code=303)

@router.post("/toggle-status/{user_id}")
async def toggle_user_status(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):

    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="You cannot alter your own active status here")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    db.commit()
    return RedirectResponse("/auth/user", status_code=303)
