"""
Tests for the logic abstraction layer defining behaviour in the app.

Copyright (C) 2020 Nicholas H.Tollervey
"""
import pytest  # type: ignore
import quart.flask_patch  # type: ignore # noqa
from unittest import mock
from uuid import uuid4
from email.message import EmailMessage
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


def test_init(datastore):
    """
    Ensure the logic object is initialised with a reference to a datastore and
    email related credentials.
    """
    logic = Logic(
        datastore, EMAIL_HOST, EMAIL_PORT, EMAIL_FROM, EMAIL_PASSWORD
    )
    assert logic.datastore == datastore
    assert logic.email_host == EMAIL_HOST
    assert logic.email_port == EMAIL_PORT
    assert logic.email_from == EMAIL_FROM
    assert logic.email_password == EMAIL_PASSWORD


@pytest.mark.asyncio
async def test_verify_credentials(logic):
    """
    Given a valid email address and password, return the object id for the
    user's in-game object.
    """
    object_id = 1234
    logic.datastore.verify_user = mock.AsyncMock(return_value=True)
    logic.datastore.email_to_object_id = mock.AsyncMock(return_value=object_id)
    email = "hello@domain.com"
    password = "password123"
    result = await logic.verify_credentials(email, password)
    assert result == object_id
    logic.datastore.verify_user.assert_called_once_with(email, password)
    logic.datastore.email_to_object_id.assert_called_once_with(email)


@pytest.mark.asyncio
async def test_verify_credentials_bad(logic):
    """
    If the credentials are bad, the resulting object_id is a false-y 0.
    """
    logic.datastore.verify_user = mock.AsyncMock(return_value=False)
    email = "hello@domain.com"
    password = "password123"
    result = await logic.verify_credentials(email, password)
    assert result == 0
    logic.datastore.verify_user.assert_called_once_with(email, password)


@pytest.mark.asyncio
async def test_set_last_seen(logic):
    """
    Cause the last seen flag to be updated in the datastore for the refenced
    user.
    """
    logic.datastore.set_last_seen = mock.AsyncMock()
    user_id = 1234
    await logic.set_last_seen(user_id)
    logic.datastore.set_last_seen.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_check_email(logic):
    """
    Ensure the expected boolean flag is returned from the datastore layer for
    the given email address.
    """
    logic.datastore.user_exists = mock.AsyncMock(return_value=True)
    email = "user@domain.com"
    result = await logic.check_email(email)
    assert result is True
    logic.datastore.user_exists.assert_called_once_with(email)


@pytest.mark.asyncio
async def test_check_token(logic):
    """
    Ensure the expected email address is returned from the datastore layer for
    the given confirmation token.
    """
    email = "user@domain.com"
    token = str(uuid4())
    logic.datastore.token_to_email = mock.AsyncMock(return_value=email)
    result = await logic.check_token(token)
    assert result == email
    logic.datastore.token_to_email.assert_called_once_with(token)


@pytest.mark.asyncio
async def test_create_user(logic):
    """
    A user with the expected email and confirmation token is created via the
    datastore layer. The expected email message is sent to the new user.
    """
    email = "user@domain.com"
    logic.datastore.create_user = mock.AsyncMock()
    logic.send_email = mock.AsyncMock()
    await logic.create_user(email)
    assert logic.datastore.create_user.await_args_list[0][0][0] == email
    message = logic.send_email.await_args_list[0][0][0]
    assert message["From"] == EMAIL_FROM
    assert message["To"] == email
    assert message["Subject"] == "Textsmith registration."


@pytest.mark.asyncio
async def test_confirm_user(logic):
    """
    Given a confirmation token and new password, the user's record is updated
    via the datastore layer. A welcome confirmation email is sent to the new
    user.
    """
    email = "user@domain.com"
    token = str(uuid4())
    password = "password123"

    logic.datastore.confirm_user = mock.AsyncMock(return_value=email)
    logic.send_email = mock.AsyncMock()
    await logic.confirm_user(token, password)
    logic.datastore.confirm_user.assert_called_once_with(token, password)
    message = logic.send_email.await_args_list[0][0][0]
    assert message["From"] == EMAIL_FROM
    assert message["To"] == email
    assert message["Subject"] == "Welcome to Textsmith."


@pytest.mark.asyncio
async def test_send_email(logic):
    """
    Email is sent to the expected server, with the correct settings.
    """
    email = "user@domain.com"
    subject = "This is a test."
    content = "Test content..."
    msg = EmailMessage()
    msg["From"] = logic.email_from
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(content)
    mock_smtp = mock.AsyncMock()
    with mock.patch("textsmith.logic.aiosmtplib.send", mock_smtp):
        await logic.send_email(msg)
        mock_smtp.assert_called_once_with(
            msg,
            hostname=logic.email_host,
            port=logic.email_port,
            username=logic.email_from,
            password=logic.email_password,
            use_tls=True,
        )


@pytest.mark.asyncio
async def test_emit_to_user(logic):
    """
    The referenced message is converted from Markdown into HTML and sent to the
    message queue for the referenced user.
    """
    logic.datastore.redis.publish = mock.AsyncMock()
    await logic.emit_to_user(123, "# Hello world")
    logic.datastore.redis.publish.assert_called_once_with(
        "123", "<h1>Hello world</h1>"
    )


@pytest.mark.asyncio
async def test_emit_to_room(logic):
    """
    The message is sent to all users in the referenced room who are not in the
    exclude list. Non user objects in the room are also ignored.
    """
    user_id = 1
    other_user = 2
    other_object = 3
    room_id = 4
    msg = "Hello, World!"
    logic.emit_to_user = mock.AsyncMock()
    logic.datastore.get_contents = mock.AsyncMock(
        return_value={
            user_id: {"id": user_id, constants.IS_USER: True,},
            other_user: {"id": other_user, constants.IS_USER: True,},
            other_object: {"id": other_object},
        }
    )
    await logic.emit_to_room(room_id, [user_id,], msg)
    logic.datastore.get_contents.assert_called_once_with(room_id)
    logic.emit_to_user.assert_called_once_with(other_user, msg)


@pytest.mark.asyncio
async def test_get_user_context(logic):
    """
    A dictionary containing context objects for simple user interactions is
    returned from the datastore layer.
    """
    user_id = 123
    room_id = 321
    connection_id = str(uuid4())
    message_id = str(uuid4())
    context = {
        "user": {"id": user_id, constants.IS_USER: True,},
        "room": {"id": room_id, constants.IS_ROOM: True,},
    }
    logic.datastore.get_user_context = mock.AsyncMock(return_value=context)
    result = await logic.get_user_context(user_id, connection_id, message_id)
    assert result == context


@pytest.mark.asyncio
async def test_get_script_context(logic):
    """
    A dictionary containing a complete context for the running of a script by
    a particular user, in a particuler room is returned from the datastore
    layer.
    """
    user_id = 123
    room_id = 321
    connection_id = str(uuid4())
    message_id = str(uuid4())
    context = {
        "user": {"id": user_id, constants.IS_USER: True,},
        "room": {"id": room_id, constants.IS_ROOM: True,},
        "exits": [{"id": 234, constants.IS_EXIT: True,}],
        "users": [{"id": 345, constants.IS_USER: True,}],
        "things": [{"id": 456,}],
    }
    logic.datastore.get_script_context = mock.AsyncMock(return_value=context)
    result = await logic.get_script_context(user_id, connection_id, message_id)
    assert result == context


@pytest.mark.asyncio
async def test_get_attribute_value(logic):
    """
    Different object attribute values are returned as the expected string
    representations. If no value for the given attribute exists, a blank string
    is returned. If a string value starts with constants.IS_SCRIPT, then the
    value returned from the script is used.
    """
    obj = {
        "name": "A name",
        "script": constants.IS_SCRIPT + ' (return "Hello")',
        "int": 1234,
        "float": 1.234,
        "bool": True,
        "list": ["This", "is", "a", "list",],
    }
    # String values.
    result = await logic.get_attribute_value(obj, "name")
    assert result == str(obj["name"])
    # String values as scripts. TODO: Complete the implementation.
    result = await logic.get_attribute_value(obj, "script")
    # assert result == "Hello"
    # Integer values.
    result = await logic.get_attribute_value(obj, "int")
    assert result == str(obj["int"])
    # Floating point values.
    result = await logic.get_attribute_value(obj, "float")
    assert result == str(obj["float"])
    # Boolean values.
    result = await logic.get_attribute_value(obj, "bool")
    assert result == str(obj["bool"])
    # List values.
    result = await logic.get_attribute_value(obj, "list")
    assert result == str(obj["list"])
    # Missing attributes result in an empty string.
    result = await logic.get_attribute_value(obj, "missing")
    assert result == ""


def test_match_object_no_identifier(logic):
    """
    If the identifier only contains whitespace, no result is returned.
    """
    identifier = "    "
    user_id = 123
    room_id = 234
    context = {
        "user": {"id": user_id, constants.IS_USER: True},
        "room": {"id": room_id, constants.IS_ROOM: True},
    }
    assert logic.match_object(identifier, context) == ([], "")


def test_match_object_special_aliases(logic):
    """
    If special aliases for the user and room are used, the correct object
    is returned.
    """
    user_id = 123
    room_id = 234
    context = {
        "user": {"id": user_id, constants.IS_USER: True},
        "room": {"id": room_id, constants.IS_ROOM: True},
    }
    for word in constants.USER_ALIASES:
        assert logic.match_object(word, context) == ([context["user"],], word)
    for word in constants.ROOM_ALIASES:
        assert logic.match_object(word, context) == ([context["room"],], word)


def test_match_object_by_object_id(logic):
    """
    Given an object id (e.g. #123), the expected object is returned.
    """
    user_id = 123
    room_id = 321
    exit_id = 234
    other_user_id = 345
    thing_id = 456
    context = {
        "user": {"id": user_id, constants.IS_USER: True,},
        "room": {"id": room_id, constants.IS_ROOM: True,},
        "exits": [{"id": exit_id, constants.IS_EXIT: True,}],
        "users": [{"id": other_user_id, constants.IS_USER: True,}],
        "things": [{"id": thing_id,}],
    }
    assert logic.match_object("#98765", context) == ([], "")
    assert logic.match_object(f"#{user_id}", context) == (
        [context["user"],],
        f"#{user_id}",
    )
    assert logic.match_object(f"#{room_id}", context) == (
        [context["room"],],
        f"#{room_id}",
    )
    assert logic.match_object(f"#{exit_id}", context) == (
        [context["exits"][0],],
        f"#{exit_id}",
    )
    assert logic.match_object(f"#{other_user_id}", context) == (
        [context["users"][0],],
        f"#{other_user_id}",
    )
    assert logic.match_object(f"#{thing_id}", context) == (
        [context["things"][0],],
        f"#{thing_id}",
    )


def test_match_object_by_name_or_alias(logic):
    """
    An object referenced by a free test name from the user is matched by the
    constants.NAME and constants.ALIAS attributes. Multiple objects may be
    returned as a result.
    """
    user_id = 123
    room_id = 321
    exit_id = 234
    other_user_id = 345
    thing_id = 456
    thing2_id = 567
    context = {
        "user": {
            "id": user_id,
            constants.IS_USER: True,
            constants.NAME: "user 1",
        },
        "room": {"id": room_id, constants.IS_ROOM: True,},
        "exits": [{"id": exit_id, constants.IS_EXIT: True,}],
        "users": [
            {
                "id": other_user_id,
                constants.IS_USER: True,
                constants.NAME: "user 2",
                constants.ALIAS: ["another alias"],
            }
        ],
        "things": [
            {
                "id": thing_id,
                constants.NAME: "a thing",
                constants.ALIAS: ["user related", "another alias"],
            },
            {
                "id": thing2_id,
                constants.NAME: "not a thing",
                constants.ALIAS: ["user related", "a thing"],
            },
        ],
    }
    assert logic.match_object("not a match", context) == ([], "")
    assert logic.match_object("user 1", context) == (
        [context["user"],],
        "user 1",
    )
    assert logic.match_object("user 2", context) == (
        [context["users"][0],],
        "user 2",
    )
    assert logic.match_object("another alias", context) == (
        [context["users"][0], context["things"][0],],
        "another alias",
    )
    assert logic.match_object("a thing", context) == (
        [context["things"][0], context["things"][1],],
        "a thing",
    )
    # Match shortest token from start of name or alias.
    assert logic.match_object("user 1 foo bar baz", context) == (
        [context["user"],],
        "user 1",
    )


def test_matches_name_by_name(logic):
    """
    If the given name is the same as the object's constants.NAME then the
    object is a match. Matching is case insensitive.
    """
    obj = {
        "id": 123,
        constants.NAME: "NAme",
    }
    assert logic.matches_name("naME", obj) is True


def test_matches_name_by_alias(logic):
    """
    If the given name is in the object's constants.ALIAS list then the object
    is a match. Matching is case insensitive.
    """
    obj = {
        "id": 123,
        constants.NAME: "name",
        constants.ALIAS: ["alias 1", "ALias 2",],
    }
    assert logic.matches_name("aliAS 2", obj) is True


def test_matches_name_no_match_is_false(logic):
    """
    If the given name is not the same as constants.NAME or in constants.ALIAS
    then it is NOT a match.
    """
    obj = {
        "id": 123,
        constants.NAME: "name",
        constants.ALIAS: ["alias 1", "alias 2",],
    }
    assert logic.matches_name("not a match", obj) is False


@pytest.mark.asyncio
async def test_clarify_object(logic):
    """
    Given a list of multiple matching objects relating to the given message,
    emit a helpful message to the referenced user.
    """
    user_id = 123
    message = "This is a test message."
    match = [
        {"id": 234, constants.NAME: "test", constants.ALIAS: ["foo",]},
        {
            "id": 345,
            constants.NAME: "something",
            constants.ALIAS: ["some", "test"],
        },
        {
            "id": 456,
            constants.NAME: "another",
            constants.ALIAS: ["test", "thing"],
        },
        {"id": 567, constants.NAME: "test"},
    ]
    logic.emit_to_user = mock.AsyncMock()
    await logic.clarify_object(user_id, message, match)
    assert logic.emit_to_user.await_args_list[0][0][0] == user_id
    output = logic.emit_to_user.await_args_list[0][0][1]
    expected = (
        "<pre><code>The following message was ambiguous:\n\n"
        '  "This is a test message."\n\n'
        "Multiple objects matched:\n\n"
        "  test (#234) [foo]\n"
        "  something (#345) [some, test]\n"
        "  another (#456) [test, thing]\n"
        "  test (#567) []\n\n"
        "Please try to be more specific "
        "(an object's ID is unique).</code></pre>"
    )
    assert output == expected


@pytest.mark.asyncio
async def test_no_matching_object(logic):
    """
    If there are no matching objects relating to the given message, emit a
    helpful message to the referenced user.
    """
    user_id = 123
    message = "This is a test message."
    logic.emit_to_user = mock.AsyncMock()
    await logic.no_matching_object(user_id, message)
    assert logic.emit_to_user.await_args_list[0][0][0] == user_id
    output = logic.emit_to_user.await_args_list[0][0][1]
    expected = (
        "<pre><code>The following message didn't match any objects:\n\n"
        '  "This is a test message."\n\n'
        "Please try to be more specific "
        "(an object's ID is unique).</code></pre>"
    )
    assert output == expected
