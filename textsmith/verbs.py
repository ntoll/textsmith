"""
Contains definitions of verbs built into the system that encompass the core
behaviours possible within the system.

Copyright (C) 2020 Nicholas H.Tollervey (ntoll@ntoll.org).
"""
"""
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>
"""
import structlog  # type: ignore
from textsmith import constants
from textsmith.logic import Logic
from flask_babel import gettext as _  # type: ignore


logger = structlog.get_logger()


class UnknownVerb(Exception):
    """
    An exception that indicates the passed in verb was not found.
    """

    pass


class Verbs:
    """
    Contains definitions of built-in verbs. These express the core fundamental
    capabilities of the world. Everything else is expressed in the scripting
    language.

    The methods for verbs should NOT be called directly. Rather just call the
    Verb object with the verb written as appropriately for the user's locale
    and the translation to the actual method to use will happen automatically.
    """

    def __init__(self, logic: Logic) -> None:
        """
        The logic object contains methods for implementing game logic and
        state transitions.
        """
        self.logic = logic
        self.languages = [
            "en",
        ]  # TODO: Add more. :-)
        self._VERBS = {
            "en": {
                # Say something.
                ("say",): self._say,
                # Shout something.
                ("shout", "scream", "holler",): self._shout,
                # Emote something.
                ("emote",): self._emote,
                # Tell something to someone.
                ("tell",): self._tell,
            }
        }

    async def __call__(
        self,
        user_id: int,
        connection_id: str,
        message_id: str,
        verb: str,
        message: str,
        locale: str = None,
    ) -> None:
        """
        Attempt to call the given verb, in the given context, with the given
        message in the given locale. If the verb wasn't found, this method will
        raise a ValueError.
        """
        if locale in self._VERBS:
            verbs = self._VERBS[locale]
        else:
            verbs = self._VERBS["en"]  # Default to English if in doubt.
        for matches in verbs:
            if verb.lower() in matches:
                return await verbs[matches](
                    user_id, connection_id, message_id, message
                )
        raise UnknownVerb("No such verb.")

    async def _say(
        self, user_id: int, connection_id: str, message_id: str, message: str
    ) -> None:
        """
        Say the message to everyone in the current location.
        """
        logger.msg(
            "Say something.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            message=message,
        )
        message = message.strip()
        if message:
            context = await self.logic.get_user_context(
                user_id, connection_id, message_id
            )
            user_message = _('> You say, "*{message}*".').format(
                message=message
            )
            await self.logic.emit_to_user(user_id, user_message)
            if "room" in context:
                username = await self.logic.get_attribute_value(
                    context["user"], constants.NAME
                )
                room_message = _('> {username} says, "*{message}*".').format(
                    username=username, message=message
                )
                await self.logic.emit_to_room(
                    context["room"]["id"], [user_id,], room_message
                )

    async def _shout(
        self, user_id: int, connection_id: str, message_id: str, message: str
    ) -> None:
        """
        Shout (<strong></strong>) the message to everyone in the current
        location.
        """
        logger.msg(
            "Shout something.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            message=message,
        )
        message = message.strip()
        if message:
            context = await self.logic.get_user_context(
                user_id, connection_id, message_id
            )
            user_message = _('> You shout, "**{message}**".').format(
                message=message
            )
            await self.logic.emit_to_user(user_id, user_message)
            if "room" in context:
                username = await self.logic.get_attribute_value(
                    context["user"], constants.NAME
                )
                room_message = _(
                    '> {username} shouts, "**{message}**".'
                ).format(username=username, message=message)
                await self.logic.emit_to_room(
                    context["room"]["id"], [user_id,], room_message
                )

    async def _emote(
        self, user_id: int, connection_id: str, message_id: str, message: str
    ) -> None:
        """
        Emote the message to everyone in the current location.
        """
        logger.msg(
            "Emote something.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            message=message,
        )
        message = message.strip()
        if message:
            context = await self.logic.get_user_context(
                user_id, connection_id, message_id
            )
            username = await self.logic.get_attribute_value(
                context["user"], constants.NAME
            )
            emoted = _("{username} {message}").format(
                username=username, message=message
            )
            await self.logic.emit_to_user(user_id, emoted)
            if "room" in context:
                await self.logic.emit_to_room(
                    context["room"]["id"], [user_id,], emoted
                )

    async def _tell(
        self, user_id: int, connection_id: str, message_id: str, message: str
    ) -> None:
        """
        Say the message to a specific person whilst being overheard by everyone
        else in the current location.
        """
        logger.msg(
            "Tell something.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            message=message,
        )
        message = message.strip()
        if message:
            context = await self.logic.get_script_context(
                user_id, connection_id, message_id
            )
            match, token = self.logic.match_object(message, context)
            matches = len(match)
            if matches == 1:
                username = await self.logic.get_attribute_value(
                    context["user"], constants.NAME
                )
                recipient = await self.logic.get_attribute_value(
                    match[0], constants.NAME
                )
                recipient_id = match[0]["id"]
                room = context.get("room", {})
                room_id = room.get("id", 0)
                # The clean_message is the message content without the
                # recipient at the start.
                clean_message = message.replace(token, "").strip()
                if clean_message:
                    # Only emit if there's something to say to the recipient.
                    user_msg = _(
                        '> You say to {recipient}, "*{message}*".'
                    ).format(recipient=recipient, message=clean_message)
                    recipient_msg = _(
                        '> {username} says, "*{message}*" to you.'
                    ).format(username=username, message=clean_message)
                    room_msg = _(
                        '> {username} says to {recipient}, "*{message}*".'
                    ).format(
                        username=username,
                        recipient=recipient,
                        message=clean_message,
                    )
                    await self.logic.emit_to_user(user_id, user_msg)
                    await self.logic.emit_to_user(recipient_id, recipient_msg)
                    if room_id:
                        await self.logic.emit_to_room(
                            room_id, [user_id, recipient_id,], room_msg
                        )
            elif matches == 0:
                await self.logic.no_matching_object(user_id, "@" + message)
            else:
                await self.logic.clarify_object(user_id, "@" + message, match)
