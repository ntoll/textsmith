"""
Run datastore related tests against a test Redis instance.
"""
import pytest  # type: ignore
from .fixtures import datastore  # noqa
from textsmith.datastore import ObjectType


@pytest.mark.asyncio
async def test_set_get_object(datastore):  # noqa
    """
    A new object is successfully created and then retrieved from the REDIS
    data store.
    """
    name = "test object"
    description = "This is a test object's description."
    summary = "This is a test object's summary."
    alias = {
        "test",
        "object",
        "alias",
        "another name",
    }
    typeof = ObjectType.OBJECT
    owner = 666
    object_id = await datastore.add_object(
        name, description, summary, alias, typeof, owner, foo="bar"
    )
    attributes = await datastore.get_object(object_id)
    assert attributes["name"] == name
    assert attributes["description"] == description
    assert attributes["summary"] == summary
    assert attributes["alias"] == alias
    assert attributes["typeof"] == ObjectType.OBJECT.name
    assert attributes["owner"] == owner
    assert attributes["editors"] == {
        str(owner),
    }
    foo = await datastore.get_annotation(object_id, "foo")
    assert foo == "bar"
    with pytest.raises(KeyError):
        await datastore.get_annotation(object_id, "qux")
    await datastore.annotate_object(object_id, qux="wibble")
    qux = await datastore.get_annotation(object_id, "qux")
    assert qux == "wibble"
