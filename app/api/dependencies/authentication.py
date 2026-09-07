from typing import Annotated
from uuid import UUID

from fastapi import Header


async def get_current_user_id(
    x_user_id: Annotated[UUID, Header(alias="X-User-Id")],
) -> UUID:
    return x_user_id