"""
Run pubsub related tests against a test Redis instance.
"""
import asyncio
import pytest  # type: ignore
from .fixtures import pool, pubsub  # noqa


@pytest.mark.asyncio
async def test_subscribe_unsubscribe(pool, pubsub, mocker):  # noqa
    """
    Ensure that subscription results in messages published for the referenced
    object ID can be retrieved. Once unsubscribed, no messages for the
    referenced object ID are retrieved.
    """
    # Subscribe to messages for player with object ID of 1.
    await pubsub.subscribe(1, "connectionid")
    # Publish a message for the player with object ID of 1.
    await pool.publish("1", "Hello player 1")
    await asyncio.sleep(0.1)
    # Get the next message for the player with object ID of 1.
    msg = await pubsub.get_message(1)
    assert msg == "Hello player 1"
    # Whilst subscribed, if there are no further messages, just return an
    # empty string.
    msg = await pubsub.get_message(1)
    assert msg == ""
    # Publish a message for the player with object ID of 1.
    await pool.publish("1", "Hello again player 1")
    await asyncio.sleep(0.1)
    # Unsubscribing will cause undelivered messages to be logged.
    mock_logger = mocker.patch("textsmith.pubsub.logger")
    await pubsub.unsubscribe(1, "connectionid")
    assert mock_logger.msg.call_count == 2
    assert mock_logger.msg.call_args_list[0][0][0] == "Unsubscribe."
    assert mock_logger.msg.call_args_list[1][0][0] == "Undelivered messages."
    # Publish a message for the player with object ID of 1.
    await pool.publish("1", "Final hello player 1")
    # While unsubscribed, just return an empty string when polling for the
    # next message, since any published messages (see line above) should not
    # be received.
    msg = await pubsub.get_message(1)
    assert msg == ""
    # Stop listening.
    await pubsub.stop()
