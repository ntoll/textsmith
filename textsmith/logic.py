"""
Functions that implement application logic.

Copyright (C) 2020 Nicholas H.Tollervey (ntoll@ntoll.org).

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
import aiosmtplib  # type: ignore
import structlog  # type: ignore
import markdown  # type: ignore
from typing import Sequence, Dict, Union, Tuple
from email.message import EmailMessage
from uuid import uuid4
from flask_babel import gettext as _  # type: ignore
from textsmith.datastore import DataStore
from textsmith import constants


logger = structlog.get_logger()


class Logic:
    """
    Gathers together methods which implement application logic. Uses the
    dependency injection pattern.
    """

    def __init__(
        self,
        datastore: DataStore,
        email_host: str,
        email_port: int,
        email_from: str,
        email_password: str,
    ) -> None:
        """
        The datastore object contains methods for getting, setting and
        searching the permenant data store.
        """
        self.datastore = datastore
        self.email_host = email_host
        self.email_port = email_port
        self.email_from = email_from
        self.email_password = email_password

    async def verify_credentials(self, email: str, password: str) -> int:
        """
        Given a user's email and password, return the user's in-game object id
        or else 0 to indicate verification failed.
        """
        is_valid = await self.datastore.verify_user(email, password)
        if is_valid:
            object_id = await self.datastore.email_to_object_id(email)
            return object_id
        else:
            return 0

    async def set_last_seen(self, email: str) -> None:
        """
        Set the last_seen timestamp to time.now() for the user with the
        referenced email address.
        """
        await self.datastore.set_last_seen(email)

    async def check_email(self, email: str) -> bool:
        """
        Return a boolean indication if an email address is not already taken.
        """
        return await self.datastore.user_exists(email)

    async def check_token(self, confirmation_token: str) -> Union[str, None]:
        """
        Return the email address of the user associated with the token, or
        None if it doesn't exist.
        """
        return await self.datastore.token_to_email(confirmation_token)

    async def create_user(self, email: str) -> None:
        """
        Create a user with the referenced email. Email a confirmation link
        with instructions for setting up a password to the new user.
        """
        confirmation_token = str(uuid4())
        await self.datastore.create_user(email, confirmation_token)
        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = email
        message["Subject"] = _("Textsmith registration.")
        message.set_content(_("This is a test... ") + confirmation_token)
        await self.send_email(message)

    async def confirm_user(
        self, confirmation_token: str, password: str
    ) -> None:
        """
        Given the user has followed the link containing the confirmation token
        and successfully set a valid password: update their record, activate
        them and send them a welcome email.
        """
        email = await self.datastore.confirm_user(confirmation_token, password)
        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = email
        message["Subject"] = _("Welcome to Textsmith.")
        message.set_content(_("User confirmed."))
        await self.send_email(message)

    async def send_email(self, message: EmailMessage) -> None:
        """
        Asynchronously log and send the referenced email.message.EmailMessage.
        """
        logger.msg(
            "Send email.",
            content=message.get_content(),
            **{k: v for k, v in message.items()},
        )
        await aiosmtplib.send(
            message,
            hostname=self.email_host,
            port=self.email_port,
            username=self.email_from,
            password=self.email_password,
            use_tls=True,
        )

    async def emit_to_user(self, user_id: int, message: str) -> None:
        """
        Emit a message to the referenced user. All messages are run through
        Markdown.
        """
        output = markdown.markdown(
            str(message),
            extensions=["textsmith.mdx.video", "textsmith.mdx.audio"],
        )
        await self.datastore.redis.publish(str(user_id), output)

    async def emit_to_room(
        self, room_id: int, exclude: Sequence[int], message: str
    ) -> None:
        """
        Emit a message to all users not in the exclude list in the referenced
        room.
        """
        contents: Dict = await self.datastore.get_contents(room_id)
        for value in contents.values():
            if (
                value.get(constants.IS_USER, False)
                and value["id"] not in exclude
            ):
                await self.emit_to_user(value["id"], message)

    async def get_user_context(
        self, user_id: int, connection_id: str, message_id: str
    ) -> Dict:
        """
        Return a dictionary representation of the immediate context in which
        the user finds themselves::

            {
                "user": { ... user's attributes ... },
                "room": { ... room's attributes ... },
            }
        """
        result = await self.datastore.get_user_context(user_id)
        logger.msg(
            "User context.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            context=result,
        )
        return result

    async def get_script_context(
        self, user_id: int, connection_id: str, message_id: str
    ) -> Dict:
        """
        Return a dictionary representation of the room-wide context in which
        the user finds themselves::

            {
                "user": { ... user's attributes ... },
                "room": { ... room's attributes ... },
                "exits": [{ ... exits from the room ... }, ],
                "users": [{ ... other users in the room ...}, ],
                "things": [{ ... other objects in the room ...}, ],
            }
        """
        result = await self.datastore.get_script_context(user_id)
        logger.msg(
            "Script context.",
            user_id=user_id,
            connection_id=connection_id,
            message_id=message_id,
            context=result,
        )
        return result

    async def get_attribute_value(self, obj: Dict, attribute: str) -> str:
        """
        Return the value of the referenced object attribute. If the value is
        a string that starts with ``constants.IS_SCRIPT`` evaluate it and
        return the result. Otherwise, return a string representation of the
        value. If there is no such value, return an empty string.
        """
        if attribute in obj:
            val = obj.get(attribute)
            if val is not None:
                if isinstance(val, str):
                    if val.strip().startswith(constants.IS_SCRIPT):
                        # Evaluate the code and return the result.
                        pass
                return str(val)
        return ""

    def match_object(
        self, identifier: str, context: Dict
    ) -> Tuple[Sequence[Dict], str]:
        """
        Given a potentially ambiguous user entered identifier, try to find a
        matching object in the given context.

        An object's name, object id or alias is assumed to begin the identifier
        string. The identifier string is always normalised: it is stripped of
        leading and trailing whitespace and matches are case insensitive.

        An object id is an integer starting with "#". For example, #123.

        A name or alias may be a multi-word reference to the object.

        A match will be the shortest sequence of words that also match the id,
        name or aliases of those objects that are the current user, the current
        room, exits from the current room, other users within the current room
        and things found in the current room all in the current context.

        The special aliases found in constants.USER_ALIASES always refer to the
        current user, and aliases found in constants.ROOM_ALIASES refer to the
        current room.

        This method returns two values: a list of matching objects (or an empty
        list of no matches found), and a string representing the token that
        made the match (or an empty string if there were no matches).

        For example, given the identifier: "#378 some more text", the return
        values will be a list containing a single dictionary representing the
        object with the id 378, and a string "#378" to indicate it was "#378"
        that caused the match.
        """
        # Normalize identifier.
        identifier = identifier.strip().lower()
        if not identifier:
            return [], ""

        # Simple special aliases.
        words = identifier.split()
        if words[0] in constants.USER_ALIASES:
            return [
                context["user"],
            ], words[0]
        if words[0] in constants.ROOM_ALIASES:
            return [
                context["room"],
            ], words[0]

        # Candidate objects are things in the current context to which the user
        # may refer.
        candidate_objects = (
            [
                context["user"],
                context["room"],
            ]
            + context["exits"]
            + context["users"]
            + context["things"]
        )

        # Check for object id in candidate objects.
        if constants.MATCH_OBJECT_ID.match(words[0]):
            object_id = int(words[0][1:])
            matches = [
                obj for obj in candidate_objects if obj["id"] == object_id
            ]
            if matches:
                # Matches by valid object_id.
                return matches, words[0]
            else:
                # No match for a valid object_id.
                return [], ""

        # Check for matching names or aliases.
        matched_objects = []
        word_list = []
        for word in words:
            word_list.append(word)
            name = " ".join(word_list)
            for obj in candidate_objects:
                if self.matches_name(name, obj):
                    matched_objects.append(obj)
            if matched_objects:
                return matched_objects, name
        # No matches.
        return [], ""

    def matches_name(self, name: str, obj: Dict) -> bool:
        """
        Returns a boolean indication if the referenced object matches the
        given name. This is case insensitive and checks the name and alias list
        for a name match.
        """
        name = name.lower()
        obj_name = obj.get(constants.NAME, "").lower()
        if obj_name == name:
            return True
        aliases = [alias.lower() for alias in obj.get(constants.ALIAS, [])]
        if name in aliases:
            return True
        return False

    async def clarify_object(
        self, user_id: int, message: str, match: Sequence[Dict]
    ) -> None:
        """
        A problem match (containing more than one object) needs to be handled
        by asking the user to clarify or re-state their term of reference to
        the desired object.
        """
        preamble = _("The following message was ambiguous:")
        message = '  "' + message + '"'
        object_intro = _("Multiple objects matched:")
        request = _(
            "Please try to be more specific (an object's ID is unique)."
        )
        object_details = []
        for obj in match:
            name = obj.get(constants.NAME, "")
            obj_id = obj["id"]
            aliases = ", ".join(obj.get(constants.ALIAS, []))
            object_details.append(f"  {name} (#{obj_id}) [{aliases}]")
        matched_objects = "\n".join(object_details)
        response = "\n\n".join(
            [
                preamble,
                message,
                object_intro,
                matched_objects,
                request,
            ]
        )
        await self.emit_to_user(
            user_id, constants.SYSTEM_OUTPUT.format(response)
        )

    async def no_matching_object(self, user_id: int, message: str) -> None:
        """
        There is a problem because the expected object match could not be
        found. Report this and ask the user to clarify or re-state their term
        of reference to the desired object.
        """
        preamble = _("The following message didn't match any objects:")
        message = '  "' + message + '"'
        request = _(
            "Please try to be more specific (an object's ID is unique)."
        )
        response = "\n\n".join(
            [
                preamble,
                message,
                request,
            ]
        )
        await self.emit_to_user(
            user_id, constants.SYSTEM_OUTPUT.format(response)
        )
