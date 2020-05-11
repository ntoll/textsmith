"""
Tests for the datastore abstraction layer (Redis).

Copyright (C) 2020 Nicholas H.Tollervey
"""
import pytest  # type: ignore
import json
import asyncio
import asynctest  # type: ignore
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
async def test_delete_attributeis(datastore):
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
