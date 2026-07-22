from fastapi import APIRouter, Depends, Form, Request, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from slugify import slugify

# Ensure correct base database engine, permission filters, and model imports are referenced
from app.core.database import get_db
from app.models.category import Category
from app.models.user import User
from app.core.permissions import browser_admin_required  # Aligned to your working dashboard admin permission utility

# Keep prefix empty since explicit paths are already fully defined inside decorators
router = APIRouter(tags=["Categories Administration"])


@router.post("/dashboard/categories/create")
async def create_category(
    request: Request,
    name: str = Form(...),
    slug: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)  # ✅ FIXED: Uses dashboard session permission wrapper
):
    name_clean = name.strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="Category name is required.")

    # Auto-generate safe slug structures if left blank by an admin
    resolved_slug = slugify(slug or name_clean)

    # Prevent unique constraints collisions before database commit actions
    exists = db.query(Category).filter(
        or_(Category.name == name_clean, Category.slug == resolved_slug)
    ).first()
    
    if exists:
        raise HTTPException(status_code=400, detail="A category with this name or slug already exists.")

    try:
        category = Category(name=name_clean, slug=resolved_slug)
        db.add(category)
        db.commit()
        db.refresh(category)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database write operation failure during category initialization.")

    # ✅ FIXED REDIRECTION PATHWAY: Returns a 303 status so your frontend fetch processes the response cleanly
    if "application/x-www-form-urlencoded" in request.headers.get("content-type", "").lower():
        return RedirectResponse("/dashboard/categories", status_code=status.HTTP_303_SEE_OTHER)

    return JSONResponse(status_code=201, content={"success": True, "detail": "Category initialized seamlessly."})


@router.post("/dashboard/categories/delete/{category_id}")
async def delete_category(
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(browser_admin_required)
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Target category tracking row not found.")

    # Safeguard constraint: prevent deleting if categories contain active content
    if getattr(category, "news", None) or getattr(category, "videos", None) or getattr(category, "musics", None):
        raise HTTPException(status_code=400, detail="Cannot delete a category that still contains active content items.")

    try:
        db.delete(category)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database dropping transaction failure encountered.")

    # ✅ HYBRID RESPONSE SYSTEM: If the request is a native form submission, redirect them safely
    if "application/x-www-form-urlencoded" in request.headers.get("content-type", "").lower():
        return RedirectResponse("/dashboard/categories", status_code=status.HTTP_303_SEE_OTHER)

    # For your optimized JavaScript fetch implementation, return a 200 OK block to drop the table row instantly
    return JSONResponse(
        status_code=200, 
        content={"success": True, "detail": "Category profile dropped successfully."}
    )
