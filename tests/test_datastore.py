"""
Tests for the datastore abstraction layer (Redis).

Copyright (C) 2020 Nicholas H.Tollervey
"""
import pytest  # type: ignore
import json
import asynctest  # type: ignore
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
    datastore.redis.incr = asynctest.CoroutineMock(return_value=123456)
    datastore.annotate_object = asynctest.CoroutineMock()
    result = await datastore.add_object(name="something")
    assert result == 123456
    datastore.annotate_object.assert_called_once_with(123456, name="something")


@pytest.mark.asyncio
async def test_annotate_object(datastore):
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
