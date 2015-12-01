from conans.errors import AuthenticationException


class UserService(object):

    def __init__(self, authenticator, credentials_manager):
        self.authenticator = authenticator
        self.credentials_manager = credentials_manager

    def authenticate(self, username, password):
        valid = self.authenticator.valid_user(username, password)

        # If user is valid returns a token
        if valid:
            token = self.credentials_manager.get_token_for(username)
            return token
        else:
            raise AuthenticationException("Wrong user or password")
