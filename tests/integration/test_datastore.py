"""
Run datastore related tests against a test Redis instance.
"""
import pytest  # type: ignore
from .fixtures import datastore  # noqa


@pytest.mark.asyncio
async def test_set_get_object(datastore):  # noqa
    name = "test"
    number = 123
    float_number = 1.23456
    boolean = False
    list_stuff = [1, 2.345, "six", True]
    object_id = await datastore.add_object(
        name=name,
        number=number,
        float_number=float_number,
        boolean=boolean,
        list_stuff=list_stuff,
    )
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj["id"] == object_id
    assert obj["name"] == name
    assert obj["number"] == number
    assert obj["float_number"] == float_number
    assert obj["boolean"] == boolean
    assert obj["list_stuff"] == list_stuff


@pytest.mark.asyncio
async def test_update_delete_object(datastore):  # noqa
    object_id = await datastore.add_object(name="test")
    # Ensure the object is in a default state.
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj == {"id": object_id, "name": "test"}
    # Update the object with a new field.
    await datastore.annotate_object(object_id, size=42)
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj == {"id": object_id, "name": "test", "size": 42}
    # Update an existing field.
    await datastore.annotate_object(object_id, size=3.141)
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj == {"id": object_id, "name": "test", "size": 3.141}
    # Get the value of a specific field.
    size = await datastore.get_attribute(object_id, "size")
    assert size == 3.141
    # Getting an unknown attribute results in a KeyError.
    with pytest.raises(KeyError):
        await datastore.get_attribute(object_id, "foo")
    # Delete the attribute.
    await datastore.delete_attribute(object_id, "size")
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj == {"id": object_id, "name": "test"}
    # Deleting an unknown attribute results in a KeyError.
    with pytest.raises(KeyError):
        await datastore.delete_attribute(object_id, "foo")
