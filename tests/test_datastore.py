"""
Tests for the datastore abstraction layer (Redis).

Copyright (C) 2020 Nicholas H.Tollervey
"""
import pytest  # type: ignore
import json
import asyncio
import asynctest  # type: ignore
import uuid
from unittest import mock
from textsmith.datastore import DataStore


@pytest.fixture
def datastore(mocker):
    return DataStore(mocker.MagicMock())


def test_init(mocker):
    """
    Ensure the DataStore object is initialised with a reference to a Redis
    pool.
    """
    mock_pool = mocker.MagicMock()
    datastore = DataStore(mock_pool)
    assert datastore.redis == mock_pool


def test_user_key(datastore):
    """
    The key for user metadata should match a certain pattern:
    "user:name@email.com".
    """
    assert datastore.user_key("foo@bar.com") == "user:foo@bar.com"


def test_token_key(datastore):
    """
    The key for confirmation token metadata should match a certain pattern:
    "token:1bdc5f9a-f86d-4b5c-a697-e5f845ca3fea"
    """
    assert (
        datastore.token_key("1bdc5f9a-f86d-4b5c-a697-e5f845ca3fea")
        == "token:1bdc5f9a-f86d-4b5c-a697-e5f845ca3fea"
    )


def test_hash_and_check_password(datastore):
    """
    Ensure hashing and checking of passwords works.
    """
    password = "topsecret"
    hashed_password = datastore.hash_password(password)
    assert datastore.verify_password(hashed_password, password) is True
    assert datastore.verify_password(hashed_password, "fail") is False


@pytest.mark.asyncio
async def test_add_object(datastore):
    """
    It is possible to add a new object with arbitrary attributes to the
    datastore, and immediately retrieve it.
    """
    datastore.redis.incr = asynctest.CoroutineMock(return_value=123456)
    datastore.annotate_object = asynctest.CoroutineMock()
    result = await datastore.add_object(name="something")
    assert result == 123456
    datastore.annotate_object.assert_called_once_with(123456, name="something")


@pytest.mark.asyncio
async def test_annotate_object(datastore):
    """
    It's possible to add arbitrarily named attributes to an object.
    """
    mock_transaction = asynctest.CoroutineMock()
    mock_transaction.hmset = asynctest.CoroutineMock()
    mock_transaction.exec = asynctest.CoroutineMock()
    datastore.redis.multi = asynctest.CoroutineMock(
        return_value=mock_transaction
    )
    object_id = 12345
    await datastore.annotate_object(object_id, name="something")
    mock_transaction.hmset.assert_called_once_with(
        str(object_id), {"name": json.dumps("something")}
    )
    mock_transaction.exec.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_objects(datastore):
    """
    A list of object IDs returns a dictionary of Python dictionaries
    deserialised from Redis. The key in the dictionary is the id of the object.
    The associated dictionary contains the attributes and associated values.
    """
    object1_name = "name1"
    object1_list = [1, 2.345, "six", False]
    object2_name = "name2"
    object2_list = [2, 3.456, "seven", True]
    object3_name = "name3"
    object3_list = [3, 4.567, "eight", False]

    mock_result1 = asyncio.get_event_loop().create_future()
    mock_result2 = asyncio.get_event_loop().create_future()
    mock_result3 = asyncio.get_event_loop().create_future()
    mock_result1.set_result(
        {"name": json.dumps(object1_name), "list": json.dumps(object1_list)}
    )
    mock_result2.set_result(
        {"name": json.dumps(object2_name), "list": json.dumps(object2_list)}
    )
    mock_result3.set_result(
        {"name": json.dumps(object3_name), "list": json.dumps(object3_list)}
    )

    mock_transaction = asynctest.CoroutineMock()
    mock_transaction.hgetall_asdict = mock.AsyncMock()

    def side_effect(*args, **kwargs):
        results = {"1": mock_result1, "2": mock_result2, "3": mock_result3}
        return results[args[0]]

    mock_transaction.hgetall_asdict.side_effect = side_effect

    mock_transaction.exec = asynctest.CoroutineMock()
    datastore.redis.multi = asynctest.CoroutineMock(
        return_value=mock_transaction
    )
    result = await datastore.get_objects([1, 2, 3])
    assert result == {
        1: {"id": 1, "name": object1_name, "list": object1_list},
        2: {"id": 2, "name": object2_name, "list": object2_list},
        3: {"id": 3, "name": object3_name, "list": object3_list},
    }


@pytest.mark.asyncio
async def test_get_attribute_that_does_not_exist(datastore):
    """
    If the referenced attribute on the object doesn't exist, then the method
    should raise a KeyError.
    """
    datastore.redis.hexists = asynctest.CoroutineMock(return_value=False)
    with pytest.raises(KeyError):
        await datastore.get_attribute(1, "foo")


@pytest.mark.asyncio
async def test_get_attribute(datastore):
    """
    The attribute on the referenced object is returned as a value of the
    correct native Python type.
    """
    datastore.redis.hexists = asynctest.CoroutineMock(return_value=True)
    datastore.redis.hget = asynctest.CoroutineMock(
        return_value=json.dumps("hello")
    )
    result = await datastore.get_attribute(1, "foo")
    assert result == "hello"
    datastore.redis.hget.assert_called_once_with("1", "foo")


@pytest.mark.asyncio
async def test_delete_attributes(datastore):
    """
    Given a list of attributes on a referenced object, returns the number of
    attributes deleted from Redis.
    """
    mock_transaction = asynctest.CoroutineMock()
    mock_transaction.exec = asynctest.CoroutineMock()
    datastore.redis.multi = asynctest.CoroutineMock(
        return_value=mock_transaction
    )
    object_id = 12345
    attributes = [
        "foo",
        "bar",
        "baz",
    ]
    mock_result1 = asyncio.get_event_loop().create_future()
    mock_result1.set_result(len(attributes))
    mock_transaction.hdel = mock.AsyncMock()

    def side_effect(*args, **kwargs):
        return mock_result1

    mock_transaction.hdel.side_effect = side_effect
    result = await datastore.delete_attributes(object_id, attributes)
    mock_transaction.hdel.assert_called_once_with(str(object_id), attributes)
    mock_transaction.exec.assert_called_once_with()
    assert result == len(attributes)


@pytest.mark.asyncio
async def test_user_exists(datastore):
    """
    The existence of the expected user tag is returned as a boolean.
    """
    datastore.redis.exists = asynctest.CoroutineMock(return_value=True)
    result = await datastore.user_exists("foo@bar.com")
    assert result is True
    datastore.redis.exists.assert_called_once_with(
        datastore.user_key("foo@bar.com")
    )


@pytest.mark.asyncio
async def test_create_user(datastore):
    """
    Creating a user from an email address and token involves the expected
    metadata being added to the database, the confirmation token is linked to
    the email address and the user's in-world object is created.
    """
    new_user_id = 123
    datastore.add_object = asynctest.CoroutineMock(return_value=new_user_id)
    mock_transaction = asynctest.CoroutineMock()
    mock_transaction.hmset = asynctest.CoroutineMock()
    mock_transaction.set = asynctest.CoroutineMock()
    mock_transaction.exec = asynctest.CoroutineMock()
    datastore.redis.multi = asynctest.CoroutineMock(
        return_value=mock_transaction
    )
    email = "foo@bar.com"
    confirmation_token = str(uuid.uuid4())
    result = await datastore.create_user(email, confirmation_token)
    assert result == new_user_id
    mock_transaction.hmset.assert_called_once_with(
        datastore.user_key(email),
        {
            "email": json.dumps(email),
            "active": json.dumps(False),
            "object_id": json.dumps(new_user_id),
        },
    )
    mock_transaction.set.assert_called_once_with(
        datastore.token_key(confirmation_token), email
    )
    mock_transaction.exec.assert_called_once_with()


@pytest.mark.asyncio
async def test_token_to_email(datastore):
    """
    If there's no email for the referenced token, None is returned. Otherwise,
    the email address referenced by the token is returned.
    """
    datastore.redis.get = asynctest.CoroutineMock(return_value=None)
    result = await datastore.token_to_email("token")
    assert result is None
    datastore.redis.get = asynctest.CoroutineMock(return_value="foo@bar.com")
    result = await datastore.token_to_email("token")
    assert result == "foo@bar.com"


@pytest.mark.asyncio
async def test_set_user_password(datastore):
    """
    Ensure the user referenced by the passed in email address has their
    password reset to that which is passed in.
    """
    datastore.redis.hget = asynctest.CoroutineMock(
        return_value=json.dumps(True)
    )
    datastore.redis.hmset = asynctest.CoroutineMock(return_value=None)
    datastore.hash_password = mock.MagicMock(return_value="hashed")
    email = "foo@bar.com"
    await datastore.set_user_password(email, "password")
    datastore.hash_password.assert_called_once_with("password")
    datastore.redis.hmset.assert_called_once_with(
        datastore.user_key(email), {"password": json.dumps("hashed")}
    )


@pytest.mark.asyncio
async def test_set_user_password_not_on_unknown_user(datastore):
    """
    No password will be set if the user's email address is not in the
    database.
    """
    datastore.redis.hget = asynctest.CoroutineMock(return_value=None)
    datastore.redis.hmset = asynctest.CoroutineMock(return_value=None)
    datastore.hash_password = mock.MagicMock(return_value="hashed")
    email = "foo@bar.com"
    await datastore.set_user_password(email, "password")
    assert datastore.redis.hmset.call_count == 0


@pytest.mark.asyncio
async def test_set_user_password_not_on_inactive_user(datastore):
    """
    Cannot change the password on inactive users.
    """
    datastore.redis.hget = asynctest.CoroutineMock(
        return_value=json.dumps(False)
    )
    datastore.redis.hmset = asynctest.CoroutineMock(return_value=None)
    datastore.hash_password = mock.MagicMock(return_value="hashed")
    email = "foo@bar.com"
    await datastore.set_user_password(email, "password")
    assert datastore.redis.hmset.call_count == 0


@pytest.mark.asyncio
async def test_confirm_user(datastore):
    """
    Given a valid user token, the referenced password is set against the
    email address of the user for whom the token was created.
    """
    email = "foo@bar.com"
    confirmation_token = str(uuid.uuid4())
    password = "password123"
    datastore.token_to_email = asynctest.CoroutineMock(return_value=email)
    datastore.set_user_active = asynctest.CoroutineMock()
    datastore.set_user_password = asynctest.CoroutineMock()
    datastore.redis.delete = asynctest.CoroutineMock()
    await datastore.confirm_user(confirmation_token, password)
    datastore.token_to_email.assert_called_once_with(confirmation_token)
    datastore.set_user_active.assert_called_once_with(email, True)
    datastore.set_user_password.assert_called_once_with(email, password)
    datastore.redis.delete.assert_called_once_with(
        [datastore.token_key(confirmation_token)]
    )


@pytest.mark.asyncio
async def test_confirm_user_missing_token(datastore):
    """
    If the referenced token is missing, a ValueError is raised.
    """
    confirmation_token = str(uuid.uuid4())
    password = "password123"
    datastore.token_to_email = asynctest.CoroutineMock(return_value=None)
    with pytest.raises(ValueError):
        await datastore.confirm_user(confirmation_token, password)


@pytest.mark.asyncio
async def test_verify_user(datastore):
    """
    Given an email address and password, the password is checked against the
    hashed value found in the datastore.
    """
    datastore.redis.hexists = asynctest.CoroutineMock(return_value=True)
    datastore.redis.hgetall_asdict = asynctest.CoroutineMock(
        return_value={
            "password": json.dumps(datastore.hash_password("password123")),
            "active": json.dumps(True),
        }
    )
    result = await datastore.verify_user("foo@bar.com", "password123")
    assert result is True


@pytest.mark.asyncio
async def test_verify_user_unknown(datastore):
    """
    Unknown email address returns False.
    """
    datastore.redis.hexists = asynctest.CoroutineMock(return_value=True)
    datastore.redis.hgetall_asdict = asynctest.CoroutineMock(return_value={})
    result = await datastore.verify_user("foo@bar.com", "password123")
    assert result is False


@pytest.mark.asyncio
async def test_verify_user_inactive(datastore):
    """
    Inactive user identified by email address returns False.
    """
    datastore.redis.hexists = asynctest.CoroutineMock(return_value=True)
    datastore.redis.hgetall_asdict = asynctest.CoroutineMock(
        return_value={
            "password": json.dumps(datastore.hash_password("password123")),
            "active": json.dumps(False),
        }
    )
    result = await datastore.verify_user("foo@bar.com", "password123")
    assert result is False


@pytest.mark.asyncio
async def test_set_user_active(datastore):
    """
    A boolean flag to indicate the user's active status is set when this method
    is called.
    """
    email = "foo@bar.com"
    key = datastore.user_key(email)
    datastore.redis.hmset = asynctest.CoroutineMock()
    await datastore.set_user_active(email)
    datastore.redis.hmset.assert_called_once_with(
        key, {"active": json.dumps(True)}
    )
    datastore.redis.hmset.reset_mock()
    await datastore.set_user_active(email, False)
    datastore.redis.hmset.assert_called_once_with(
        key, {"active": json.dumps(False)}
    )
