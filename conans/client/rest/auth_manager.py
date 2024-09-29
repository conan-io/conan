"""
Collaborate with RestApiClient to make remote anonymous and authenticated calls.
Uses user_input to request user's login and password and obtain a token for calling authenticated
methods if receives AuthenticationException from RestApiClient.


Flow:
    Directly invoke a REST method in RestApiClient, example: get_conan.
    if receives AuthenticationException (not open method) will ask user for login and password
    and will invoke RestApiClient.get_token() (with LOGIN_RETRIES retries) and retry to call
    get_conan with the new token.
"""

from conan.api.output import ConanOutput
from conans.client.rest.remote_credentials import RemoteCredentials
from conans.client.rest.rest_client import RestApiClient
from conans.errors import AuthenticationException, ConanException, ForbiddenException

LOGIN_RETRIES = 3


class ConanApiAuthManager:

    def __init__(self, requester, cache_folder, localdb, global_conf):
        self._requester = requester
        self._localdb = localdb
        self._global_conf = global_conf
        self._cache_folder = cache_folder
        self._cached_capabilities = {}  # common to all RestApiClient

    def call_rest_api_method(self, remote, method_name, *args, **kwargs):
        """Handles AuthenticationException and request user to input a user and a password"""
        user, token, refresh_token = self._localdb.get_login(remote.url)
        rest_client = self._get_rest_client(remote)

        if method_name == "authenticate":
            return self._authenticate(remote, *args, **kwargs)

        try:
            ret = getattr(rest_client, method_name)(*args, **kwargs)
            return ret
        except ForbiddenException as e:
            raise ForbiddenException(f"Permission denied for user: '{user}': {e}")
        except AuthenticationException:
            # User valid but not enough permissions
            if user is None or token is None:
                # token is None when you change user with user command
                # Anonymous is not enough, ask for a user
                ConanOutput().info('Please log in to "%s" to perform this action. '
                                   'Execute "conan remote login" command.' % remote.name)
                if self._get_credentials_and_authenticate(user, remote):
                    return self.call_rest_api_method(remote, method_name, *args, **kwargs)
            elif token and refresh_token:
                # If we have a refresh token try to refresh the access token
                try:
                    self._authenticate(remote, user, None)
                except AuthenticationException:
                    # logger.info("Cannot refresh the token, cleaning and retrying: {}".format(exc))
                    self._clear_user_tokens_in_db(user, remote)
                return self.call_rest_api_method(remote, method_name, *args, **kwargs)
            else:
                # Token expired or not valid, so clean the token and repeat the call
                # (will be anonymous call but exporting who is calling)
                # logger.info("Token expired or not valid, cleaning the saved token and retrying")
                self._clear_user_tokens_in_db(user, remote)
                return self.call_rest_api_method(remote, method_name, *args, **kwargs)

    def _get_credentials_and_authenticate(self, user, remote):
        """Try LOGIN_RETRIES to obtain a password from user input for which
        we can get a valid token from api_client. If a token is returned,
        credentials are stored in localdb and rest method is called"""
        creds = RemoteCredentials(self._cache_folder, self._global_conf)
        for _ in range(LOGIN_RETRIES):
            input_user, input_password, interactive = creds.auth(remote)
            try:
                self._authenticate(remote, input_user, input_password)
            except AuthenticationException:
                out = ConanOutput()
                if user is None:
                    out.error('Wrong user or password', error_type="exception")
                else:
                    out.error(f'Wrong password for user "{user}"', error_type="exception")
                if not interactive:
                    raise AuthenticationException(f"Authentication error in remote '{remote.name}'")
            else:
                return True
        raise AuthenticationException("Too many failed login attempts, bye!")

    def _get_rest_client(self, remote):
        username, token, refresh_token = self._localdb.get_login(remote.url)
        return RestApiClient(remote, token, refresh_token, self._requester,
                             self._global_conf, self._cached_capabilities)

    def _clear_user_tokens_in_db(self, user, remote):
        try:
            self._localdb.store(user, token=None, refresh_token=None, remote_url=remote.url)
        except Exception as e:
            out = ConanOutput()
            out.error('Your credentials could not be stored in local cache\n', error_type="exception")
            out.debug(str(e) + '\n')

    def _authenticate(self, remote, user, password):
        rest_client = self._get_rest_client(remote)
        if user is None:  # The user is already in DB, just need the password
            prev_user = self._localdb.get_username(remote.url)
            if prev_user is None:
                raise ConanException("User for remote '%s' is not defined" % remote.name)
            else:
                user = prev_user
        try:
            token, refresh_token = rest_client.authenticate(user, password)
        except UnicodeDecodeError:
            raise ConanException("Password contains not allowed symbols")

        # Store result in DB
        self._localdb.store(user, token, refresh_token, remote.url)
