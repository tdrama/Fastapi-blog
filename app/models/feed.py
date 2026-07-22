from sqlalchemy import text
from app.core.database import engine

def create_feed_view():
    view_query = """
    CREATE VIEW IF NOT EXISTS feed AS
    SELECT id, 'news' AS type, title, created_at, image, slug, views FROM news
    UNION ALL
    SELECT id, 'video' AS type, title, created_at, NULL AS image, NULL AS slug, views FROM videos
    UNION ALL
    SELECT id, 'music' AS type, title, created_at, image, NULL AS slug, views FROM music;
    """
    with engine.begin() as connection:
        try:
            connection.execute(text(view_query))
            print("Database unified feed view generated successfully.")
        except Exception as e:
            print(f"Error creating database view: {e}")

if __name__ == "__main__":
    create_feed_view()
