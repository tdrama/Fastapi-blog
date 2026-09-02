from sqlalchemy import text
from app.core.database import engine

def create_feed_view():
    with engine.begin() as connection:
        try:
            connection.execute(text("DROP TABLE IF EXISTS feed;"))

            # Create a fresh feed table
            connection.execute(text("""
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
            """))

            # Populate the feed table from all content sources
            connection.execute(text("""
                INSERT INTO feed (
                    id,
                    title,
                    slug,
                    content,
                    media,
                    views,
                    created_at,
                    type,
                    video_file,
                    music_file
                )
                SELECT
                    id,
                    title,
                    slug,
                    content,
                    image,
                    views,
                    created_at,
                    'news',
                    NULL,
                    NULL
                FROM news

                UNION ALL

                SELECT
                    id,
                    title,
                    NULL,
                    description,
                    NULL,
                    views,
                    created_at,
                    'videos',
                    video_file,
                    NULL
                FROM videos

                UNION ALL

                SELECT
                    id,
                    title,
                    NULL,
                    NULL,
                    cover_image,
                    views,
                    created_at,
                    'music',
                    NULL,
                    music_file
                FROM music;
            """))

            print("Feed table rebuilt successfully.")

        except Exception as e:
            print(f"Database build failed: {e}")


if __name__ == "__main__":
    create_feed_view()
