from conans.server.crypto.jwt.jwt_manager import JWTManager


class JWTCredentialsManager(JWTManager):
    """JWT for manage auth credentials"""

    def __init__(self, secret, expire_time):
        super(JWTCredentialsManager, self).__init__(secret, expire_time)

    def get_token_for(self, brl_user):
        """Generates a token with the brl_user and additional data dict if needed"""
        return JWTManager.get_token_for(self, {"user": brl_user})

    def get_user(self, token):
        """Gets the user from credentials object. None if no credentials.
        Can raise jwt.ExpiredSignature and jwt.DecodeError"""
        profile = self.get_profile(token)
        username = profile.get("user", None)
        return username
