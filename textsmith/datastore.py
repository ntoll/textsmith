"""
Functions that CRUD state stored in a Redis datastore.

Apart from a few system attributes (defined in SYSTEM_ATTRIBUTES) data is
stored as hashmaps (the equivalent of dictionaries in Python) so all the
relevant metadata is stored with the value so it can be boxed/unboxed from/to
Python data types.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
from datetime import datetime
from enum import Enum
from typing import Sequence, Optional, Dict, Set, Union
from asyncio_redis import Pool  # type: ignore
from asyncio_redis.replies import SetReply  # type: ignore


#: Attributes that cannot be updated by the user directly.
SYSTEM_ATTRIBUTES = {
    "alias",  # a set of names by which the object can be aliased.
    "attributes",  # a set of all attributes associated with an object.
    "contains",  # a set of integer object ids contained within an object.
    "editors",  # a set of integer object ids of users who may edit the object.
    "location",  # the integer id of the object containing the object.
    "owner",  # the integer id of the owner of the object.
    "password",  # a string containing the user's hashed password.
    "seen",  # a datetime.isoformat() of a user's last activity.
    "static",  # a boolean flag to indicate if an object can be carried/moved.
    "typeof",  # the type of object (see the ObjectType class).
    "whitelist",  # a set of users who can see the object. Empty=all users.
}

#: Attributes that all objects must have.
MANDATORY_ATTRIBUTES = {
    "alias",
    "attributes",
    "description",  # A human readable description of the object as a string.
    "editors",
    "name",  # The human readable name of the object as a string.
    "owner",
    "summary",  # A short summary string of the object (for repeat viewing).
    "static",
    "typeof",
    "whitelist",
}

#: System attributes that are sets, rather than hashes.
SET_ATTRIBUTES = {
    "alias",
    "attributes",
    "editors",
    "whitelist",
}

#: System attributes that are sets of numbers.
IS_NUMERIC = {
    "contains",
    "editors",
    "whitelist",
}


class ObjectType(Enum):
    """
    Defines the valid object types in the game.

    An object is something which has named attributes with associated values.
    """

    USER = 0  #: An object representing a human player within the game.
    CONTAINER = 1  #: An object that contains other objects (e.g. a room).
    TRANSITION = 2  #: An object representing how to move between CONTAINERs.
    OBJECT = 3  #: A generic object to represent anything other than the above.


class DataStore:
    """
    Gathers together methods to implement storage related operations via Redis.
    """

    def __init__(self, redis: Pool) -> None:
        """
        The redis object is a connection pool to a Redis instance.
        """
        self.redis = redis

    def key_for(self, object_id: int, attribute: str) -> str:
        """
        Return a key conforming to the schema for a valid key of the form:
        object_id:attribute
        """
        return f"{object_id}:{attribute}"

    def box(
        self, value: Union[str, int, float, bool, Dict]
    ) -> Dict[str, Union[str, int, float, bool, Dict]]:
        """
        Turn a Python value into a "boxed" up dictionary representation of the
        value that's suitable for storage as a Redis hashmap.
        """
        if isinstance(value, dict):
            # If already a dictionary, it's just a hashmap representing
            # executable code.
            attribute_value = dict(value)
            attribute_value["typeof"] = "code"
            return attribute_value
        else:
            # Otherwise, use a string representation of the value and typeof
            # annotation for the attribute as a hashmap.
            attribute_value = {
                "value": str(value),
            }
            typeof = type(value)
            if typeof is str:
                attribute_value["typeof"] = "str"
            elif typeof is bool:
                attribute_value["typeof"] = "bool"
            elif typeof is int:
                attribute_value["typeof"] = "int"
            elif typeof is float:
                attribute_value["typeof"] = "float"
            else:
                raise TypeError("Cannot store {typeof} in Redis.")
            return attribute_value

    def unbox(self, obj: Dict[str, str]) -> Union[str, int, float, bool, Dict]:
        """
        Given a hashmap object representing a value in Redis, unbox it as a
        native Python value (dict [for executable code], str, bool, int or
        float).
        """
        if "typeof" not in obj:
            raise TypeError("Cannot unbox value: {}".format(obj))
        typeof = obj["typeof"]
        del obj["typeof"]
        if typeof == "code":
            raw_value: Union[str, int, float, bool, Dict] = obj
        elif typeof == "str":
            raw_value = obj["value"]
        elif typeof == "bool":
            raw_value = bool(obj["value"])
        elif typeof == "int":
            raw_value = int(obj["value"])
        elif typeof == "float":
            raw_value = float(obj["value"])
        return raw_value

    async def add_object(
        self,
        name: str,
        description: str,
        summary: str,
        alias: Sequence[str],
        static: bool,
        typeof: ObjectType,
        owner: Optional[int],
        whitelist: Sequence[str],
        **attributes: Dict[str, Union[str, int, float, bool, Set, Dict]],
    ) -> int:
        """
        Creates a new object in the datastore. Returns the new object's unique
        integer id.

        name - the name of the object given to it by its owner.

        description - a human readable description of the object. When a user
        looks at this object or upon first encountering the object, the name
        and this description are displayed.

        summary - a short human readable summary of the object. Displayed with
        the object name upon repeat encounters.

        alias - other names which could refer to this object.

        static - A flag to indicate if this object is moveable.

        typeof - an instance of ObjectType to denote what sort of object this
        is.

        owner - the id of the object representing the user who owns the new
        object. If none, the object owns itself (i.e. it is a player).

        whitelist - the ids of users who can see the object. If the whitelist
        is empty, all users can see the object.

        attributes - key/value representation of the names and associated
        values of attributes associated with the new object.
        """
        # Get the new object's unique ID.
        object_id = int(await self.redis.incr("object_counter"))
        # Set the owner (if no owner is referenced, the object belongs to
        # itself and *MUST* be a user).
        if owner is None:
            if typeof is ObjectType.USER:
                owner = object_id
            else:
                raise ValueError("New object must be owned by a user.")
        # Create the object's mandatory attributes.
        transaction = await self.redis.multi()
        await transaction.hmset(
            self.key_for(object_id, "name"), self.box(name)
        )
        await transaction.hmset(
            self.key_for(object_id, "description"), self.box(description)
        )
        await transaction.hmset(
            self.key_for(object_id, "summary"), self.box(summary)
        )
        await transaction.hmset(
            self.key_for(object_id, "static"), self.box(static)
        )
        await transaction.hmset(
            self.key_for(object_id, "typeof"), self.box(typeof.name)
        )
        await transaction.hmset(
            self.key_for(object_id, "owner"), self.box(owner)
        )
        if alias:
            await transaction.sadd(
                self.key_for(object_id, "alias"), list(alias)
            )
        if whitelist:
            await transaction.sadd(
                self.key_for(object_id, "whitelist"),
                [str(i) for i in whitelist],
            )
        await transaction.sadd(
            self.key_for(object_id, "editors"), [str(owner),]
        )
        await transaction.sadd(
            self.key_for(object_id, "attributes"), list(MANDATORY_ATTRIBUTES)
        )
        await transaction.exec()
        # Add additional attributes to the object.
        if attributes:
            await self.annotate_object(object_id, **attributes)
        # Return the new object's id
        return object_id

    async def get_objects(
        self, object_ids: Sequence[int]
    ) -> Dict[int, Dict[str, Union[str, int, float, bool, Set, Dict]]]:
        """
        Given a list of object IDs, return a dictionary whose keys are object
        IDs and values are all the related mandatory attributes of the object
        expressed as a dictionary.
        """
        # Gather mandatory attributes for the objects.
        result = {}
        transaction = await self.redis.multi()
        for object_id in object_ids:
            for attribute_name in MANDATORY_ATTRIBUTES:
                key = self.key_for(object_id, attribute_name)
                if attribute_name in SET_ATTRIBUTES:
                    # Special case for set based attributes.
                    result[key] = await transaction.smembers(key)
                else:
                    # Everything else is a hash.
                    result[key] = await transaction.hgetall_asdict(key)
        await transaction.exec()
        # Build result dictionary.
        object_attributes: Dict[
            int, Dict[str, Union[str, int, float, bool, Set, Dict]]
        ] = {object_id: {"id": object_id,} for object_id in object_ids}
        for k, v in result.items():
            obj, key = k.split(":", 1)
            oid = int(obj)
            value = await v
            if isinstance(value, SetReply):
                # Special case for set based attributes.
                set_result: Set = set()
                is_numeric = key in IS_NUMERIC
                for a in value:
                    a_name = await a
                    if is_numeric:
                        a_name = int(a_name)
                    set_result.add(a_name)
                object_attributes[oid][key] = set_result
            else:
                # Everything else should be an unboxable value.
                object_attributes[oid][key] = self.unbox(value)
        return object_attributes

    async def annotate_object(
        self,
        object_id: int,
        **attributes: Dict[str, Union[str, int, float, bool, Set, Dict]],
    ) -> None:
        """
        Annotate a referenced object with the named attributes.
        """
        transaction = await self.redis.multi()
        keys = []
        for key, value in attributes.items():
            if key not in SYSTEM_ATTRIBUTES:
                object_key = self.key_for(object_id, key)
                await transaction.hmset(object_key, self.box(value))
                keys.append(key)
        # Log the attribute key in the "attributes" set associated with
        # the object.
        await transaction.sadd(self.key_for(object_id, "attributes"), keys)
        await transaction.exec()

    async def get_annotation(
        self, object_id: int, name: str
    ) -> Union[str, int, float, bool, Dict]:
        """
        Given an object ID and name of an attribute, return the associated
        value or raise a KeyError to indicate the attribute doesn't exist on
        the object.
        """
        # Check annotation exists.
        key = self.key_for(object_id, name)
        exists = await self.redis.exists(key)
        if not exists:
            raise KeyError(f"The attribute {object_id}:{name} does not exist.")
        result = await self.redis.hgetall_asdict(key)
        return self.unbox(result)

    async def delete_annotation(self, object_id: int, name: str) -> None:
        """
        Given an object ID and name of an attribute, so long as the attribute
        is NOT a mandatory attribute, delete it. Raise a KeyError if the
        attribute doesn't already exist. Raise a ValueError if the key is a
        system or mandatory attribute.
        """
        if name in SYSTEM_ATTRIBUTES or name in MANDATORY_ATTRIBUTES:
            raise ValueError(f"You cannot delete attribute {name}.")
        key = self.key_for(object_id, name)
        exists = await self.redis.exists(key)
        if not exists:
            raise KeyError(f"The attribute {object_id}:{name} does not exist.")
        transaction = await self.redis.multi()
        await transaction.delete(
            [key,]
        )
        await transaction.srem(self.key_for(object_id, "attributes"), [name,])
        await transaction.exec()

    async def add_alias(self, object_id: int, alias: str) -> None:
        """
        Add the referenced alias string to the object identified by object id.
        """
        await self.redis.sadd(self.key_for(object_id, "alias"), [alias,])

    async def delete_alias(self, object_id: int, alias: str) -> None:
        """
        Delete the referenced alias string from the object identified by object
        id.
        """
        await self.redis.srem(self.key_for(object_id, "alias"), [alias,])

    async def add_editor(self, object_id: int, user: int) -> None:
        """
        Add the referenced user's object id to the set of editors who may
        change the object identified by object id.
        """
        await self.redis.sadd(self.key_for(object_id, "editors"), [str(user),])

    async def delete_editor(self, object_id: int, user: int) -> None:
        """
        Delete the referenced user's object id from the set of editors who may
        change the object identified by object id.
        """
        await self.redis.srem(self.key_for(object_id, "editors"), [str(user),])

    async def add_whitelist(self, object_id: int, user: int) -> None:
        """
        Add a user, identified by their object id, to the whitelist for the
        referenced object. The whitelist indicates who can see the object.
        """
        await self.redis.sadd(
            self.key_for(object_id, "whitelist"), [str(user),]
        )

    async def delete_whitelist(self, object_id: int, user: int) -> None:
        """
        Delete a user, identified by their object id, from the whitelist for
        the referenced object. The whitelist indicates who can see the object.
        """
        await self.redis.srem(
            self.key_for(object_id, "whitelist"), [str(user),]
        )

    async def clear_whitelist(self, object_id: int) -> None:
        """
        Make the whitelist for the referenced object empty, thus indicating
        that all users can see the object.
        """
        await self.redis.delete(self.key_for(object_id, "whitelist"))

    async def delete_object(self, object_id: int) -> None:
        """
        Delete the referenced object by removing all keys associated with it
        from the database.
        """
        attribute_key = self.key_for(object_id, "attributes")
        exists = await self.redis.exists(attribute_key)
        if not exists:
            raise KeyError(f"The object with {object_id} does not exist.")
        attributes = await self.redis.smembers_asset(attribute_key)
        keys: Set = set()
        for attribute in attributes:
            keys.add(self.key_for(object_id, attribute))
        await self.redis.delete(keys)

    async def move_object(
        self, object_id: int, old_container: int, new_container: int
    ) -> None:
        """
        Move the referenced object from the old container to the new
        container in a single atomic transaction.
        """
        transaction = await self.redis.multi()
        await transaction.hmset(
            self.key_for(object_id, "location"), self.box(new_container)
        )
        await transaction.srem(
            self.key_for(old_container, "contains"), [str(object_id),]
        )
        await transaction.sadd(
            self.key_for(new_container, "contains"), [str(object_id),]
        )
        await transaction.exec()

    async def get_contents(self, object_id: int) -> Set[int]:
        """
        Return an inventory of object ids contained within the object
        identified by the object id.
        """
        result = await self.redis.smembers_asset(
            self.key_for(object_id, "contains")
        )
        return {int(i) for i in result}

    async def change_owner(self, object_id: int, user: int) -> None:
        """
        Change the owner of the referenced object to the user identified by
        their object's id.
        """
        await self.redis.hmset(
            self.key_for(object_id, "owner"), self.box(user)
        )

    async def set_password_hash(self, user: int, password_hash: str) -> None:
        """
        Set the hashed password for the referenced user.
        """
        key = self.key_for(user, "password")
        transaction = await self.redis.multi()
        await transaction.hmset(key, self.box(password_hash))
        await transaction.sadd(self.key_for(user, "attributes"), ["password",])
        await transaction.exec()

    async def set_seen(self, user: int) -> None:
        """
        Set the seen attribute (representing the time last activity) of the
        referenced user to now.
        """
        key = self.key_for(user, "seen")
        value = datetime.now().isoformat()
        transaction = await self.redis.multi()
        await transaction.hmset(key, self.box(value))
        await transaction.sadd(self.key_for(user, "attributes"), ["seen",])
        await transaction.exec()

    async def get_seen(self, user: int) -> datetime:
        """
        Get a datetime instance indicating the time of most recent activity
        for the referenced user.
        """
        key = self.key_for(user, "seen")
        result = await self.redis.hgetall_asdict(key)
        value = self.unbox(result)
        return datetime.fromisoformat(value)  # type: ignore

    async def set_static(self, object_id: int, is_static: bool) -> None:
        """
        Set the static attribute/flag of the referenced object to indicate if
        it is moveable / carryable.
        """
        key = self.key_for(object_id, "static")
        transaction = await self.redis.multi()
        await transaction.hmset(key, self.box(is_static))
        await transaction.sadd(
            self.key_for(object_id, "attributes"), ["static",]
        )
        await transaction.exec()
