"""Interactively create one local user without accepting passwords as arguments."""

import argparse
import getpass

from opsbridge.application.errors import DuplicateIdentityError, PasswordPolicyError
from opsbridge.domain.identity import IdentityValidationError
from opsbridge.domain.tickets import ActorRole
from opsbridge.infrastructure.auth_composition import create_auth_service
from opsbridge.infrastructure.config import get_settings
from opsbridge.infrastructure.db import Database


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a local OpsBridge user")
    parser.add_argument("--login", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--role",
        required=True,
        choices=["requester", "technician", "approver"],
    )
    args = parser.parse_args()
    password = getpass.getpass("Password (12-128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("User was not created: passwords do not match.")
        return 2
    database = Database(get_settings().database_url)
    try:
        service = create_auth_service(database, get_settings())
        user = service.create_user(
            login_id=args.login,
            display_name=args.display_name,
            role=ActorRole(args.role),
            password=password,
        )
    except (DuplicateIdentityError, PasswordPolicyError, IdentityValidationError) as exc:
        print(f"User was not created: {type(exc).__name__}.")
        return 2
    finally:
        database.dispose()
    print(f"Created local user {user.login_id} with role {user.role.value}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
