"""
Functions that implement application logic.

Copyright (C) 2019 Nicholas H.Tollervey.
"""


class Logic:
    """
    Gathers together methods which implement application logic. Uses the
    dependency injection pattern.
    """

    def __init__(self, datastore):
        """
        The datastore object contains methods for getting, setting and
        searching the permenant data store.
        """
        self.datastore = datastore

    async def verify_password(self, email, password):
        """
        Given a username and password, return a boolean to indicate if the
        combination is valid.
        """
        return await self.datastore.check_user(email, password)

    async def set_last_login(self, user_id):
        """
        Set the last_login timestamp to time.now() for the referenced user.
        """
        await self.datastore.set_last_seen(user_id)

    async def check_email(self, email: str) -> bool:
        """
        Return a boolean indication if the username is both valid and not
        already taken.
        """
        return await self.datastore.user_exists(email)

    async def create_user(self, email, password):
        """
        Create a user with the referenced email and password. Email a
        confirmation link with instructions to the new user.
        """
        return
