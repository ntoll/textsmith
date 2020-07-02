"""
Functions that implement application logic.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import aiosmtplib  # type: ignore
import structlog  # type: ignore
import markdown  # type: ignore
from typing import Sequence, Dict, Union
from email.message import EmailMessage
from uuid import uuid4
from textsmith import defaults
from textsmith.datastore import DataStore


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
    ):
        """
        The datastore object contains methods for getting, setting and
        searching the permenant data store.
        """
        self.datastore = datastore
        self.email_host = email_host
        self.email_port = email_port
        self.email_from = email_from
        self.email_password = email_password

    async def verify_password(self, email: str, password: str) -> int:
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

    async def set_last_login(self, user_id):
        """
        Set the last_login timestamp to time.now() for the referenced user.
        """
        await self.datastore.set_last_seen(user_id)

    async def check_email(self, email: str) -> bool:
        """
        Return a boolean indication if the username is both valid and not
        already taken.
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
        message["Subject"] = "Textsmith registration."
        message.set_content("This is a test... " + confirmation_token)
        await self.send_email(message)

    async def confirm_user(self, confirmation_token: str, password: str):
        """
        Given the user has followed the link containing the confirmation token
        and successfully set a valid password: update their record, activate
        them and send them a welcome email.
        """
        email = await self.datastore.confirm_user(confirmation_token, password)
        message = EmailMessage()
        message["From"] = self.email_from
        message["To"] = email
        message["Subject"] = "Welcome to Textsmith."
        message.set_content("User confirmed.")
        await self.send_email(message)

    async def send_email(self, message: EmailMessage) -> None:
        """
        Asynchronously log and send the referenced email.message.EmailMessage.
        """
        logger.msg(
            "Send email.",
            content=message.get_content(),
            **{k: v for k, v in message.items()}
        )
        await aiosmtplib.send(
            message,
            hostname=self.email_host,
            port=self.email_port,
            username=self.email_from,
            password=self.email_password,
            use_tls=True,
        )

    async def emit_to_user(self, user_id: int, message: str):
        """
        Emit a message to the referenced user. All messages are run through
        Markdown.
        """
        output = markdown.markdown(
            str(message),
            extensions=["textsmith.mdx.video", "textsmith.mdx.audio"],
        )
        await self.datastore.redis.publish(str(user_id), output)

    async def emit_to_location(
        self, room_id: int, exclude: Sequence[int], message: str
    ):
        """
        Emit to all users not in the exclude list in the referenced room.
        """
        contents: Dict = await self.datastore.get_contents(room_id)
        for key, value in contents:
            if defaults.IS_USER in value:
                await self.emit_to_user(value["id"], message)

    async def gather_context(
        self, user_id: int, connection_id: str, message_id: str
    ) -> Dict:
        """
        Return a dictionary representation of the current context in which the
        user finds themselves.

        {
          "user": the object representing the user issuing the command,
          "room": the object representing the room containing the user,
          "objects": a list of all the objects in the same room as the user,
        }
        """
        return {}
