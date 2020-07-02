"""
Functions for parsing the user input. Calls into the game logic layer to affect
changes and read data from the datastore.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import random
import structlog  # type: ignore
from uuid import uuid4
from textsmith.logic import Logic
from flask_babel import gettext as _  # type: ignore


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
            exc_info=exception,
        )
        await self.logic.emit_to_user(
            user_id,
            _("Sorry. Something went wrong when processing your command."),
        )

    async def parse(self, user_id: int, connection_id: str, message: str):
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
        that verb (as defined in this module).

        If the verb isn't built into the game engine, then the parser breaks
        the raw input apart into sections that follow the following patterns:

        VERB
        VERB DIRECT-OBJECT
        VERB DIRECT-OBJECT PREPOSITION INDIRECT-OBJECT

        Examples of these patterns are:

        look
        take sword
        give sword to andrew
        say "Hello there" to nicholas

        NOTE: English articles ("a", "the" etc) shouldn't be used in commands.

        Anything enclosed in double-quotes (") is treated as a single entity if
        in the direct-object or indirect-object position. The parser will try
        to match objects against available aliases available in the current
        room's context. The following reserved words are synonyms:

        "me" - the user.
        "here" - the current location.

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
        attribute's value is a string and that string has the characters
        "#!" (hash-bang) at the start, then it'll attempt to evaluate the rest
        of the string as a script (see the script module for more detail of how
        this works).

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

        # Give new messages a message_id for debugging purposes.
        message_id = str(uuid4())
        logger.msg(
            "Assigning message id.",
            message=message,
            message_id=message_id,
            user_id=user_id,
            connection_id=connection_id,
        )

        # Check and process special "shortcut" characters.
        message = message.lstrip()
        if message.startswith('"'):
            # " The user is saying something to everyone in their location.
            return await self.say(
                user_id, connection_id, message_id, message[1:]
            )
        elif message.startswith("!"):
            # ! The user is shouting something to everyone in their location.
            return await self.shout(
                user_id, connection_id, message_id, message[1:]
            )
        elif message.startswith(":"):
            # : The user is emoting something to everyone in their location.
            return await self.emote(
                user_id, connection_id, message_id, message[1:]
            )
        elif message.startswith("@"):
            # @ The user is saying something to a specific person in their
            # location.
            return await self.tell(
                user_id, connection_id, message_id, message[1:]
            )

        """
        # Gather the context in which the message is to be parsed.
        context = await self.logic.gather_context(
            user_id, connection_id, message_id
        )

        # Check for verbs built into the game.
        split_message = message.split(" ", 1)
        verb = split_message[0]  # The first word in a message is a verb.
        args = ""
        if len(split_message) == 2:
            # The remainder of the message contains the "arguments" to use with
            # the verb, and may ultimately contain the direct and indirectt
            # objects (if needed).
            args = split_message[1]
        """

        # Act of last resort ~ choose a stock fun response. ;-)
        response = random.choice(
            [
                _("I don't understand that."),
                _("Nope. No idea what you're on about."),
                _("I don't know what you mean."),
                _("Try explaining that in a way I can understand."),
                _("Yeah right... as if I know what you're on about. :-)"),
                _("Let me try tha... nope."),
                _("Ummm... you're not making sense. Again, but with feeling!"),
                _("No idea. Try giving me something I understand."),
                _("Huh? I don't understand. Maybe ask someone for help?"),
                _("Try using commands I understand."),
            ]
        )
        i_give_up = f'"{message}", ' + response
        return await self.logic.emit_to_user(user_id, i_give_up)

    async def say(self, user_id, connection_id, message_id, message):
        """
        Say the message to everyone in the current location.
        """
        pass

    async def shout(self, user_id, connection_id, message_id, message):
        """
        Shout (ALL CAPS) the message to everyone in the current location.
        """
        pass

    async def emote(self, user_id, connection_id, message_id, message):
        """
        Emote the message to everyone in the current location.
        """
        pass

    async def tell(self, user_id, connection_id, message_id, message):
        """
        Say the message to a specific person whilst being overheard by everyone
        else in the current location.
        """
        pass
