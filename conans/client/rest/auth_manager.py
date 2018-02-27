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

from conans.errors import AuthenticationException, ForbiddenException,\
    ConanException
from uuid import getnode as get_mac
import hashlib
from conans.util.log import logger


def input_credentials_if_unauthorized(func):
    """Decorator. Handles AuthenticationException and request user
    to input a user and a password"""
    LOGIN_RETRIES = 3

    def wrapper(self, *args, **kwargs):
        try:
            # Set custom headers of mac_digest and username
            self.set_custom_headers(self.user)
            ret = func(self, *args, **kwargs)
            return ret
        except ForbiddenException:
            raise ForbiddenException("Permission denied for user: '%s'" % self.user)
        except AuthenticationException:
            # User valid but not enough permissions
            if self.user is None or self._rest_client.token is None:
                # token is None when you change user with user command
                # Anonymous is not enough, ask for a user
                remote = self.remote
                self._user_io.out.info('Please log in to "%s" to perform this action. '
                                       'Execute "conan user" command.' % remote.name)
                if "bintray" in remote.url:
                    self._user_io.out.info('If you don\'t have an account sign up here: '
                                           'https://bintray.com/signup/oss')
                return retry_with_new_token(self, *args, **kwargs)
            else:
                # Token expired or not valid, so clean the token and repeat the call
                # (will be anonymous call but exporting who is calling)
                logger.info("Token expired or not valid, cleaning the saved token and retrying")
                self._store_login((self.user, None))
                self._rest_client.token = None
                # Set custom headers of mac_digest and username
                self.set_custom_headers(self.user)
                return wrapper(self, *args, **kwargs)

    def retry_with_new_token(self, *args, **kwargs):
        """Try LOGIN_RETRIES to obtain a password from user input for which
        we can get a valid token from api_client. If a token is returned,
        credentials are stored in localdb and rest method is called"""
        for _ in range(LOGIN_RETRIES):
            user, password = self._user_io.request_login(self._remote.name, self.user)
            token = None
            try:
                token = self.authenticate(user, password)
            except AuthenticationException:
                if self.user is None:
                    self._user_io.out.error('Wrong user or password')
                else:
                    self._user_io.out.error(
                        'Wrong password for user "%s"' % self.user)
                    self._user_io.out.info(
                        'You can change username with "conan user <username>"')
            if token:
                logger.debug("Got token: %s" % str(token))
                self._rest_client.token = token
                self.user = user
                self._store_login((user, token))
                # Set custom headers of mac_digest and username
                self.set_custom_headers(user)
                return wrapper(self, *args, **kwargs)

        raise AuthenticationException("Too many failed login attempts, bye!")
    return wrapper


class ConanApiAuthManager(object):

    def __init__(self, rest_client, user_io, localdb):
        self._user_io = user_io
        self._rest_client = rest_client
        self._localdb = localdb
        self._remote = None

    @property
    def remote(self):
        return self._remote

    @remote.setter
    def remote(self, remote):
        self._remote = remote
        self._rest_client.remote_url = remote.url
        self._rest_client.verify_ssl = remote.verify_ssl
        self.user, self._rest_client.token = self._localdb.get_login(remote.url)

    def _store_login(self, login):
        try:
            self._localdb.set_login(login, self._remote.url)
        except Exception as e:
            self._user_io.out.error(
                'Your credentials could not be stored in local cache\n')
            self._user_io.out.debug(str(e) + '\n')

    @staticmethod
    def get_mac_digest():
        sha1 = hashlib.sha1()
        sha1.update(str(get_mac()).encode())
        return str(sha1.hexdigest())

    def set_custom_headers(self, username):
        # First identifies our machine, second the username even if it was not
        # authenticated
        custom_headers = self._rest_client.custom_headers
        custom_headers['X-Client-Anonymous-Id'] = self.get_mac_digest()
        custom_headers['X-Client-Id'] = str(username or "")

    # ######### CONAN API METHODS ##########

    @input_credentials_if_unauthorized
    def upload_recipe(self, conan_reference, the_files, retry, retry_wait, ignore_deleted_file):
        return self._rest_client.upload_recipe(conan_reference, the_files, retry, retry_wait,
                                               ignore_deleted_file)

    @input_credentials_if_unauthorized
    def upload_package(self, package_reference, the_files, retry, retry_wait):
        return self._rest_client.upload_package(package_reference, the_files, retry, retry_wait)

    @input_credentials_if_unauthorized
    def get_conan_digest(self, conan_reference):
        return self._rest_client.get_conan_digest(conan_reference)

    @input_credentials_if_unauthorized
    def get_package_digest(self, package_reference):
        return self._rest_client.get_package_digest(package_reference)

    @input_credentials_if_unauthorized
    def get_recipe(self, conan_reference, dest_folder, filter_function):
        return self._rest_client.get_recipe(conan_reference, dest_folder, filter_function)

    @input_credentials_if_unauthorized
    def get_package(self, package_reference, dest_folder):
        return self._rest_client.get_package(package_reference, dest_folder)

    @input_credentials_if_unauthorized
    def get_package_info(self, package_reference):
        return self._rest_client.get_package_info(package_reference)

    @input_credentials_if_unauthorized
    def search(self, pattern, ignorecase):
        return self._rest_client.search(pattern, ignorecase)

    @input_credentials_if_unauthorized
    def search_packages(self, reference, query):
        return self._rest_client.search_packages(reference, query)

    @input_credentials_if_unauthorized
    def remove(self, conan_refernce):
        return self._rest_client.remove_conanfile(conan_refernce)

    @input_credentials_if_unauthorized
    def remove_packages(self, conan_reference, package_ids):
        return self._rest_client.remove_packages(conan_reference, package_ids)

    @input_credentials_if_unauthorized
    def get_path(self, conan_reference, path, package_id):
        return self._rest_client.get_path(conan_reference, path, package_id)

    def authenticate(self, user, password):
        remote_url = self._remote.url
        prev_user = self._localdb.get_username(remote_url)
        prev_username = prev_user or "None (anonymous)"
        if not user:
            self._user_io.out.info("Current '%s' user: %s" % (self._remote.name, prev_username))
        else:
            user = None if user.lower() == 'none' else user
            if user and password is not None:
                token = self._remote_auth(user, password)
            else:
                token = None
            if prev_user == user:
                self._user_io.out.info("Current '%s' user already: %s"
                                       % (self._remote.name, prev_username))
            else:
                username = user or "None (anonymous)"
                self._user_io.out.info("Change '%s' user from %s to %s"
                                       % (self._remote.name, prev_username, username))
            self._localdb.set_login((user, token), remote_url)
            return token

    def _remote_auth(self, user, password):
        try:
            return self._rest_client.authenticate(user, password)
        except UnicodeDecodeError:
            raise ConanException("Password contains not allowed symbols")
