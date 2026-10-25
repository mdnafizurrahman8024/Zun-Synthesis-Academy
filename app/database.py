from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import AdminUser, Certificate, ContentItem, Course, CourseProgress, Enrollment, FinancialAidRequest, PaymentHistory, StudentUser, UserProfile, VisitEvent  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name
    bool_default = "TRUE" if dialect == "postgresql" else "1"
    with engine.begin() as connection:
        if "admin_users" in tables:
            admin_columns = {column["name"] for column in inspect(connection).get_columns("admin_users")}
            if "role" not in admin_columns:
                connection.exec_driver_sql("ALTER TABLE admin_users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'admin'")
            if "is_active" not in admin_columns:
                connection.exec_driver_sql(f"ALTER TABLE admin_users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT {bool_default}")
        if "courses" in tables:
            course_columns = {column["name"] for column in inspect(connection).get_columns("courses")}
            if "regular_price_cents" not in course_columns:
                connection.exec_driver_sql("ALTER TABLE courses ADD COLUMN regular_price_cents INTEGER NOT NULL DEFAULT 0")
            if "offer_price_cents" not in course_columns:
                connection.exec_driver_sql("ALTER TABLE courses ADD COLUMN offer_price_cents INTEGER NULL")
            if "discount_badge_text" not in course_columns:
                connection.exec_driver_sql("ALTER TABLE courses ADD COLUMN discount_badge_text VARCHAR(60) NOT NULL DEFAULT ''")
            connection.exec_driver_sql("UPDATE courses SET regular_price_cents = price_cents WHERE regular_price_cents = 0 AND price_cents > 0")

    with SessionLocal() as db:
        has_super_admin = db.scalar(select(AdminUser.id).where(AdminUser.role == "super_admin").limit(1))
        if has_super_admin is None:
            first_admin = db.scalar(select(AdminUser).order_by(AdminUser.id).limit(1))
            if first_admin:
                first_admin.role = "super_admin"
                first_admin.is_active = True
                db.commit()
