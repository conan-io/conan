from datetime import datetime, timezone
from calendar import timegm

import jwt


class JWTCredentialsManager:
    """JWT for manage auth credentials"""

    def __init__(self, secret, expire_time):
        """expire_time is a timedelta
        secret is a string with the secret encoding key"""
        self.secret = secret
        self.expire_time = expire_time

    def get_token_for(self, user):
        """Generates a token with the brl_user and additional data dict if needed"""
        profile_fields = {"user": user,
                          "exp": timegm((datetime.now(timezone.utc) + self.expire_time).timetuple())}
        return jwt.encode(profile_fields, self.secret, algorithm="HS256")

    def get_user(self, token):
        """Gets the user from credentials object. None if no credentials.
        Can raise jwt.ExpiredSignature and jwt.DecodeError"""
        profile = jwt.decode(token, self.secret, algorithms=["HS256"])
        return profile.get("user", None)
