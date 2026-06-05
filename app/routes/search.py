from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.news import News
from app.models.music import Music
from app.models.video import Video

router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)

@router.get("/search")
def search(
    request: Request,
    q: str = "",
    db: Session = Depends(get_db)
):
    news = db.query(News).filter(
        News.title.contains(q)
    ).all()

    music = db.query(Music).filter(
        Music.title.contains(q)
    ).all()

    videos = db.query(Video).filter(
        Video.title.contains(q)
    ).all()

    return templates.TemplateResponse(
        "frontend/search.html",
        {
            "request": request,
            "q": q,
            "news": news,
            "music": music,
            "videos": videos
        }
    )
