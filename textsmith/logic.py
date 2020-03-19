"""
Functions that implement application logic.

Copyright (C) 2019 Nicholas H.Tollervey.
"""


class Logic:
    """
    Gathers together methods which implement game logic. Uses the dependency
    injection pattern.
    """

    def __init__(self, models, datastore):
        """
        The models object contains methods for creating data structures that
        represent in-game objects.

        The datastore object contains methods for getting, setting and
        searching the permenant data store.
        """
        self.models = models
        self.datastore = datastore

    async def verify_password(self, username, password):
        """
        Given a username and password, return a boolean to indicate if the
        combination is valid.
        """
        pass

    async def set_last_login(self, user_id):
        """
        Set the last_login timestamp to time.now() for the referenced user.
        """
        pass

    async def check_username(self, username):
        """
        Return a boolean indication if the username is both valid and not
        already taken.
        """
        pass

    async def create_user(self, username, password, email):
        """
        Create a user with the referenced username, password and email address.
        Email a confirmation link with instructions to the new user.
        """
        pass
