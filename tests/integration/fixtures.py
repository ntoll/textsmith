"""
Fixtures needed for the integration tests.
"""
import asyncio_redis  # type: ignore
import pytest  # type: ignore
from textsmith.datastore import DataStore
from textsmith.pubsub import PubSub


@pytest.fixture
async def pubsub():
    """
    Create a PubSub instance for messaging purposes.
    """
    pool = await asyncio_redis.Pool.create(
        host="localhost", port=6379, db=1, poolsize=10
    )
    subscriber = await pool.start_subscribe()
    pubsub = PubSub(subscriber)
    yield pubsub
    pool.close()


@pytest.fixture
async def pool(event_loop):
    """
    Create a test Redis database and connection pool. Once finished, flush the
    test Redis database of all items.
    """
    pool = await asyncio_redis.Pool.create(
        host="localhost", port=6379, db=1, poolsize=10
    )
    # Delete all items from database.
    pool.flushdb()
    yield pool
    pool.close()


@pytest.fixture
async def datastore():
    """
    Create a test Redis database and connection pool. Yield a DataStore object
    and once finished, flush the test Redis database of all items.
    """
    pool = await asyncio_redis.Pool.create(
        host="localhost", port=6379, db=1, poolsize=10
    )
    # Delete all items from database.
    pool.flushdb()
    ds = DataStore(pool)
    yield ds
    pool.close()
