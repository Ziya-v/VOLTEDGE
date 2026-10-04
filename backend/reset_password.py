"""Reset a VoltEdge user's password locally without displaying it."""

import os
from datetime import datetime, timezone
from getpass import getpass

from pymongo.errors import PyMongoError

from app.core.database import client, database
from app.core.security import hash_password
from app.models import UserDocument


def main():
    if database is None:
        print("MongoDB is not configured. Check backend/.env.")
        return

    employee_id = input("Employee ID to reset (for example ADM0001): ").strip().upper()
    if not employee_id:
        print("Employee ID is required.")
        return

    user = database["users"].find_one({"employee_id": employee_id})
    is_initial_admin = employee_id == os.getenv("INITIAL_ADMIN_ID", "ADM0001").strip().upper()
    if user is None and not is_initial_admin:
        print("That account was not found.")
        return

    role = user["role"] if user else "admin"
    minimum_length = 12 if role == "admin" else 8
    new_password = getpass(f"New password ({minimum_length}+ characters; input hidden): ")
    confirmation = getpass("Re-enter new password: ")
    if len(new_password) < minimum_length:
        print(f"Password must be at least {minimum_length} characters.")
        return
    if new_password != confirmation:
        print("The passwords did not match. Nothing was changed.")
        return

    try:
        users = database["users"]
        users.create_index("employee_id", unique=True)
        now = datetime.now(timezone.utc)
        if user:
            users.update_one(
                {"employee_id": employee_id},
                {"$set": {"password_hash": hash_password(new_password), "updated_at": now}},
            )
        else:
            name = os.getenv("INITIAL_ADMIN_NAME", "VoltEdge Admin").strip() or "VoltEdge Admin"
            admin = UserDocument(
                employee_id=employee_id,
                name=name,
                role="admin",
                password_hash=hash_password(new_password),
                created_at=now,
            )
            users.insert_one(admin.dict())
        print(f"Password reset complete for {employee_id}. Sign in with the new password.")
    except PyMongoError:
        print("Could not update the password in MongoDB. Check the Atlas connection.")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
