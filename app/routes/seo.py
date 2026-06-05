from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()

@router.get("/robots.txt")
def robots():

    content = """
User-agent: *
Allow: /

Sitemap: https://yourdomain.com/sitemap.xml
"""

    return Response(
        content=content,
        media_type="text/plain"
    )


@router.get("/sitemap.xml")
def sitemap():

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

<url>
<loc>https://yourdomain.com/</loc>
</url>

<url>
<loc>https://yourdomain.com/news</loc>
</url>

<url>
<loc>https://yourdomain.com/videos</loc>
</url>

<url>
<loc>https://yourdomain.com/music</loc>
</url>

</urlset>
"""

    return Response(
        content=xml,
        media_type="application/xml"
    )
