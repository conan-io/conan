from datetime import datetime
from calendar import timegm

import jwt
import six


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
           if exp is True, expiration time will be used

           This method supports both JWT 1.x and 2.x
           Read https://github.com/conan-io/conan/pull/8952 for more details
        """
        profile_fields = profile_fields or {}

        if self.expire_time:
            profile_fields["exp"] = datetime.utcnow() + self.expire_time

        # profile_fields.exp no longer is converted to integer on JWT 2.x, we need to do it manually
        if self.expire_time and isinstance(profile_fields.get("exp"), datetime):
            profile_fields["exp"] = timegm(profile_fields.get("exp").utctimetuple())
        encoded = jwt.encode(profile_fields, self.secret, algorithm="HS256")
        # JWT 2,x returns decoded string, but 1.x returns encoded bytes
        if isinstance(encoded, six.text_type):
            encoded = encoded.encode('utf-8')
        return encoded

    def get_profile(self, token):
        """Gets the user from credentials object. None if no credentials.
        Can raise jwt.ExpiredSignature and jwt.DecodeError"""
        profile = jwt.decode(token, self.secret, algorithms=["HS256"])
        return profile
