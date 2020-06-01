"""
Run datastore related tests against a test Redis instance.
"""
import pytest  # type: ignore
import datetime
from .fixtures import datastore  # noqa
from uuid import uuid4


@pytest.mark.asyncio
async def test_set_get_object(datastore):  # noqa
    """
    Objects can be created and retrieved.
    """
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
    """
    Objects can be updated, checked and deleted.
    """
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
    assert 1 == await datastore.delete_attributes(object_id, ["size",])
    objects = await datastore.get_objects([object_id,])
    obj = objects[object_id]
    assert obj == {"id": object_id, "name": "test"}
    assert 0 == await datastore.delete_attributes(object_id, ["foo",])


@pytest.mark.asyncio
async def test_user_sign_up_journey_in_data(datastore):  # noqa
    """
    User related functions for signing up populate the datastore with the
    expected metadata at each step of the sign-up process:

    * A token with associated email address is created.
    * An inactive user cannot have a password set.
    * On email confirmation, the user is able to set a password.
    * A user can update their password.
    * A user can be verified by their email and password.
    * A user can be set as active or inactive.
    * Inactive users fail credential validation.
    """
    confirmation_token = str(uuid4())
    email = "foo@bar.com"
    password = "password123"
    # A token is associated with the new user's email address and the object_id
    # of the game object associated with the player is returned.
    object_id = await datastore.create_user(email, confirmation_token)
    assert object_id > 0
    # We can get the email address from the metadata via the confirmation
    # token.
    new_user_email = await datastore.token_to_email(confirmation_token)
    assert email == new_user_email
    # It's not possible to set a password for an inactive user.
    result = await datastore.set_user_password(email, password)
    assert result is False
    # Confirm the user's email address and new password.
    new_user_email = await datastore.confirm_user(confirmation_token, password)
    assert new_user_email == email
    # Now the user is confirmed (and activated) they can change their password
    # again.
    result = await datastore.set_user_password(email, password)
    assert result is True
    # Now a user can be verified via their email and password credentials.
    result = await datastore.verify_user(email, password)
    assert result is True
    result = await datastore.verify_user(email, "wrong")
    assert result is False
    result = await datastore.verify_user("wrong", password)
    assert result is False
    result = await datastore.verify_user("wrong", "wrong")
    assert result is False
    # It's possible to update a user's "active" status (in this case to
    # inactive).
    await datastore.set_user_active(email, False)
    # Inactive user's cannot be verified.
    result = await datastore.verify_user(email, password)
    assert result is False
    # Re-activated users can be.
    await datastore.set_user_active(email, True)
    result = await datastore.verify_user(email, password)
    assert result is True


@pytest.mark.asyncio
async def test_set_get_last_seen(datastore):  # noqa
    """
    It is possible to set / get a user's last seen timestamp.
    """
    confirmation_token = str(uuid4())
    email = "foo@bar.com"
    object_id = await datastore.create_user(email, confirmation_token)
    # Set the last seen value.
    await datastore.set_last_seen(email)
    # Get the value just set.
    last_seen = await datastore.get_last_seen(object_id)
    # ...which is a datetime object.
    assert isinstance(last_seen, datetime.datetime)
    # None existent user objects result in None.
    last_seen = await datastore.get_last_seen(-1)
    assert last_seen is None
