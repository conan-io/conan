"""
Collaborate with RestApiClient to make remote anonymous and authenticated calls.
Uses user_io to request user's login and password and obtain a token for calling authenticated
methods if receives AuthenticationException from RestApiClient.


Flow:
    Directly invoke a REST method in RestApiClient, example: get_conan.
    if receives AuthenticationException (not open method) will ask user for login and password
    and will invoke RestApiClient.get_token() (with LOGIN_RETRIES retries) and retry to call
    get_conan with the new token.
"""

import hashlib
from uuid import getnode as get_mac

from conans.client.cmd.user import update_localdb
from conans.errors import AuthenticationException, ConanException, ForbiddenException
from conans.util.log import logger

LOGIN_RETRIES = 3


class ConanApiAuthManager(object):

    def __init__(self, rest_client_factory, user_io, localdb):
        self._user_io = user_io
        self._rest_client_factory = rest_client_factory
        self._localdb = localdb

    def call_rest_api_method(self, remote, method_name, *args, **kwargs):
        """Handles AuthenticationException and request user to input a user and a password"""
        user, token, refresh_token = self._localdb.get_login(remote.url)
        rest_client = self._get_rest_client(remote)

        if method_name == "authenticate":
            return self._authenticate(remote, *args, **kwargs)

        try:
            ret = getattr(rest_client, method_name)(*args, **kwargs)
            return ret
        except ForbiddenException:
            raise ForbiddenException("Permission denied for user: '%s'" % user)
        except AuthenticationException:
            # User valid but not enough permissions
            if user is None or token is None:
                # token is None when you change user with user command
                # Anonymous is not enough, ask for a user
                self._user_io.out.info('Please log in to "%s" to perform this action. '
                                       'Execute "conan user" command.' % remote.name)
                return self._retry_with_new_token(user, remote, method_name, *args, **kwargs)
            elif token and refresh_token:
                # If we have a refresh token try to refresh the access token
                try:
                    self._authenticate(remote, user, None)
                except AuthenticationException as exc:
                    logger.info("Cannot refresh the token, cleaning and retrying: {}".format(exc))
                    self._clear_user_tokens_in_db(user, remote)
                return self.call_rest_api_method(remote, method_name, *args, **kwargs)
            else:
                # Token expired or not valid, so clean the token and repeat the call
                # (will be anonymous call but exporting who is calling)
                logger.info("Token expired or not valid, cleaning the saved token and retrying")
                self._clear_user_tokens_in_db(user, remote)
                return self.call_rest_api_method(remote, method_name, *args, **kwargs)

    def _retry_with_new_token(self, user, remote, method_name, *args, **kwargs):
        """Try LOGIN_RETRIES to obtain a password from user input for which
        we can get a valid token from api_client. If a token is returned,
        credentials are stored in localdb and rest method is called"""
        for _ in range(LOGIN_RETRIES):
            input_user, input_password = self._user_io.request_login(remote.name, user)
            try:
                self._authenticate(remote, input_user, input_password)
            except AuthenticationException:
                if user is None:
                    self._user_io.out.error('Wrong user or password')
                else:
                    self._user_io.out.error('Wrong password for user "%s"' % user)
                    self._user_io.out.info('You can change username with "conan user <username>"')
            else:
                return self.call_rest_api_method(remote, method_name, *args, **kwargs)

        raise AuthenticationException("Too many failed login attempts, bye!")

    def _get_rest_client(self, remote):
        username, token, refresh_token = self._localdb.get_login(remote.url)
        custom_headers = {'X-Client-Anonymous-Id': self._get_mac_digest(),
                          'X-Client-Id': str(username or "")}
        return self._rest_client_factory.new(remote, token, refresh_token, custom_headers)

    def _clear_user_tokens_in_db(self, user, remote):
        try:
            self._localdb.store(user, token=None, refresh_token=None, remote_url=remote.url)
        except Exception as e:
            self._user_io.out.error('Your credentials could not be stored in local cache\n')
            self._user_io.out.debug(str(e) + '\n')

    @staticmethod
    def _get_mac_digest():
        sha1 = hashlib.sha1()
        sha1.update(str(get_mac()).encode())
        return str(sha1.hexdigest())

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
        remote_name, prev_user, user = update_localdb(self._localdb, user, token, refresh_token,
                                                      remote)
        return remote_name, prev_user, user
