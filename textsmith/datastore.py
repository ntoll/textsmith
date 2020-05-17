"""
Functions that CRUD state stored in a Redis datastore.

Data for objects is stored in Redis Hashes whose values are serialized as
strings of JSON.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import json
import structlog  # type: ignore
from typing import Sequence, Dict, Union
from asyncio_redis import Pool  # type: ignore
from asyncio_redis.exceptions import Error, ErrorReply  # type: ignore


logger = structlog.get_logger()


class DataStore:
    """
    Gathers together methods to implement storage related operations via Redis.
    """

    def __init__(self, redis: Pool) -> None:
        """
        The redis object is a connection pool to a Redis instance.
        """
        self.redis = redis

    async def add_object(
        self,
        **attributes: Dict[
            str,
            Union[
                str, int, float, bool, Sequence[Union[str, int, float, bool]]
            ],
        ],
    ) -> int:
        """
        Create a new object. The new object's parent object is referenced by
        parent_id.
        """
        # Get the new object's unique ID.
        try:
            object_id = int(await self.redis.incr("object_counter"))
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error incrementing object_counter.",
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg("Created new object.", object_id=object_id)
        # Add attributes to the object.
        if attributes:
            await self.annotate_object(object_id, **attributes)
        # Return the new object's id
        return object_id

    async def annotate_object(
        self,
        object_id: int,
        **attributes: Dict[
            str,
            Union[
                str, int, float, bool, Sequence[Union[str, int, float, bool]]
            ],
        ],
    ) -> None:
        """
        Annotate attributes to the object.
        """
        data = {
            attribute: json.dumps(value)
            for attribute, value in attributes.items()
        }
        try:
            transaction = await self.redis.multi()
            await transaction.hmset(str(object_id), data)
            await transaction.exec()
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error annotating object.",
                object_id=object_id,
                attributes=attributes,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg(
            "Annotated attributes to object.", object_id=object_id, data=data
        )

    async def get_objects(
        self, ids: Sequence[int]
    ) -> Dict[
        int,
        Dict[
            str,
            Union[
                str, int, float, bool, Sequence[Union[str, int, float, bool]]
            ],
        ],
    ]:
        """
        Given a list of object IDs, return a dictionary whose keys are object
        IDs and values are a dictionary of the related attributes of each
        object.
        """
        try:
            results = {}
            transaction = await self.redis.multi()
            for object_id in ids:
                results[object_id] = await transaction.hgetall_asdict(
                    str(object_id)
                )
            await transaction.exec()
            # Build result dictionary.
            object_attributes: Dict[
                int,
                Dict[
                    str,
                    Union[
                        str,
                        int,
                        float,
                        bool,
                        Sequence[Union[str, int, float, bool]],
                    ],
                ],
            ] = {object_id: {} for object_id in ids}
            for object_id, result in results.items():
                values = await result
                for key, value in values.items():
                    object_attributes[object_id][key] = json.loads(value)
                object_attributes[object_id]["id"] = object_id
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error getting attributes for objects.",
                object_ids=ids,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        return object_attributes

    async def get_attribute(
        self, object_id: int, attribute: str
    ) -> Union[str, int, float, bool, Sequence[Union[str, int, float, bool]]]:
        """
        Given an object ID and attribute, return the associated value or raise
        a KeyError to indicate the attribute doesn't exist on the object.
        """
        try:
            # Check attribute exists.
            exists = await self.redis.hexists(str(object_id), attribute)
            if not exists:
                raise KeyError(
                    f"Attribute '{attribute}' on #{object_id} does not exist."
                )
            result = await self.redis.hget(str(object_id), attribute)
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error getting attribute for object.",
                object_id=object_id,
                attribute=attribute,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        return json.loads(result)

    async def delete_attributes(
        self, object_id: int, attributes: Sequence[str]
    ) -> None:
        """
        Given an object ID and list of attributes, delete them. Returns the
        number of attributes deleted.
        """
        try:
            transaction = await self.redis.multi()
            result = await transaction.hdel(str(object_id), attributes)
            await transaction.exec()
            number_changed = await result
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error deleting attributes from object.",
                object_id=object_id,
                attributes=attributes,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg(
            f"Deleted {number_changed} attributes from object.",
            object_id=object_id,
            attributes=attributes,
        )
        return number_changed

    async def user_exists(self, email: str) -> bool:
        """
        Returns a boolean indication if a user linked to the referenced email
        address exists within the system.
        """
        return False

    async def create_user(self, email: str, password: str) -> int:
        """
        Create metadata for the new user identified by the referenced email
        address and using the referenced password. Return the id of the object
        in the database associated with this user.
        """
        pass

    async def set_user_password(self, email: str, password: str):
        """
        Given a user identified by the referenced email address, update their
        password to the one provided as an argument to this function.
        """
        pass

    async def check_user(self, email: str, password: str) -> bool:
        """
        Given an email address and password, will check that the credentials
        are valid for signing into the system.
        """
        pass

    async def set_user_active(self, email: str, active_flag: bool = True):
        """
        Set the "active" flag against the user identified via the email
        address to the value of "active_flag".
        """
        pass

    async def set_last_seen(self, user_id: int):
        """
        Set the last_seen value for the user identified by the referenced
        object id.
        """
        pass

    async def delete_user(self, email: str):
        """
        Delete the user and all the objects owned by the user who is
        identified by the referenced email address.
        """
        pass

    async def set_container(self, object_id: int, container_id: int):
        """
        Ensure the referenced object is set to be contained by the object
        referenced as container_id.
        """

    async def get_contents(
        self, object_id: int
    ) -> Dict[
        int,
        Dict[
            str,
            Union[
                str, int, float, bool, Sequence[Union[str, int, float, bool]]
            ],
        ],
    ]:
        """
        Return a dictionary containing all the objects contained within the
        referenced object.
        """
        pass

    async def get_location(self, object_id) -> Union[int, None]:
        """
        Given an object_id, return the id of the object that contains it. If
        the object is not contained within another object, return None.
        """
        pass
