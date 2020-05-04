"""
The pub/sub message passing methods and handlers needed for TextSmith.

Copyright (C) 2019 Nicholas H.Tollervey.
"""
import asyncio
import structlog  # type: ignore
from asyncio_redis import Subscription  # type: ignore


logger = structlog.get_logger()


class PubSub:
    """
    Contains methods needed to manage listening for messages broadcast on the
    pub/sub layer of the game.
    """

    def __init__(self, subscriber: Subscription) -> None:
        """
        The subscriber object represents a connection to Redis in "subscribe"
        mode (i.e. listening for messages).
        """
        # Key: user_id Value: list of pending messages (for all users
        # connected this instance).
        self.connected_users = {}  # type: dict
        # The Redis connection used to subscribe to pub/sub messages.
        self.subscriber = subscriber
        # A flag to show if new messages are retrievable.
        self.listening = False
        # Schedule a task to constantly listen for new messages on
        # subscribed-to channels.
        self.listener = asyncio.create_task(self.listen())

    async def subscribe(self, user_id: int, connection_id: str) -> None:
        """
        Ensure there's an entry for the referenced user's message queue.
        Add the user ID to the list of channels this instance subscribes to
        via Redis. Log this event.
        """
        self.connected_users[user_id] = []
        await self.subscriber.subscribe(
            [str(user_id),]
        )
        logger.msg("Subscribe.", user_id=user_id, connection_id=connection_id)

    async def unsubscribe(self, user_id: int, connection_id: str) -> None:
        """
        Remove the user ID from the list of channels to which this instance
        subscribes via Redis. Delete the message queue for the referenced user.
        Log this event. If there are undelivered messages, log these.
        """
        undelivered_messages = self.connected_users.pop(user_id, None)
        await self.subscriber.unsubscribe(
            [str(user_id),]
        )
        logger.msg(
            "Unsubscribe.", user_id=user_id, connection_id=connection_id
        )
        if undelivered_messages:
            logger.msg(
                "Undelivered messages.",
                user_id=user_id,
                connection_id=connection_id,
                undelivered_messages=undelivered_messages,
            )

    async def listen(self) -> None:
        """
        Listen to the messages on subscribed channels. Each channel represents
        an object ID. If the object ID is a user connected to this application,
        then it's put into the message queue for that user, to be sent via the
        websocket connection.
        """
        self.listening = True
        while True:
            try:
                message = await self.subscriber.next_published()
                user_id = int(message.channel)
                logger.msg("Message.", user_id=user_id, value=message.value)
                if user_id in self.connected_users:
                    self.connected_users[user_id].append(message.value)
            except StopIteration:
                logger.msg("Broken subscriber.",)
                self.listening = False
                break
            except ValueError:
                logger.msg(
                    "Bad Message.",
                    channel=message.channel,
                    value=message.value,
                )

    async def get_message(self, user_id: int) -> str:
        """
        Return the next message in the message queue for the referenced user.
        Otherwise, return an empty string (indicating no messages).
        """
        if not self.listening:
            raise ValueError(f"Cannot get messages for user {user_id}.")
        message_queue = self.connected_users.get(user_id)
        if message_queue:
            message = message_queue[0]
            self.connected_users[user_id] = message_queue[1:]
            return message
        else:
            return ""

    async def stop(self):
        self.listener.cancel()
        try:
            await self.listener
        except asyncio.CancelledError:
            logger.msg("Stop PubSub.", subscribed=self.connected_users)
