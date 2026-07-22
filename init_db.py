from sqlalchemy import text
from app.core.database import engine

def create_feed_view():
    drop_query = "DROP VIEW IF EXISTS feed;"
    
    # ✅ CONFIGURATION: Explicitly maps to SINGULAR database table structures
    view_query = """
    CREATE VIEW feed AS
    SELECT 
        id, 
        title, 
        slug, 
        content, 
        image AS media, 
        views, 
        created_at, 
        'news' AS type, 
        NULL AS video_file, 
        NULL AS music_file 
    FROM news
    
    UNION ALL
    
    SELECT 
        id, 
        title, 
        NULL AS slug, 
        description AS content, 
        NULL AS media, 
        views, 
        created_at, 
        'video' AS type, 
        video_file, 
        NULL AS music_file 
    FROM video
    
    UNION ALL
    
    SELECT 
        id, 
        title, 
        NULL AS slug, 
        NULL AS content, 
        image AS media, 
        views, 
        created_at, 
        'music' AS type, 
        NULL AS video_file, 
        music_file 
    FROM music;
    """
    with engine.begin() as connection:
        try:
            connection.execute(text(drop_query))
            connection.execute(text(view_query))
            print("Database unified 10-column feed view generated successfully.")
        except Exception as e:
            print(f"Error creating database view layout: {e}")

if __name__ == "__main__":
    create_feed_view()
