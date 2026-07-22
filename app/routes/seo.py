from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.models.news import News
from app.models.video import Video
from app.models.music import Music

router = APIRouter()

DOMAIN = "https://yourdomain.com"  # Change this to your real domain

@router.get("/robots.txt")
def robots():
    content = f"""User-agent: *
Allow: /

Sitemap: {DOMAIN}/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")

@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)):
    urls = []
    
    # Static pages
    urls.append({"loc": f"{DOMAIN}/", "changefreq": "daily", "priority": "1.0"})
    urls.append({"loc": f"{DOMAIN}/news", "changefreq": "daily", "priority": "0.8"})
    urls.append({"loc": f"{DOMAIN}/videos", "changefreq": "daily", "priority": "0.8"})
    urls.append({"loc": f"{DOMAIN}/music", "changefreq": "daily", "priority": "0.8"})

    # Dynamic news
    news_items = db.query(News).order_by(News.id.desc()).limit(500).all()
    for item in news_items:
        lastmod = item.created_at.isoformat() if hasattr(item, 'created_at') and item.created_at else None
        urls.append({
            "loc": f"{DOMAIN}/news/{item.slug}",
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": "0.6"
        })

    # Dynamic videos
    videos = db.query(Video).order_by(Video.id.desc()).limit(500).all()
    for item in videos:
        lastmod = item.created_at.isoformat() if hasattr(item, 'created_at') and item.created_at else None
        urls.append({
            "loc": f"{DOMAIN}/videos/{item.id}",
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": "0.6"
        })

    # Dynamic music
    musics = db.query(Music).order_by(Music.id.desc()).limit(500).all()
    for item in musics:
        lastmod = item.created_at.isoformat() if hasattr(item, 'created_at') and item.created_at else None
        urls.append({
            "loc": f"{DOMAIN}/music/{item.id}",
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": "0.6"
        })

    # Build XML
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    
    for url in urls:
        xml_parts.append("<url>")
        xml_parts.append(f"<loc>{url['loc']}</loc>")
        if url.get("lastmod"):
            xml_parts.append(f"<lastmod>{url['lastmod']}</lastmod>")
        xml_parts.append(f"<changefreq>{url['changefreq']}</changefreq>")
        xml_parts.append(f"<priority>{url['priority']}</priority>")
        xml_parts.append("</url>")
    
    xml_parts.append("</urlset>")
    xml = "\n".join(xml_parts)

    return Response(content=xml, media_type="application/xml")
