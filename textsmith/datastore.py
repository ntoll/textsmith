"""
Functions that CRUD state stored in a Redis datastore.

Data for objects is stored in Redis Hashes whose values are serialized as
strings of JSON.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import json
from typing import Sequence, Dict, Union
from asyncio_redis import Pool  # type: ignore


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
        object_id = int(await self.redis.incr("object_counter"))
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
        transaction = await self.redis.multi()
        await transaction.hmset(str(object_id), data)
        await transaction.exec()

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
        IDs and values are all the related attributes of the object belonging
        to the object itself, expressed as a dictionary.
        """
        # Gather the values associated with objects.
        transaction = await self.redis.multi()
        results = {}
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
        ] = {object_id: {"id": object_id,} for object_id in ids}
        for object_id, result in results.items():
            values = await result
            for key, value in values.items():
                object_attributes[object_id][key] = json.loads(value)
        return object_attributes

    async def get_attribute(
        self, object_id: int, attribute: str
    ) -> Union[str, int, float, bool, Sequence[Union[str, int, float, bool]]]:
        """
        Given an object ID and attribute, return the associated value or raise
        a KeyError to indicate the attribute doesn't exist on the object.
        """
        # Check attribute exists.
        exists = await self.redis.hexists(str(object_id), attribute)
        if not exists:
            raise KeyError(
                f"The attribute '{attribute}' on #{object_id} does not exist."
            )
        result = await self.redis.hget(str(object_id), attribute)
        return json.loads(result)

    async def delete_attribute(self, object_id: int, attribute: str) -> None:
        """
        Given an object ID and owner of an attribute, delete it. Raise a
        KeyError if the attribute doesn't already exist.
        """
        exists = await self.redis.hexists(str(object_id), attribute)
        if not exists:
            raise KeyError(
                f"The attribute '{attribute}' on #{object_id} does not exist."
            )
        transaction = await self.redis.multi()
        await transaction.hdel(str(object_id), [attribute,])
        await transaction.exec()
