#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select

from camp_match.config.settings import get_settings
from camp_match.modules.identity.adapters.persistence.models import AccountModel
from camp_match.modules.security.adapters.persistence.models import SecurityUserRoleModel
from camp_match.modules.security.domain.value_objects import Role
from camp_match.platform.db.session import create_engine, create_session_factory


async def assign_role(email: str, role_name: str) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    try:
        role = Role[role_name.upper()]
    except KeyError:
        valid_roles = [r.name for r in Role]
        print(f"Error: Invalid role '{role_name}'. Valid roles are: {valid_roles}")
        sys.exit(1)

    async with session_factory() as session:
        # Find account by email
        stmt = select(AccountModel).where(AccountModel.email == email)
        result = await session.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            print(f"Error: No account found with email '{email}'")
            sys.exit(1)

        identity_id = account.id

        # Check if role already assigned
        role_stmt = select(SecurityUserRoleModel).where(
            SecurityUserRoleModel.identity_id == identity_id,
            SecurityUserRoleModel.role == role.name,
        )
        existing_role = (await session.execute(role_stmt)).scalar_one_or_none()

        if existing_role:
            print(f"User {email} already has role {role.name}.")
        else:
            user_role = SecurityUserRoleModel(
                id=uuid4(),
                identity_id=identity_id,
                role=role.name,
            )
            session.add(user_role)
            await session.commit()
            print(
                f"Successfully assigned role {role.name} to user {email} "
                f"(identity_id: {identity_id})."
            )

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign a role to a user account by email.")
    parser.add_argument("email", help="User account email address")
    parser.add_argument("role", help="Role name to assign (e.g. OPERATIONS, ADMIN)")
    args = parser.parse_args()

    asyncio.run(assign_role(args.email, args.role))


if __name__ == "__main__":
    main()
