from datetime import datetime
from calendar import timegm

import jwt


class JWTManager(object):
    """
        Handles the JWT token generation and encryption.
    """

    def __init__(self, secret, expire_time):
        """expire_time is a timedelta
           secret is a string with the secret encoding key"""
        self.secret = secret
        self.expire_time = expire_time

    def get_token_for(self, profile_fields=None):
        """Generates a token with the provided fields.
        if exp is True, expiration time will be used"""
        profile_fields = profile_fields or {}

        if self.expire_time:
            profile_fields["exp"] = timegm((datetime.utcnow() + self.expire_time).timetuple())

        return jwt.encode(profile_fields, self.secret, algorithm="HS256")

    def get_profile(self, token):
        """Gets the user from credentials object. None if no credentials.
        Can raise jwt.ExpiredSignature and jwt.DecodeError"""
        profile = jwt.decode(token, self.secret, algorithms=["HS256"])
        return profile
