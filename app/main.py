from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.routes.api import router as api_router
from app.routes.admin import router as admin_page_router
from app.routes.admin_users import router as admin_users_router
from app.routes.courses import router as courses_router
from app.routes.pages import router as pages_router
from app.routes.students import router as students_router
from app.routes.media import router as media_router
from app.routes.student_dashboard import public_router as certificate_public_router
from app.routes.student_dashboard import router as student_dashboard_router
from app.services.default_content import seed_default_content
from app.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("Set JWT_SECRET to a random value of at least 32 characters before starting the server.")
    init_db()
    from app.database import SessionLocal

    with SessionLocal() as db:
        seed_default_content(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
if settings.allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
if settings.force_https:
    app.add_middleware(HTTPSRedirectMiddleware)
app.include_router(pages_router)
app.include_router(admin_page_router)
app.include_router(api_router)
app.include_router(admin_users_router)
app.include_router(media_router)
app.include_router(courses_router)
app.include_router(students_router)
app.include_router(student_dashboard_router)
app.include_router(certificate_public_router)

# Keep these mounts last so they do not intercept application routes. The image
# files are served from the same root-relative names used in index.html.
settings.media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.media_dir), name="uploads")
app.mount("/", StaticFiles(directory=settings.static_dir), name="site-static")
