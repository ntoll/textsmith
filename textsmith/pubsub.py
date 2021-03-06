"""
The pub/sub message passing methods and handlers needed for TextSmith.

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
import asyncio
import structlog  # type: ignore
from asyncio_redis import Subscription  # type: ignore
from asyncio_redis.exceptions import Error, ErrorReply  # type: ignore


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
        # Key: user_id Value: deque of pending messages (for all users
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
        self.connected_users[user_id] = asyncio.Queue()
        try:
            await self.subscriber.subscribe(
                [
                    str(user_id),
                ]
            )
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error subscribing to channel.",
                user_id=user_id,
                connection_id=connection_id,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg("Subscribe.", user_id=user_id, connection_id=connection_id)

    async def unsubscribe(self, user_id: int, connection_id: str) -> None:
        """
        Remove the user ID from the list of channels to which this instance
        subscribes via Redis. Delete the message queue for the referenced user.
        Log this event. If there are undelivered messages, log these.
        """
        self.connected_users.pop(user_id, None)
        try:
            await self.subscriber.unsubscribe(
                [
                    str(user_id),
                ]
            )
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error unsubscribing from channel.",
                user_id=user_id,
                connection_id=connection_id,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg(
            "Unsubscribe.", user_id=user_id, connection_id=connection_id
        )

    async def listen(self) -> None:
        """
        Listen to the messages on subscribed channels. Each channel represents
        an object ID. If the object ID is a user connected to this application,
        then it's put into the message queue for that user, to be sent via the
        websocket connection.
        """
        self.listening = True
        while self.listening:
            try:
                message = await self.subscriber.next_published()
                user_id = int(message.channel)
                logger.msg("Message.", user_id=user_id, value=message.value)
                if user_id in self.connected_users:
                    await self.connected_users[user_id].put(message.value)
            except ValueError:
                logger.msg(
                    "Bad Message.",
                    channel=message.channel,
                    value=message.value,
                )
            except StopIteration:  # pragma: no cover
                logger.msg(
                    "Broken subscriber.",
                )
                self.listening = False
                break
            except (Error, ErrorReply) as ex:  # pragma: no cover
                self.listening = False
                logger.msg(
                    "Error listening to Redis PubSub.",
                    exc_info=ex,
                    redis_error=True,
                )
                break

    async def get_message(self, user_id: int) -> str:
        """
        Return the next message in the message queue for the referenced user.
        Otherwise, return an empty string (indicating no messages).
        """
        if not self.listening:
            raise ValueError(f"Cannot get messages for user {user_id}.")
        message_queue = self.connected_users.get(user_id)
        if message_queue:
            result = await message_queue.get()
            return result
        else:
            return ""

    async def stop(self) -> None:
        """
        Cleanly stop listening to the Redis PubSub.
        """
        self.listener.cancel()
        try:
            await self.listener
        except asyncio.CancelledError:
            logger.msg("Stop PubSub.", subscribed=self.connected_users)
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error stopping listener to Redis PubSub.",
                exc_info=ex,
                redis_error=True,
            )
