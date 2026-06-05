from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.category import Category

router = APIRouter()


@router.post("/dashboard/categories/create")
def create_category(
    name: str = Form(...),
    slug: str = Form(None),
    db: Session = Depends(get_db)
):
    if not slug:
        slug = name.lower().replace(" ", "-")

    exists = db.query(Category).filter(
        Category.name == name
    ).first()

    if exists:
        return RedirectResponse(
            "/dashboard/categories",
            status_code=302
        )

    category = Category(
        name=name,
        slug=slug
    )

    db.add(category)
    db.commit()
    db.refresh(category)
    return RedirectResponse(
        "/dashboard/categories",
        status_code=302
    )


@router.get("/dashboard/categories/delete/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db)
):
    category = db.query(Category).filter(
        Category.id == category_id
    ).first()

    if category:
        db.delete(category)
        db.commit()

    return RedirectResponse(
        "/dashboard/categories",
        status_code=302
    )
