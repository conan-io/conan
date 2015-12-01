from conans.server.crypto.jwt.jwt_manager import JWTManager


class JWTUpDownAuthManager(JWTManager):
    """JWT for manage auth credentials"""

    def __init__(self, secret, expire_time):
        super(JWTUpDownAuthManager, self).__init__(secret, expire_time)

    def get_token_for(self, resource_path, username, filesize=None):
        """Generates a token with the brl_user and additional data dict if needed"""
        # By now username field will be used only for trace support. Its not necessary
        # for security, if you have a token you are already authenticated
        return JWTManager.get_token_for(self, {"resource_path": resource_path,
                                               "username": username,
                                               "filesize": filesize})

    def get_resource_info(self, token):
        """Gets the user from credentials object. None if no credentials.
        Can raise jwt.ExpiredSignature and jwt.DecodeError"""
        profile = self.get_profile(token)
        username = profile.get("username", None)
        resource_path = profile.get("resource_path", None)
        filesize = profile.get("filesize", None)
        return resource_path, filesize, username
