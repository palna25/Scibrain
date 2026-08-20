from getpass import getpass

from app.database.postgres import SessionLocal
from app.models.user import User
from app.core.security import hash_password


def create_admin():
    db = SessionLocal()

    try:
        existing_admin = (
            db.query(User)
            .filter(User.role == "admin")
            .first()
        )

        if existing_admin:
            print(
                f"Admin already exists: {existing_admin.email}"
            )
            return

        full_name = input("Admin full name: ").strip()
        email = input("Admin email: ").strip().lower()
        password = getpass("Admin password: ")

        existing_user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing_user:
            print(
                "A user with this email already exists."
            )
            return

        admin = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            is_active=True
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("\nAdmin account created successfully.")
        print(f"Email: {admin.email}")
        print(f"Role: {admin.role}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()