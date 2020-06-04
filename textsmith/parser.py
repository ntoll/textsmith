"""
Functions for parsing the user input. Calls into the game logic layer to affect
changes and read data from the datastore.

Copyright (C) 2019 Nicholas H.Tollervey.
"""
import structlog  # type: ignore
from flask_babel import gettext as _  # type: ignore
from textsmith.logic import Logic


logger = structlog.get_logger()


class Parser:
    """
    Gathers together methods to parse user input. Uses the dependency
    injection pattern.
    """

    def __init__(self, logic: Logic):
        """
        The logic object contains methods for implementing game logic and
        state transitions.
        """
        self.logic = logic

    async def eval(self, user_id: int, connection_id: str, message: str):
        """
        Evaluate the user's input message. If there's an error, recover by
        sending the error message from the associated exception object.
        """
        try:
            await self.parse(user_id, connection_id, message)
        except Exception as ex:
            await self.handle_exception(user_id, connection_id, ex)

    async def handle_exception(self, user_id, connection_id, exception):
        """
        Given an exception raised in the logic or parsing layer of the game,
        extract the useful message which explains what the problem is, and turn
        it into a message back to the referenced user.
        """
        logger.msg(
            "Exception",
            user_id=user_id,
            connection_id=connection_id,
            exception=exception,
        )
        await self.logic.emit_to_user(
            user_id,
            _("Sorry. Something went wrong when processing your command."),
        )

    async def parse(self, user_id: int, connection_id: str, message: str):
        await self.logic.emit_to_user(user_id, f"You typed: '{message}'")
