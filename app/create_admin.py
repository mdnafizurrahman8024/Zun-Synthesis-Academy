from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import AdminUser
from app.services.auth import hash_password


def main() -> None:
    init_db()
    email = input("Admin email: ").strip().lower()
    password = getpass("Admin password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords did not match.")
    with SessionLocal() as db:
        if db.scalar(select(AdminUser.id).where(AdminUser.email == email)):
            raise SystemExit("An admin with that email already exists.")
        first_account = db.scalar(select(AdminUser.id).limit(1)) is None
        db.add(AdminUser(email=email, password_hash=hash_password(password), role="super_admin" if first_account else "admin"))
        db.commit()
    print("Admin account created.")


if __name__ == "__main__":
    main()
