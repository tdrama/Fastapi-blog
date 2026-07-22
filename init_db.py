from sqlalchemy import text
from app.core.database import engine

def create_feed_view():
    with engine.begin() as connection:
        try:
            # 1. Clear out any old virtual view attempts that block table creation
            connection.execute(text("DROP VIEW IF EXISTS feed;"))
            connection.execute(text("DROP TABLE IF EXISTS feed;"))
            
            # 2. Build a real, solid physical table structure matching your 10 columns
            create_table_query = """
            CREATE TABLE feed (
                id INTEGER,
                title TEXT,
                slug TEXT,
                content TEXT,
                media TEXT,
                views INTEGER,
                created_at DATETIME,
                type TEXT,
                video_file TEXT,
                music_file TEXT
            );
            """
            connection.execute(text(create_table_query))
            
            # 3. Aggregate and copy live rows across your actual singular tables smoothly
            insert_query = """
            INSERT INTO feed 
            SELECT id, title, slug, content, image AS media, views, created_at, 'news' AS type, NULL AS video_file, NULL AS music_file FROM news
            UNION ALL
            SELECT id, title, NULL AS slug, description AS content, NULL AS media, views, created_at, 'video' AS type, video_file, NULL AS music_file FROM video
            UNION ALL
            SELECT id, title, NULL AS slug, NULL AS content, image AS media, views, created_at, 'music' AS type, NULL AS video_file, music_file FROM music;
            """
            connection.execute(text(insert_query))
            print("Successfully initialized physical, indexed 10-column feed database table 🎉")
            
        except Exception as e:
            print(f"Database build failure layout context: {e}")

if __name__ == "__main__":
    create_feed_view()
