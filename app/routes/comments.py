import bleach

from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.comment import Comment

router = APIRouter()


# =========================
# MUSIC COMMENT
# =========================
@router.post("/music/{music_id}/comment")
def music_comment(
    music_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

    name = bleach.clean(name.strip(), tags=[], strip=True)
    content = bleach.clean(content.strip(), tags=[], strip=True)

    if not name or not content:
        raise HTTPException(400, "Name and comment are required")

    if len(name) > 100:
        raise HTTPException(400, "Name too long")

    if len(content) > 1000:
        raise HTTPException(400, "Comment too long")

    comment = Comment(
        name=name,
        content=content,
        music_id=music_id
    )

    db.add(comment)
    db.commit()

    return RedirectResponse(f"/music/{music_id}", status_code=303)


# =========================
# VIDEO COMMENT
# =========================
@router.post("/video/{video_id}/comment")
def video_comment(
    video_id: int,
    name: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):

    name = bleach.clean(name.strip(), tags=[], strip=True)
    content = bleach.clean(content.strip(), tags=[], strip=True)

    if not name or not content:
        raise HTTPException(400, "Name and comment are required")

    if len(name) > 100:
        raise HTTPException(400, "Name too long")

    if len(content) > 1000:
        raise HTTPException(400, "Comment too long")

    comment = Comment(
        name=name,
        content=content,
        video_id=video_id
    )

    db.add(comment)
    db.commit()

    return RedirectResponse(f"/videos/{video_id}", status_code=303)


# =========================
# NEWS COMMENT
# =========================
#@router.post("/news/{news_id}/comment")
#def news_comment(
 #   news_id: int,
  #  name: str = Form(...),
   # content: str = Form(...),
    #db: Session = Depends(get_db)
#):
#
 #   name = bleach.clean(name.strip(), tags=[], strip=True)
  #  content = bleach.clean(content.strip(), tags=[], strip=True)
#
 #   if not name or not content:
  #      raise HTTPException(400, "Name and comment are required")
#
 #   if len(name) > 100:
  #      raise HTTPException(400, "Name too long")
#
 #   if len(content) > 1000:
  #      raise HTTPException(400, "Comment too long")
#
 #   comment = Comment(
  #      name=name,
   #     content=content,
    #    news_id=news_id
   # )

    #db.add(comment)
    #db.commit()
#
 #   return RedirectResponse(f"/news/{news_id}", status_code=303)
