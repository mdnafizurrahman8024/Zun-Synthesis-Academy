from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings:
    app_name = "Zun Synthesis Academy"
    templates_dir = PROJECT_ROOT / "app" / "templates"
    static_dir = PROJECT_ROOT / "app" / "static"
    media_dir = Path(os.getenv("MEDIA_UPLOAD_DIR", str(static_dir / "uploads"))).resolve()
    allowed_hosts = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "*").split(",") if host.strip()] or ["*"]
    force_https = os.getenv("FORCE_HTTPS", "false").lower() in {"1", "true", "yes"}
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{(PROJECT_ROOT / 'academy.db').as_posix()}")
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_algorithm = "HS256"
    jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))


settings = Settings()
