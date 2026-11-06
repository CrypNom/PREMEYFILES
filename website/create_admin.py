"""
create_admin.py - Create (or reset the password of) the administrator account.

Run it from the website folder:   python create_admin.py

The password is typed in the window and is never written to any file.
Only a secure hash of it is saved in the database.
"""
import getpass
import sys

import config
import database as db


def main():
    db.init_db()
    print("=== PREMEYFILES - create administrator ===")
    print("Database:", config.DATABASE_PATH)
    username = input("Admin username: ").strip()
    if len(username) < 3:
        print("Username must be at least 3 characters.")
        return 1
    password = getpass.getpass("Admin password (min %d chars, hidden): " % config.MIN_PASSWORD_LENGTH)
    if len(password) < config.MIN_PASSWORD_LENGTH:
        print("Password must be at least %d characters." % config.MIN_PASSWORD_LENGTH)
        return 1
    if password != getpass.getpass("Repeat password: "):
        print("The passwords do not match.")
        return 1
    action = db.create_or_update_admin(username, password)
    print("Done! Admin '%s' %s." % (username, action))
    return 0


if __name__ == "__main__":
    sys.exit(main())
