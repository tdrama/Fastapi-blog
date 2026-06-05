from fastapi import (
    APIRouter,
    Request,
    Depends,
    Form,
    HTTPException
)
from app.models.login_log import LoginLog
from fastapi import BackgroundTasks
from app.services.email_service import send_login_email
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from app.core.database import get_db
from datetime import datetime
from app.core.security import (
    hash_password,
    verify_password
)

from app.models.user import User

# =========================================
# ROUTER
# =========================================

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

templates = Jinja2Templates(
    directory="app/templates"
)

# =========================================
# REGISTER PAGE
# =========================================

@router.get("/register")
async def register_page(request: Request):

    return templates.TemplateResponse(
        "auth/register.html",
        {
            "request": request
        }
    )

# =========================================
# REGISTER USER
# =========================================

#@router.post("/register")
#async def register_user(
 #   request: Request,
  #  username: str = Form(...),
   # email: str = Form(...),
   # password: str = Form(...),
    #db: Session = Depends(get_db)
#):
#
 #   existing_user = db.query(User)\
  #      .filter(User.email == email)\
   #     .first()
#
 #   if existing_user:
#
 #       return templates.TemplateResponse(
  #          "auth/register.html",
   #         {
    #            "request": request,
     #           "error": "Email already exists"
      #      }
       # )
#
 #   existing_username = db.query(User)\
  #      .filter(User.username == username)\
   #     .first()
#
 #   if existing_username:
#
 #       return templates.TemplateResponse(
  #          "auth/register.html",
   #         {
    #            "request": request,
     #           "error": "Username already exists"
      #      }
       # )
#
 #   user = User(
  #      username=username,
   #     email=email,
    #    password=hash_password(password)
   # )
#
 #   db.add(user)
  #  db.commit()
#
 #   return RedirectResponse(
  #      "/auth/login",
   #     status_code=303
   # )
# =========================================
# REGISTER USER
# =========================================

@router.post("/register")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    # CHECK EMAIL
    existing_user = db.query(User)\
        .filter(User.email == email)\
        .first()

    if existing_user:

        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": "Email already exists"
            }
        )

    # CHECK USERNAME
    existing_username = db.query(User)\
        .filter(User.username == username)\
        .first()

    if existing_username:

        return templates.TemplateResponse(
            "auth/register.html",
            {
                "request": request,
                "error": "Username already exists"
            }
        )

    # COUNT USERS
    total_users = db.query(User).count()

    # FIRST USER = SUPER ADMIN
    if total_users == 0:

        user = User(
            username=username,
            email=email,
            password=hash_password(password),
            is_admin=True,
            is_super_admin=True,
            is_active=True
        )

    else:

        user = User(
            username=username,
            email=email,
            password=hash_password(password),
            is_admin=False,
            is_super_admin=False,
            is_active=True
        )

    db.add(user)
    db.commit()

    return RedirectResponse(
        "/auth/login",
        status_code=303
    )
# =========================================
# LOGIN PAGE
# =========================================

@router.get("/login")
async def login_page(request: Request):

    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request
        }
    )

# =========================================
# LOGIN USER
# =========================================

# =========================================
# LOGIN USER
# =========================================
@router.post("/login")
async def login_user(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):

    # 🔍 FIND USER
    user = db.query(User).filter(User.email == email).first()

    # ❌ INVALID EMAIL
    if not user:
        return RedirectResponse("/auth/login", status_code=303)

    # ❌ INVALID PASSWORD
    if not verify_password(password, user.password):
        return RedirectResponse("/auth/login", status_code=303)

    # =========================================
    # ✅ SESSION LOGIN (IMPORTANT FIX)
    # =========================================
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["is_admin"] = user.is_admin
    request.session["is_super_admin"] = user.is_super_admin
    request.session["login_time"] = datetime.utcnow().isoformat()

    # =========================================
    # LOG LOGIN ACTIVITY
    # =========================================
    log = LoginLog(
        user_id=user.id,
        email=user.email,
        ip_address=request.client.host
    )

    db.add(log)
    db.commit()

    # =========================================
    # EMAIL NOTIFICATION (BACKGROUND)
    # =========================================
    background_tasks.add_task(
        send_login_email,
        user.email,
        request.client.host
    )

    # =========================================
    # REDIRECT DASHBOARD
    # =========================================
    return RedirectResponse(
        "/dashboard",
        status_code=303
    )
# =========================================
# LOGOUT
# =========================================

@router.get("/logout")
async def logout(request: Request):

    request.session.clear()

    return RedirectResponse(
        "/auth/login",
        status_code=303
    )

# =========================================
# USERS PAGE
# =========================================

@router.get("/user")
async def users_page(
    request: Request,
    db: Session = Depends(get_db)
):

    users = db.query(User)\
        .order_by(User.id.desc())\
        .all()

    total_users = db.query(User).count()

    active_users = db.query(User)\
        .filter(User.is_active == True)\
        .count()

    disabled_users = db.query(User)\
        .filter(User.is_active == False)\
        .count()

    admins = db.query(User)\
        .filter(User.is_admin == True)\
        .count()

    return templates.TemplateResponse(
        "dashboard/users/index.html",
        {
            "request": request,
            "users": users,
            "total_users": total_users,
            "active_users": active_users,
            "disabled_users": disabled_users,
            "admins": admins
        }
    )

# =========================================
# EDIT USER PAGE
# =========================================

@router.get("/edit/{user_id}")
async def edit_user_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return templates.TemplateResponse(
        "dashboard/users/edit.html",
        {
            "request": request,
            "user": user
        }
    )

# =========================================
# UPDATE USER
# =========================================

@router.post("/update/{user_id}")
async def update_user(
    user_id: int,
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    is_admin: bool = Form(False),
    is_super_admin: bool = Form(False),
    is_active: bool = Form(False),
    db: Session = Depends(get_db)
):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.username = username
    user.email = email
    user.is_admin = is_admin
    user.is_super_admin = is_super_admin
    user.is_active = is_active

    db.commit()

    return RedirectResponse(
        "/auth/user",
        status_code=303
    )

# =========================================
# DELETE USER
# =========================================

@router.get("/delete/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):

    current_user_id = request.session.get("user_id")

    if current_user_id == user_id:

        raise HTTPException(
            status_code=400,
            detail="You cannot delete yourself"
        )

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    db.delete(user)
    db.commit()

    return RedirectResponse(
        "/auth/user",
        status_code=303
    )

# =========================================
# TOGGLE STATUS
# =========================================

@router.get("/toggle-status/{user_id}")
async def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.is_active = not user.is_active

    db.commit()

    return RedirectResponse(
        "/auth/user",
        status_code=303
    )

# =========================================
# TOGGLE ADMIN
# =========================================

@router.get("/toggle-admin/{user_id}")
async def toggle_admin(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.is_admin = not user.is_admin

    db.commit()

    return RedirectResponse(
        "/auth/user",
        status_code=303
    )
