from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.news import News
from app.models.music import Music
from app.models.video import Video

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/search")
async def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    q = q.strip()
    
    if not q:
        return templates.TemplateResponse(
            "frontend/search.html",
            {"request": request, "q": "", "news": [], "music": [], "videos": [],"total":0}
        )

    search_term = f"%{q}%"
    limit = 20

    news = db.query(News).filter(News.title.ilike(search_term)).limit(limit).all()
    music = db.query(Music).filter(Music.title.ilike(search_term)).limit(limit).all()
    videos = db.query(Video).filter(Video.title.ilike(search_term)).limit(limit).all()
    return request.app.state.render_with_csrf(
         templates_instance=templates,
         request=request,
         template_name="frontend/search.html",
         context={
             "q": q,
             "news": news,
             "music": music,
             "videos": videos,
             "total": len(news) + len(music) + len(videos)
         }
     )
