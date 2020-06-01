"""
Functions that CRUD state stored in a Redis datastore.

Data for objects is stored in Redis Hashes whose values are serialized as
strings of JSON.

Copyright (C) 2020 Nicholas H.Tollervey.
"""
import os
import binascii
import hashlib
import json
import structlog  # type: ignore
from datetime import datetime
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

    def user_key(self, email: str) -> str:
        """
        Given a user's unique email address, return the key to use to
        reference the user in the Redis database.
        """
        return f"user:{email}"

    def token_key(self, token: str) -> str:
        """
        Given a token value, return the key to use to retrieve the associated
        user's details.
        """
        return f"token:{token}"

    def last_seen_key(self, user_id: int) -> str:
        """
        Given a user id, return the key to use to set the timestamp at which
        the user was last seen on the server.
        """
        return f"lastseen:{user_id}"

    def hash_password(self, password: str) -> str:
        """
        Hash a password for safe storage.
        """
        salt = hashlib.sha256(os.urandom(60)).hexdigest().encode("ascii")
        pwdhash = hashlib.pbkdf2_hmac(
            "sha512", password.encode("utf-8"), salt, 100000
        )
        pwdhash = binascii.hexlify(pwdhash)
        return (salt + pwdhash).decode("ascii")

    def verify_password(
        self, stored_password: str, provided_password: str
    ) -> bool:
        """
        Verify a stored password hash against a plaintext provided password.
        """
        salt = stored_password[:64]
        stored_password = stored_password[64:]
        hashed = hashlib.pbkdf2_hmac(
            "sha512",
            provided_password.encode("utf-8"),
            salt.encode("ascii"),
            100000,
        )
        pwdhash = binascii.hexlify(hashed).decode("ascii")
        return pwdhash == stored_password

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
        try:
            result = await self.redis.exists(self.user_key(email))
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error checking if user exists.",
                user_email=email,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        return result

    async def create_user(self, email: str, confirmation_token: str) -> int:
        """
        Create metadata for the new user identified by the referenced email
        address and using the referenced password. Return the id of the object
        in the database associated with this user.
        """
        try:
            # Make an object in the world.
            object_id = await self.add_object()
            # Generate some simple metadata about the new user.
            user = {
                "email": email,
                "active": False,
                "object_id": object_id,
            }
            # JSON-ify for Redis.
            data = {
                attribute: json.dumps(value)
                for attribute, value in user.items()
            }
            transaction = await self.redis.multi()
            # Set the meta-data.
            await transaction.hmset(self.user_key(email), data)
            # Set the link from the emailed token to the user for password
            # creation and account confirmation.
            await transaction.set(self.token_key(confirmation_token), email)
            await transaction.exec()
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error creating user.",
                user_email=email,
                confirmation_token=confirmation_token,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg("Created user.", user=data)
        # Return the object created to represent the user in the world.
        return object_id

    async def token_to_email(
        self, confirmation_token: str
    ) -> Union[str, None]:
        """
        Given a confirmation token, will return the related email address. If
        no email or token exists, returns None.
        """
        try:
            email = await self.redis.get(self.token_key(confirmation_token))
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error getting email from token.",
                confirmation_token=confirmation_token,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        if email:
            return email
        return None

    async def set_user_password(self, email: str, password: str) -> bool:
        """
        Given a user identified by the referenced email address, update their
        password to the one provided as an argument to this function.

        Passwords cannot be set for non-existent users, nor inactive users.
        """
        hashed_password = self.hash_password(password)
        # JSON-ify for Redis.
        data = {"password": json.dumps(hashed_password)}
        try:
            key = self.user_key(email)
            flag = await self.redis.hget(key, "active")
            if flag:  # The user exists.
                is_active = json.loads(flag)
                if is_active:  # The user is active.
                    await self.redis.hmset(key, data)
                    logger.msg("Set password.", user_email=email)
                    return True
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error setting password.",
                user_email=email,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        return False

    async def confirm_user(
        self, confirmation_token: str, password: str
    ) -> str:
        """
        Given a confirmation token sets the referenced password against the
        email address related to the token. This is the final step in user
        confirmation.
        """
        email = await self.token_to_email(confirmation_token)
        if email:
            await self.set_user_active(email, True)
            await self.set_user_password(email, password)
        else:
            msg = "Unable to confirm user with token."
            logger.msg(
                msg, confirmation_token=confirmation_token,
            )
            raise ValueError(msg)
        try:
            await self.redis.delete([self.token_key(confirmation_token)])
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error deleting token.",
                user_email=email,
                confirmation_token=confirmation_token,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg("User confirmed email address.", user_email=email)
        return email

    async def verify_user(self, email: str, password: str) -> bool:
        """
        Given an email address and password, will check that the credentials
        are valid for signing into the system.
        """
        try:
            result = await self.redis.hgetall_asdict(self.user_key(email))
            if not result:
                return False
            user_data = {key: json.loads(val) for key, val in result.items()}
            # Check the user is active.
            if not user_data.get("active", False):
                # Inactive users can never log in.
                return False
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error getting stored password.",
                user_email=email,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        return self.verify_password(user_data["password"], password)

    async def set_user_active(
        self, email: str, active_flag: bool = True
    ) -> None:
        """
        Set the "active" flag against the user identified via the email
        address to the value of "active_flag".
        """
        # JSON-ify for Redis.
        data = {"active": json.dumps(active_flag)}
        try:
            await self.redis.hmset(self.user_key(email), data)
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error setting user active.",
                user_email=email,
                new_active_flag_value=active_flag,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg(
            "Set user active flag.", user_email=email, active=active_flag
        )

    async def set_last_seen(self, email: str) -> None:
        """
        Set the last_seen value for the user identified by the referenced
        object id.
        """
        try:
            result = await self.redis.hgetall_asdict(self.user_key(email))
            if not result:
                return
            user_data = {key: json.loads(val) for key, val in result.items()}
            key = self.last_seen_key(user_data["object_id"])
            now = datetime.now().isoformat()
            await self.redis.set(key, now)
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error setting last seen.",
                user_email=email,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        logger.msg("Set last seen.", user_email=email, last_seen=now)

    async def get_last_seen(self, user_id: int) -> Union[datetime, None]:
        """
        Returns a datetime object representing the moment at which the user,
        whose in-game object is referenced in the arguments, was last seen.
        """
        try:
            key = self.last_seen_key(user_id)
            val = await self.redis.get(key)
            if val:  # The user was last seen at a certain time.
                return datetime.fromisoformat(val)
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error getting last seen.",
                user_id=user_id,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        return None

    async def delete_user(self, email: str) -> None:
        """
        Soft delete the user whilst keeping all the objects owned by the user
        (who is identified by the referenced email address). This involves
        setting the user as inactive (so they can't log in) and ensuring they
        are not contained within another object.
        """
        await self.set_user_active(email, False)
        try:
            result = await self.redis.hgetall_asdict(self.user_key(email))
            if not result:
                return
            user_data = {key: json.loads(val) for key, val in result.items()}
        except (Error, ErrorReply) as ex:  # pragma: no cover
            logger.msg(
                "Error deleting user.",
                user_email=email,
                exc_info=ex,
                redis_error=True,
            )
            raise ex
        await self.set_container(user_data["object_id"], -1)

    async def set_container(self, object_id: int, container_id: int) -> bool:
        """
        Ensure the referenced object is set to be contained by the object
        referenced as container_id. If the container_id < 0, then the
        referenced object_id is not contained anywhere.
        """
        return False

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
