from app.models.subscriber import Subscriber
from app.services.email_service import send_email

subscribers = db.query(Subscriber).all()

for sub in subscribers:
    send_email(
        sub.email,
        f"New Video: {video.title}",
        video.description
    )
db.add(new_video)
db.commit()
db.refresh(new_video)

subscribers = db.query(Subscriber).all()

for sub in subscribers:
    send_email(
        sub.email,
        f"New Video: {new_video.title}",
        new_video.description or ""
    )
