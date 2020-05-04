"""
Tests for the datastore abstraction layer (Redis).

Copyright (C) 2020 Nicholas H.Tollervey
"""
# import pytest  # type: ignore
# import asynctest  # type: ignore
from unittest import mock
from textsmith.datastore import DataStore


def test_init():
    """
    Ensure the DataStore object is initialised with a reference to a Redis
    pool.
    """
    mock_pool = mock.MagicMock()
    ds = DataStore(mock_pool)
    assert ds.redis == mock_pool


def test_key_for():
    """
    Check the key schema is as expected: object_id:namespace:attribute.
    """
    pass
