"""
Run datastore related tests against a test Redis instance.
"""
import pytest  # type: ignore
import datetime
from .fixtures import datastore  # noqa
from textsmith import constants
from uuid import uuid4


@pytest.mark.asyncio
async def test_set_get_delete_object(datastore):  # noqa
    """
    Objects can be created, retrieved and deleted.
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
    await datastore.delete_object(object_id)
    objects = await datastore.get_objects([object_id,])
    assert len(objects) == 0


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
async def test_user_journey_in_data(datastore):  # noqa
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

    When a user is deleted, they are "soft" deleted such that:

    * The user is set as inactive.
    * The user's in game object is not located anywhere (they're in limbo).
    """
    confirmation_token = str(uuid4())
    email = "foo@bar.com"
    password = "password123"
    # A token is associated with the new user's email address and the object_id
    # of the game object associated with the player is returned.
    object_id = await datastore.create_user(email, confirmation_token)
    assert object_id > 0
    # The object representing the user in the game is marked as a user's
    # object.
    user_obj = await datastore.get_objects([object_id,])
    user_obj = user_obj[object_id]
    assert user_obj[constants.IS_USER] is True
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
    # It's possible to get the object id of the in-game object representing the
    # user from the user's email address.
    result = await datastore.email_to_object_id(email)
    assert result == object_id
    # Place a user in a new location (a pre-requisite for checking user
    # deletion).
    room_id = await datastore.add_object(name="room")
    await datastore.set_container(object_id, room_id)
    # Deletion of object means they're disabled and in no location.
    await datastore.delete_user(email)
    # Inactive user's cannot be verified.
    result = await datastore.verify_user(email, password)
    assert result is False
    # The user has no location.
    user_location = await datastore.get_location(object_id)
    assert user_location is None


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


@pytest.mark.asyncio
async def test_set_get_location(datastore):  # noqa
    """
    It is possible to set objects as being contained in others. As a result we
    can discover which objects are inside others, and which object may contain
    another.
    """
    room_id = await datastore.add_object(name="room")
    user_id = await datastore.add_object(name="user")
    item_id = await datastore.add_object(name="item")

    # The item is carried by the user.
    await datastore.set_container(item_id, user_id)
    # The user is in the room.
    await datastore.set_container(user_id, room_id)
    # Check this is the case.
    room_location = await datastore.get_location(room_id)
    assert room_location is None  # The room isn't contained within anything.
    user_location = await datastore.get_location(user_id)
    assert user_location == room_id  # The user is in the room.
    item_location = await datastore.get_location(item_id)
    assert item_location == user_id  # The item is carried by the user.
    # The room reports the user is in it.
    room_contents = await datastore.get_contents(room_id)
    assert len(room_contents) == 1
    assert user_id in room_contents
    assert room_contents[user_id]["name"] == "user"
    # The user reports it is carrying the item.
    user_contents = await datastore.get_contents(user_id)
    assert len(user_contents) == 1
    assert item_id in user_contents
    assert user_contents[item_id]["name"] == "item"
    # The item reports it doesn't contain anything.
    item_contents = await datastore.get_contents(item_id)
    assert item_contents == {}
    # The user drops the item into the room.
    await datastore.set_container(item_id, room_id)
    # The room contains two things: the user and the item.
    room_contents = await datastore.get_contents(room_id)
    assert len(room_contents) == 2
    assert user_id in room_contents
    assert room_contents[user_id]["name"] == "user"
    assert item_id in room_contents
    assert room_contents[item_id]["name"] == "item"
    # The user reports it isn't carrying anything.
    user_contents = await datastore.get_contents(user_id)
    assert user_contents == {}
    # The item reports its location as the room.
    item_location = await datastore.get_location(item_id)
    assert item_location == room_id
    # Setting a location to < 0 means the thing is not contained by anything.
    await datastore.set_container(item_id, -1)
    # Now the room contains just one thing again.
    room_contents = await datastore.get_contents(room_id)
    assert len(room_contents) == 1
    assert user_id in room_contents
    assert room_contents[user_id]["name"] == "user"
    # The item reports it isn't contained anywhere.
    item_location = await datastore.get_location(item_id)
    assert item_location is None


@pytest.mark.asyncio
async def test_contexts(datastore):  # noqa
    """
    The expected objects are placed into the right values in a dictionary
    representing the context in which a script is run.
    """
    room_data = {
        constants.NAME: "room",
        constants.DESCRIPTION: "A test room.",
        constants.IS_ROOM: True,
    }
    room_id = await datastore.add_object(**room_data)
    exit_data = {
        constants.NAME: "exit",
        constants.DESCRIPTION: "A test exit from the room.",
        constants.IS_EXIT: True,
    }
    exit_id = await datastore.add_object(**exit_data)
    user_data = {
        constants.NAME: "user",
        constants.DESCRIPTION: "A test user.",
        constants.IS_USER: True,
    }
    user_id = await datastore.add_object(**user_data)
    other_user_data = {
        constants.NAME: "other_user",
        constants.DESCRIPTION: "Another user in the game.",
        constants.IS_USER: True,
    }
    other_user_id = await datastore.add_object(**other_user_data)
    item_data = {
        constants.NAME: "item",
        constants.DESCRIPTION: "A test object.",
    }
    item_id = await datastore.add_object(**item_data)

    # The exit is in the room.
    await datastore.set_container(exit_id, room_id)
    # The item is in the room.
    await datastore.set_container(item_id, room_id)
    # The current user is in the room.
    await datastore.set_container(user_id, room_id)
    # The other user is in the room.
    await datastore.set_container(other_user_id, room_id)
    # Check the context as a result of the above settings.
    context = await datastore.get_script_context(user_id)
    # The current user is in the context.
    assert context["user"][constants.NAME] == "user"
    assert context["user"][constants.DESCRIPTION] == "A test user."
    assert context["user"]["id"] == user_id
    # The room containing the user is in the context.
    assert context["room"][constants.NAME] == "room"
    assert context["room"][constants.DESCRIPTION] == "A test room."
    assert context["room"]["id"] == room_id
    # The exit object is in the exits list.
    assert len(context["exits"]) == 1
    exit = context["exits"][0]
    assert exit[constants.NAME] == "exit"
    assert exit[constants.DESCRIPTION] == "A test exit from the room."
    assert exit["id"] == exit_id
    # The other user is in the users list.
    assert len(context["users"]) == 1
    other = context["users"][0]
    assert other[constants.NAME] == "other_user"
    assert other[constants.DESCRIPTION] == "Another user in the game."
    assert other["id"] == other_user_id
    # The object is in the things list.
    assert len(context["things"]) == 1
    thing = context["things"][0]
    assert thing[constants.NAME] == "item"
    assert thing[constants.DESCRIPTION] == "A test object."
    assert thing["id"] == item_id
