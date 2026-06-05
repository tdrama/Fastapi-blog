from sqlalchemy.orm import Session

from app.models.models import (
    User,
    Post,
    News,
    Comment,
    Video,
    Music
)


# =========================
# USER CRUD
# =========================

def create_user(db: Session, user_data):

    user = User(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_users(db: Session):
    return db.query(User).all()


# =========================
# POST CRUD
# =========================

def create_post(db: Session, post_data, author_id):

    post = Post(
        title=post_data.title,
        content=post_data.content,
        category=post_data.category,
        tags=post_data.tags,
        author_id=author_id
    )

    db.add(post)
    db.commit()
    db.refresh(post)

    return post


def get_posts(db: Session):
    return db.query(Post).all()


def get_post(db: Session, post_id: int):
    return db.query(Post).filter(Post.id == post_id).first()


def update_post(db: Session, post_id: int, data):

    post = db.query(Post).filter(Post.id == post_id).first()

    post.title = data.title
    post.content = data.content

    db.commit()

    return post


def delete_post(db: Session, post_id: int):

    post = db.query(Post).filter(Post.id == post_id).first()

    db.delete(post)

    db.commit()


# =========================
# NEWS CRUD
# =========================

def create_news(db: Session, news_data, author_id):

    news = News(
        title=news_data.title,
        content=news_data.content,
        category=news_data.category,
        author_id=author_id
    )

    db.add(news)
    db.commit()
    db.refresh(news)

    return news


def get_news(db: Session):
    return db.query(News).all()


# =========================
# COMMENT CRUD
# =========================

def create_comment(db: Session, comment_data, user_id):

    comment = Comment(
        content=comment_data.content,
        post_id=comment_data.post_id,
        user_id=user_id
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment


# =========================
# VIDEO CRUD
# =========================

def create_video(db: Session, data, user_id):

    video = Video(
        title=data.title,
        description=data.description,
        video_file="static/uploads/default.mp4",
        user_id=user_id
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return video


# =========================
# MUSIC CRUD
# =========================

def create_music(db: Session, data, user_id):

    music = Music(
        title=data.title,
        artist=data.artist,
        music_file="static/uploads/default.mp3",
        user_id=user_id
    )

    db.add(music)
    db.commit()
    db.refresh(music)

    return music
