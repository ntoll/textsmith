"""
Run datastore related tests against a test Redis instance.
"""
import pytest  # type: ignore
from .fixtures import datastore  # noqa
from textsmith.datastore import ObjectType


async def make_object(datastore):  # noqa
    name = "test object"
    description = "This is a test object's description."
    summary = "This is a test object's summary."
    alias = set()
    whitelist = []
    static = False
    typeof = ObjectType.OBJECT
    owner = 666
    object_id = await datastore.add_object(
        name, description, summary, alias, static, typeof, owner, whitelist,
    )
    return object_id


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
    whitelist = [
        1,
        2,
    ]
    static = True
    typeof = ObjectType.OBJECT
    owner = 666
    object_id = await datastore.add_object(
        name,
        description,
        summary,
        alias,
        static,
        typeof,
        owner,
        whitelist,
        foo="bar",
    )
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj["id"] == object_id
    assert obj["name"] == name
    assert obj["description"] == description
    assert obj["summary"] == summary
    assert obj["alias"] == alias
    assert obj["typeof"] == ObjectType.OBJECT.name
    assert obj["static"] == static
    assert obj["owner"] == owner
    assert obj["editors"] == {
        owner,
    }
    assert obj["whitelist"] == {1, 2}
    foo = await datastore.get_annotation(object_id, "foo")
    assert foo == "bar"


@pytest.mark.asyncio
async def test_annotate_object(datastore):  # noqa
    """
    Create, retrieve, update and delete an annotation on an object.
    """
    object_id = await make_object(datastore)
    # Pre-requisit that the annotation doesn't exist.
    with pytest.raises(KeyError):
        await datastore.get_annotation(object_id, "qux")
    # Create
    await datastore.annotate_object(object_id, qux="wibble")
    # Retrieve
    qux = await datastore.get_annotation(object_id, "qux")
    assert qux == "wibble"
    # Update
    await datastore.annotate_object(object_id, qux="bibble")
    qux = await datastore.get_annotation(object_id, "qux")
    assert qux == "bibble"
    # Delete
    await datastore.delete_annotation(object_id, "qux")
    with pytest.raises(KeyError):
        qux = await datastore.get_annotation(object_id, "qux")


@pytest.mark.asyncio
async def test_alias_object(datastore):  # noqa
    """
    Add, read and delete aliases for an object.
    """
    object_id = await make_object(datastore)
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    # Pre-requisit, there are no aliases for the object.
    assert obj["alias"] == set()
    # Add an alias.
    await datastore.add_alias(object_id, "test alias")
    # Check it exists.
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj["alias"] == {
        "test alias",
    }
    # Delete it.
    await datastore.delete_alias(object_id, "test alias")
    # Check it's no longer there.
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj["alias"] == set()
