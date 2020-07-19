"""
Functions for parsing the user input. Calls into the game logic layer to affect
changes and read data from the datastore.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import random
import html
import structlog  # type: ignore
from uuid import uuid4
from textsmith.logic import Logic
from textsmith.verbs import Verbs, UnknownVerb
from flask_babel import gettext as _  # type: ignore
from textsmith import constants


logger = structlog.get_logger()


class Parser:
    """
    Gathers together methods to parse user input. Uses the dependency
    injection pattern.
    """

    def __init__(self, logic: Logic) -> None:
        """
        The logic object contains methods for implementing game logic and
        state transitions.
        """
        self.logic = logic
        self.verbs = Verbs(self.logic)  # Built in verbs/functions.

    async def eval(
        self, user_id: int, connection_id: str, message: str
    ) -> None:
        """
        Evaluate the user's input message. If there's an error, recover by
        sending the error message from the associated exception object.
        """
        # Give new messages a message_id for debugging purposes.
        message_id = str(uuid4())
        logger.msg(
            "Assigning message id.",
            message=message,
            message_id=message_id,
            user_id=user_id,
            connection_id=connection_id,
        )
        try:
            # All user input is immediately cleaned so it's safe to render
            # client side.
            escaped = html.escape(message)
            await self.parse(user_id, connection_id, message_id, escaped)
        except Exception as ex:
            await self.handle_exception(
                user_id, connection_id, message_id, message, ex
            )

    async def handle_exception(
        self,
        user_id: int,
        connection_id: str,
        message_id: str,
        message: str,
        exception: Exception,
    ) -> None:
        """
        Given an exception raised in the logic or parsing layer of the game,
        extract the useful message which explains what the problem is, and turn
        it into a message back to the referenced user.
        """
        logger.msg(
            "Exception.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            message=message,
            exc_info=exception,
        )
        reply: str = " ".join(
            [
                _("Sorry. Something went wrong when processing your command."),
                f"id: {message_id}",
            ]
        )
        await self.logic.emit_to_user(
            user_id, constants.SYSTEM_OUTPUT.format(reply)
        )

    async def parse(
        self, user_id: int, connection_id: str, message_id: str, message: str
    ) -> None:
        """
        Parse the incoming message from the referenced user.

        There are four special characters which, if they start the message, act
        as shortcuts for common communication related activities:

        " - the user says whatever follows in the message.
        ! - make it appear like the user is shouting the message.
        : - "emote" the message directly as "username " + message.
        @ - the user is saying something directly to another @user.

        Next the parser expects the first word of the message to be a verb. If
        this verb is one of several built-in commands, the remainder of the
        message is passed as a single string into the relevant function for
        that verb (as defined in the verbs module). These verbs are translated
        by Babel, so the equivalent verbs in the user's preferred locale (if
        supported by TextSmith) should work instead.

        If the verb isn't built into the game engine, then the parser breaks
        the raw input apart into sections that follow the following patterns:

        VERB
        VERB DIRECT-OBJECT
        VERB DIRECT-OBJECT PREPOSITION INDIRECT-OBJECT

        Examples of these patterns are:

        look
        take sword
        give big sword to andrew
        say "Hello there" to nicholas

        NOTE: English articles ("a", "the" etc) shouldn't be used in commands.

        Verbs that start sentences are assumed to be single words. Direct
        objects and indirect objects may be identified via multiple words.

        Anything enclosed in double-quotes (") is treated as a single entity if
        in the direct-object or indirect-object position. The parser will try
        to match objects against available aliases available in the current
        room's context. If there are no matches or multiple matches then the
        parser will retain the string representation of the direct-object or
        indirect-object.

        The following lists of reserved words are synonyms:

        constants.USER_ALIASES - the user.
        constants.ROOM_ALIASES - the current location.

        These reserved words are actually translated by Babel, so the
        equivalent terms in the user's preferred locale (if supported by
        TextSmith) should work instead.

        At this point the parser has identified the verb string, and the direct
        and indirect objects. It looks for a matching verb on the four
        following objects (in order or precedence):

        1. The user giving the command.
        2. The room the user is in (including where the verb is an exit name).
        3. The direct object (if an object in the database).
        4. The indirect object (if an object in the database).

        The game checks each object in turn and, if it finds an attribute that
        matches the verb it attempts to "execute" it.

        Mostly, the attribute's value will be returned. However, if the
        attribute's value is a string and that string starts with the
        characters defined in constants.IS_SCRIPT, then it'll attempt to
        evaluate the rest of the string as a script (see the script module for
        more detail of how this works).

        If such "executable" attributes are found then the associated code will
        be run with the following objects in scope:

        user - a reference to the user who issued the command.
        room - a reference to the room in which the user is situated.
        exits - objects that allow the user to move out of the current room.
        users - objects representing other users currently in the current room.
        things - all the other objects currently in the room.
        this - a reference to the object which matched the verb (the user, room
          or other object in scope).
        direct_object - either the matching object or raw string for the direct
          object. This could be None.
        preposition - a string containing the preposition. This could be None.
        indirect_object - either the matching object or raw string for the
          indirect object. This could be None.

        The user, room, direct_object and indirect_object objects can all be
        passed to a special "emit" function along with a message to display to
        that object (if the object is a user, it'll be sent just to them, if
        the object is a room, the message will be sent to all users in that
        room).

        That's it!
        """
        # Don't do anything with empty messages.
        if not message.strip():
            return

        # Check and process special "shortcut" characters.
        message = message.lstrip()
        if message.startswith('"'):
            # " The user is saying something to everyone in their location.
            return await self.verbs._say(
                user_id, connection_id, message_id, message[1:]
            )
        elif message.startswith("!"):
            # ! The user is shouting something to everyone in their location.
            return await self.verbs._shout(
                user_id, connection_id, message_id, message[1:]
            )
        elif message.startswith(":"):
            # : The user is emoting something to everyone in their location.
            return await self.verbs._emote(
                user_id, connection_id, message_id, message[1:]
            )
        elif message.startswith("@"):
            # @ The user is saying something to a specific person in their
            # location.
            return await self.verbs._tell(
                user_id, connection_id, message_id, message[1:]
            )

        # Check for verbs built into the game.
        split_input = message.split(" ", 1)
        verb = split_input[0]  # The first word in a message is a verb.
        args = ""
        if len(split_input) == 2:
            # The remainder of the message contains the "arguments" to use with
            # the verb, and may ultimately contain the direct and indirect
            # objects (if needed).
            args = split_input[1]
        try:
            return await self.verbs(
                user_id, connection_id, message_id, verb, args
            )
        except UnknownVerb:
            # No matching verb has been found, so pass on silently.
            pass

        # Act of last resort ~ choose a stock fun response. ;-)
        response = random.choice(constants.HUH)
        i_give_up = f'"{message}", ' + response
        return await self.logic.emit_to_user(user_id, i_give_up)
