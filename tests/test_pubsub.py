"""
Tests for the pub/sub message passing methods and handlers.

Copyright (C) 2019 Nicholas H.Tollervey
"""
import pytest  # type: ignore
import asynctest  # type: ignore
from uuid import uuid4
from unittest import mock
from textsmith.pubsub import PubSub


def test_init():
    """
    Ensure the PubSub instance is initialised with the correct state.

    * There is an empty dictionary for tracking user's message queues assigned
      to connected_users.
    * The subscriber object (used to subscribe to the different Redis
      channels) is assigned to subsciber.
    * The async.create_task is called once with the coroutine created by the
      object's listen method.
    """
    mock_subscriber = mock.MagicMock()
    with mock.patch("textsmith.pubsub.asyncio") as mock_async, mock.patch(
        "textsmith.pubsub.PubSub.listen"
    ) as mock_listen:
        ps = PubSub(mock_subscriber)
        assert ps.connected_users == {}
        assert ps.subscriber == mock_subscriber
        assert mock_async.create_task.call_count == 1
        assert mock_listen.call_count == 1


@pytest.mark.asyncio
async def test_subscribe():
    """
    Ensure that when the object is asked to subscribe to messages for a
    specific user, the following changes take place:

    * An empty list (for the message queue) is initialised in the
      connected_users dictionary against the user_id key.
    * The subscriber object is awaited to subscribe to the Redis based message
      channel associated with the user_id.
    * The subscription event is logged.
    """
    mock_subscriber = asynctest.MagicMock()
    mock_subscriber.subscribe = asynctest.CoroutineMock()
    with asynctest.patch("textsmith.pubsub.logger") as mock_logger:
        ps = PubSub(mock_subscriber)
        user_id = 1
        connection_id = str(uuid4())
        await ps.subscribe(user_id, connection_id)
        assert user_id in ps.connected_users
        assert ps.connected_users[user_id] == []
        ps.subscriber.subscribe.assert_called_once_with(
            [str(user_id),]
        )
        mock_logger.msg.assert_called_once_with(
            "Subscribe.", user_id=user_id, connection_id=connection_id
        )


@pytest.mark.asyncio
async def test_unsubscribe():
    """
    Ensure that when the object is asked to unsubscribe from messages for a
    specific user, the following changes take place:

    * The entry associated with the user is removed from the connected_users
      dictionary.
    * The subsciber object is awaited to unsubscribe from the Redis based
      message channel associated with the user_id.
    * Both the unsubscribe event and any undelivered messages for the user
      are logged.
    """
    mock_subscriber = asynctest.MagicMock()
    mock_subscriber.unsubscribe = asynctest.CoroutineMock()
    user_id = 1
    connection_id = str(uuid4())
    with asynctest.patch("textsmith.pubsub.logger") as mock_logger:
        ps = PubSub(mock_subscriber)
        message_queue = [
            "Undelivererd",
            "Messages",
        ]
        ps.connected_users[user_id] = message_queue
        await ps.unsubscribe(user_id, connection_id)
        assert user_id not in ps.connected_users
        ps.subscriber.unsubscribe.assert_called_once_with(
            [str(user_id),]
        )
        assert mock_logger.msg.call_count == 2


@pytest.mark.asyncio
async def test_listen():
    """
    Ensure that messages receieved via pub/sub are added to the correct
    message queue for the referenced user.

    The only reason an exception is used as a side_effect is so it's possible
    to break out of the infinite loop used to keep polling for new messages.
    """
    user_id = 1
    mock_message = mock.MagicMock()
    mock_message.channel = str(user_id)
    mock_message.value = "This is the textual content of the message."
    mock_subscriber = asynctest.MagicMock()
    mock_subscriber.subscribe = asynctest.CoroutineMock()
    mock_subscriber.next_published = asynctest.CoroutineMock()
    mock_subscriber.next_published.side_effect = [
        mock_message,
    ]
    with asynctest.patch("textsmith.pubsub.logger") as mock_logger:
        ps = PubSub(mock_subscriber)
        await ps.subscribe(user_id, str(uuid4()))
        mock_logger.msg.reset_mock()
        await ps.listen()
        assert ps.connected_users[user_id] == [
            mock_message.value,
        ]
        assert mock_logger.msg.call_args_list[0] == mock.call(
            "Message.", user_id=user_id, value=mock_message.value
        )


@pytest.mark.asyncio
async def test_listen_bad_message():
    """
    If a message receieved via pub/sub does not have an integer as the channel
    name, then log the bad message and ignore.

    The only reason an exception is used as a side_effect is so it's possible
    to to break out of the infinite loop used to keep polling for new messages.
    """
    mock_message = mock.MagicMock()
    mock_message.channel = "hello"
    mock_message.value = "This is the textual content of the message."
    mock_subscriber = asynctest.MagicMock()
    mock_subscriber.next_published = asynctest.CoroutineMock()
    mock_subscriber.next_published.side_effect = [
        mock_message,
    ]
    with asynctest.patch("textsmith.pubsub.logger") as mock_logger:
        ps = PubSub(mock_subscriber)
        await ps.listen()
        assert mock_logger.msg.call_args_list[0] == mock.call(
            "Bad Message.", channel="hello", value=mock_message.value
        )


@pytest.mark.asyncio
async def test_get_message_that_exists():
    """
    Ensure, if there are messages in the queue, the first to be received is
    returned and the state of the queue is updated accordingly (the returned
    message is removed from the head of the queue).
    """
    user_id = 1
    message_queue = [
        "First message",
        "Second message",
        "Third message",
    ]
    mock_subscriber = asynctest.MagicMock()
    ps = PubSub(mock_subscriber)
    ps.connected_users[user_id] = message_queue
    ps.listening = True
    result = await ps.get_message(user_id)
    assert result == "First message"
    assert len(ps.connected_users[user_id]) == 2
    assert ps.connected_users[user_id] == [
        "Second message",
        "Third message",
    ]


@pytest.mark.asyncio
async def test_get_message_no_messages():
    """
    Ensure an empty string is returned if there are no pending messages in the
    message queue associated with the referenced user_id.
    """
    user_id = 1
    mock_subscriber = asynctest.MagicMock()
    ps = PubSub(mock_subscriber)
    ps.connected_users[user_id] = []
    ps.listening = True
    result = await ps.get_message(user_id)
    assert result == ""


@pytest.mark.asyncio
async def test_get_message_no_such_queue():
    """
    Ensure that an empty string is returned if there is no message queue
    associated with the referenced user_id.
    """
    user_id = 1
    mock_subscriber = asynctest.MagicMock()
    ps = PubSub(mock_subscriber)
    ps.listening = True
    result = await ps.get_message(user_id)
    assert result == ""


@pytest.mark.asyncio
async def test_get_message_not_listening():
    """
    Ensure a ValueError is raised if getting messages for a user_id and the
    PubSub instance is no longer listening (usually an indication that there's
    a problem).
    """
    user_id = 1
    mock_subscriber = asynctest.MagicMock()
    ps = PubSub(mock_subscriber)
    ps.listening = False
    with pytest.raises(ValueError):
        await ps.get_message(user_id)