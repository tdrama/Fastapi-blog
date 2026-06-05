from fastapi import Request, HTTPException
from datetime import datetime, timedelta


def check_session_timeout(request: Request):
    user_id = request.session.get("user_id")
    login_time = request.session.get("login_time")

    if not user_id:
        return None

    if not login_time:
        request.session.clear()
        return None

    login_time = datetime.fromisoformat(login_time)

    if datetime.utcnow() - login_time > timedelta(hours=3):
        request.session.clear()
        return None

    return user_id
