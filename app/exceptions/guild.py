from uuid import UUID


class GuildNotFoundError(Exception):
    def __init__(self, guild_id: UUID) -> None:
        self.guild_id = guild_id
        super().__init__(f"Guild {guild_id} was not found.")

class OwnerCannotLeaveGuildError(Exception):
    def __init__(self, guild_id: UUID) -> None:
        self.guild_id = guild_id

        super().__init__(
            f"The owner of Guild {guild_id} cannot leave "
            "without transferring ownership or deleting the Guild."
        )
class GuildOwnerRequiredError(Exception):
    def __init__(self, guild_id: UUID) -> None:
        self.guild_id = guild_id
        super().__init__(
            f"Only the owner of Guild {guild_id} may perform this operation."
        )
class GuildMembershipRequiredError(Exception):
    def __init__(self, guild_id: UUID) -> None:
        self.guild_id = guild_id
        super().__init__(
            f"Membership in Guild {guild_id} is required."
        )