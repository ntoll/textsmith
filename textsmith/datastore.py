"""
Functions that CRUD game state stored in a Redis datastore.

Copyright (C) 2019 Nicholas H.Tollervey.
"""
from enum import Enum
from typing import Sequence, Optional, Dict, Set, Union
from asyncio_redis import Pool  # type: ignore
from asyncio_redis.replies import SetReply  # type: ignore


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
        # Attributes that cannot be updated by the user directly.
        self.system_attributes = {
            "alias",  # a set of names by which the object can be aliased.
            "attributes",  # a set of all attributes associated with an object.
            "editors",  # a set of user ids who may edit the object.
            "owner",  # the integer id of the owner of the object.
            "password",  # a user's hashed password.
            "static",  # a flag to indicate if an object can be carried/moved.
            "typeof",  # the type of object (see the ObjectType class).
        }
        # Attributes that all objects must have.
        self.mandatory_attributes = {
            "alias",
            "attributes",
            "description",
            "editors",
            "name",
            "owner",
            "summary",
            "typeof",
        }
        # Attributes that are sets, rather than hashes.
        self.set_attributes = {
            "alias",
            "attributes",
            "editors",
        }

    def key_for(self, object_id: int, attribute_name: str) -> str:
        """
        Return a key conforming to the schema for a valid key of the form:
        object_id:attribute_name
        """
        return f"{object_id}:{attribute_name}"

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
        typeof: ObjectType,
        owner: Optional[int],
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

        typeof - an instance of ObjectType to denote what sort of object this
        is.

        owner - the id of the object representing the user who owns the new
        object. If none, the object owns itself (i.e. it is a player).

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
            self.key_for(object_id, "typeof"), self.box(typeof.name)
        )
        await transaction.hmset(
            self.key_for(object_id, "owner"), self.box(owner)
        )
        await transaction.sadd(self.key_for(object_id, "alias"), list(alias))
        await transaction.sadd(
            self.key_for(object_id, "editors"), [str(owner),]
        )
        await transaction.sadd(
            self.key_for(object_id, "attributes"),
            list(self.mandatory_attributes),
        )
        await transaction.exec()
        # Add additional attributes to the object.
        if attributes:
            await self.annotate_object(object_id, **attributes)
        # Return the new object's id
        return object_id

    async def get_object(
        self, object_id: int
    ) -> Dict[str, Union[str, int, float, bool, Set, Dict]]:
        """
        Given an object ID, return all the mandatory attributes as a
        dictionary.
        """
        # Check object exists.
        exists = await self.redis.exists(self.key_for(object_id, "attributes"))
        if not exists:
            raise ValueError(f"No object with id {object_id} exists.")
        # Gather mandatory attributes for the object.
        result = {}
        transaction = await self.redis.multi()
        for attribute_name in self.mandatory_attributes:
            key = self.key_for(object_id, attribute_name)
            if attribute_name in self.set_attributes:
                # Special case for set based attributes.
                result[attribute_name] = await transaction.smembers(key)
            else:
                # Everything else is a hash.
                result[attribute_name] = await transaction.hgetall_asdict(key)
        await transaction.exec()
        # Build result dictionary.
        object_attributes: Dict[
            str, Union[str, int, float, bool, Set, Dict]
        ] = {}
        for k, v in result.items():
            value = await v
            if isinstance(value, SetReply):
                # Special case for set based attributes.
                set_result: Set = set()
                for a in value:
                    a_name = await a
                    set_result.add(a_name)
                object_attributes[k] = set_result
            else:
                # Everything else should be an unboxable value.
                object_attributes[k] = self.unbox(value)
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
            if key not in self.system_attributes:
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
        # Check object exists.
        key = self.key_for(object_id, name)
        exists = await self.redis.exists(key)
        if not exists:
            raise KeyError(f"The attribute {object_id}:{name} does not exist.")
        result = await self.redis.hgetall_asdict(key)
        return self.unbox(result)

    async def delete_annotation(self, object_id: int, name: str) -> bool:
        """
        Given an object ID and name of an attribute, so long as the attribute
        is NOT a mandatory attribute, delete it. Raise a KeyError if the
        attribute doesn't already exist. Returns a boolean flag to indicate if
        the operation was a success.
        """
        pass

    async def add_alias(self, object_id: int, name):
        """
        """
        pass

    async def delete_alias(self, object_id: int, name):
        """
        """
        pass

    async def delete_object(self, object_id: int) -> bool:
        """
        """
        pass

    async def move_object(
        self, object_id: int, old_container: int, new_container: int
    ) -> bool:
        """
        """
        pass

    async def get_contents(self, object_id: int) -> Sequence[int]:
        """
        """
        pass

    async def get_possessions(self, object_id: int) -> Sequence[int]:
        """
        """
        pass

    async def get_seen(self, object_id: int, user_id: int) -> bool:
        """
        """
        pass

    async def set_seen(self, object_id: int, user_id: int) -> bool:
        """
        """
        pass
