"""
Tests for the core verbs built into the system that define the fundamental
behaviours available to users.

Copyright (C) 2020 Nicholas H.Tollervey
"""
import pytest  # type: ignore
import quart.flask_patch  # type: ignore # noqa
from unittest import mock
from uuid import uuid4
from textsmith.verbs import Verbs, UnknownVerb
from textsmith.logic import Logic
from textsmith.datastore import DataStore
from textsmith import constants


EMAIL_HOST = "email.host.com"
EMAIL_PORT = 1234
EMAIL_FROM = "hello@textsmith.com"
EMAIL_PASSWORD = "secret123"


@pytest.fixture
def datastore(mocker):
    return DataStore(mocker.MagicMock())


@pytest.fixture
def logic(datastore):
    return Logic(datastore, EMAIL_HOST, EMAIL_PORT, EMAIL_FROM, EMAIL_PASSWORD)


@pytest.fixture
def verbs(logic):
    return Verbs(logic)


@pytest.fixture
def user_id():
    return 1234


@pytest.fixture
def room_id():
    return 5678


@pytest.fixture
def connection_id():
    return str(uuid4())


@pytest.fixture
def message_id():
    return str(uuid4())


@pytest.fixture
def message():
    return "Hello, World!"


def test_init(logic):
    """
    Ensure the Verbs instance is instantiated with the expected attributes.
    """
    verbs = Verbs(logic)
    assert verbs.logic == logic
    assert isinstance(verbs.languages, list)
    assert isinstance(verbs._VERBS, dict)


@pytest.mark.asyncio
async def test_call(user_id, connection_id, message_id, message):
    """
    Check that the verbs instance is callable in the expected manner.
    """
    mock_say = mock.AsyncMock()
    with mock.patch("textsmith.verbs.Verbs._say", mock_say):
        verbs = Verbs(logic)
        # Defaults to English
        await verbs(user_id, connection_id, message_id, "say", message)
        verbs._say.assert_called_once_with(
            user_id, connection_id, message_id, message
        )
        verbs._say.reset_mock()
        # An existing locale is selected for use.
        await verbs(user_id, connection_id, message_id, "say", message, "en")
        verbs._say.assert_called_once_with(
            user_id, connection_id, message_id, message
        )
        # No such verb raises a NoMatchFound exception.
        with pytest.raises(UnknownVerb):
            await verbs(user_id, connection_id, message_id, "fooooo", message)


@pytest.mark.asyncio
async def test_say(
    verbs, user_id, room_id, connection_id, message_id, message
):
    """
    A message is said in the current location. This results in the expected
    messages being put onto the expected message queues.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._say(user_id, connection_id, message_id, message)
    verbs.logic.emit_to_user.assert_called_once_with(
        user_id, f'> You say, "*{message}*".'
    )
    verbs.logic.emit_to_room.assert_called_once_with(
        room_id, [user_id,], f'> {username} says, "*{message}*".'
    )


@pytest.mark.asyncio
async def test_say_whitespace(
    verbs, user_id, room_id, connection_id, message_id
):
    """
    Messages containing just whitespace are ignored.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._say(user_id, connection_id, message_id, "      ")
    assert verbs.logic.emit_to_user.call_count == 0
    assert verbs.logic.emit_to_room.call_count == 0


@pytest.mark.asyncio
async def test_shout(
    verbs, user_id, room_id, connection_id, message_id, message
):
    """
    A message is shouted in the current location. This results in the expected
    messages being put onto the expected message queues.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._shout(user_id, connection_id, message_id, message)
    verbs.logic.emit_to_user.assert_called_once_with(
        user_id, f'> You shout, "**{message}**".'
    )
    verbs.logic.emit_to_room.assert_called_once_with(
        room_id, [user_id,], f'> {username} shouts, "**{message}**".'
    )


@pytest.mark.asyncio
async def test_shout_whitespace(
    verbs, user_id, room_id, connection_id, message_id
):
    """
    Messages containing just whitespace are ignored.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._shout(user_id, connection_id, message_id, "      ")
    assert verbs.logic.emit_to_user.call_count == 0
    assert verbs.logic.emit_to_room.call_count == 0


@pytest.mark.asyncio
async def test_emote(
    verbs, user_id, room_id, connection_id, message_id, message
):
    """
    A message is emoted in the current location. This results in the expected
    messages being put onto the expected message queues.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._emote(user_id, connection_id, message_id, message)
    expected = f"{username} {message}"
    verbs.logic.emit_to_user.assert_called_once_with(user_id, expected)
    verbs.logic.emit_to_room.assert_called_once_with(
        room_id, [user_id,], expected
    )


@pytest.mark.asyncio
async def test_emote_whitespace(
    verbs, user_id, room_id, connection_id, message_id
):
    """
    Messages containing just whitespace are ignored.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._emote(user_id, connection_id, message_id, "      ")
    assert verbs.logic.emit_to_user.call_count == 0
    assert verbs.logic.emit_to_room.call_count == 0


@pytest.mark.asyncio
async def test_tell(verbs, user_id, room_id, connection_id, message_id):
    """
    As message is (publicly) told to a specific user in the current context.
    """
    username = "a user"
    verbs.logic.get_script_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {
                "id": room_id,
                constants.IS_ROOM: True,
                constants.NAME: "a room",
            },
            "exits": [
                {
                    "id": 2222,
                    constants.IS_EXIT: True,
                    constants.NAME: "A path",
                    constants.ALIAS: ["path",],
                },
            ],
            "users": [
                {
                    "id": 3333,
                    constants.IS_USER: True,
                    constants.NAME: "Fred",
                    constants.ALIAS: ["Freddy", "Freddo",],
                },
                {
                    "id": 4444,
                    constants.IS_USER: True,
                    constants.NAME: "Alice",
                    constants.ALIAS: ["Al", "Ali",],
                },
            ],
            "things": [],
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._tell(user_id, connection_id, message_id, "ali Hello, world!")
    assert verbs.logic.emit_to_user.call_count == 2
    assert verbs.logic.emit_to_room.call_count == 1
    assert verbs.logic.emit_to_user.await_args_list[0][0][0] == user_id
    user_msg = '> You say to Alice, "*Hello, world!*".'
    assert verbs.logic.emit_to_user.await_args_list[0][0][1] == user_msg
    assert verbs.logic.emit_to_user.await_args_list[1][0][0] == 4444
    recipient_msg = '> a user says, "*Hello, world!*" to you.'
    assert verbs.logic.emit_to_user.await_args_list[1][0][1] == recipient_msg
    assert verbs.logic.emit_to_room.await_args_list[0][0][0] == room_id
    assert verbs.logic.emit_to_room.await_args_list[0][0][1] == [
        user_id,
        4444,
    ]
    room_msg = '> a user says to Alice, "*Hello, world!*".'
    assert verbs.logic.emit_to_room.await_args_list[0][0][2] == room_msg


@pytest.mark.asyncio
async def test_tell_whitespace(
    verbs, user_id, room_id, connection_id, message_id
):
    """
    Messages containing just whitespace are ignored.
    """
    username = "a user"
    verbs.logic.get_user_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {"id": room_id, constants.IS_ROOM: True,},
        }
    )
    verbs.logic.emit_to_user = mock.AsyncMock()
    verbs.logic.emit_to_room = mock.AsyncMock()
    await verbs._tell(user_id, connection_id, message_id, "      ")
    assert verbs.logic.emit_to_user.call_count == 0
    assert verbs.logic.emit_to_room.call_count == 0


@pytest.mark.asyncio
async def test_tell_too_many_matches(
    verbs, user_id, room_id, connection_id, message_id
):
    """
    As message is (publicly) told to a specific user in the current context.
    """
    username = "a user"
    verbs.logic.get_script_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {
                "id": room_id,
                constants.IS_ROOM: True,
                constants.NAME: "a room",
            },
            "exits": [
                {
                    "id": 2222,
                    constants.IS_EXIT: True,
                    constants.NAME: "A path",
                    constants.ALIAS: ["path",],
                },
            ],
            "users": [
                {
                    "id": 3333,
                    constants.IS_USER: True,
                    constants.NAME: "Fred",
                    constants.ALIAS: ["Freddy", "Freddo", "user"],
                },
                {
                    "id": 4444,
                    constants.IS_USER: True,
                    constants.NAME: "Alice",
                    constants.ALIAS: ["Al", "Ali", "user",],
                },
            ],
            "things": [],
        }
    )
    verbs.logic.clarify_object = mock.AsyncMock()
    message = "user Hello, world!"
    await verbs._tell(user_id, connection_id, message_id, message)
    verbs.logic.clarify_object.assert_called_once_with(
        user_id,
        "@" + message,
        [
            {
                "id": 3333,
                constants.IS_USER: True,
                constants.NAME: "Fred",
                constants.ALIAS: ["Freddy", "Freddo", "user"],
            },
            {
                "id": 4444,
                constants.IS_USER: True,
                constants.NAME: "Alice",
                constants.ALIAS: ["Al", "Ali", "user",],
            },
        ],
    )


@pytest.mark.asyncio
async def test_tell_no_matches(
    verbs, user_id, room_id, connection_id, message_id
):
    """
    As message is (publicly) told to a specific user in the current context.
    """
    username = "a user"
    verbs.logic.get_script_context = mock.AsyncMock(
        return_value={
            "user": {
                "id": user_id,
                constants.IS_USER: True,
                constants.NAME: username,
            },
            "room": {
                "id": room_id,
                constants.IS_ROOM: True,
                constants.NAME: "a room",
            },
            "exits": [
                {
                    "id": 2222,
                    constants.IS_EXIT: True,
                    constants.NAME: "A path",
                    constants.ALIAS: ["path",],
                },
            ],
            "users": [
                {
                    "id": 3333,
                    constants.IS_USER: True,
                    constants.NAME: "Fred",
                    constants.ALIAS: ["Freddy", "Freddo", "user"],
                },
                {
                    "id": 4444,
                    constants.IS_USER: True,
                    constants.NAME: "Alice",
                    constants.ALIAS: ["Al", "Ali", "user",],
                },
            ],
            "things": [],
        }
    )
    verbs.logic.no_matching_object = mock.AsyncMock()
    message = "foo Hello, world!"
    await verbs._tell(user_id, connection_id, message_id, message)
    verbs.logic.no_matching_object.assert_called_once_with(
        user_id, "@" + message
    )
