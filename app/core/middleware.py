from fastapi import Request
from fastapi.responses import RedirectResponse


class AuthMiddleware:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        path = request.url.path

        # =========================
        # PUBLIC ROUTES
        # =========================

        public_paths = [

            "/",

            "/auth/login",

            "/auth/register",

            "/static",

            "/news",

            "/videos",

            "/music"
        ]

        # allow public paths
        for public in public_paths:

            if path.startswith(public):

                await self.app(scope, receive, send)
                return

        # =========================
        # PROTECT DASHBOARD
        # =========================

        if path.startswith("/dashboard"):

            user_id = request.session.get("user_id")

            if not user_id:

                response = RedirectResponse(
                    "/auth/login",
                    status_code=302
                )

                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
