'''
Collaborate with RestApiClient to make remote anonymous and authenticated calls.
Uses user_io to request user's login and password and obtain a token for calling authenticated
methods if receives AuthenticationException from RestApiClient.


Flow:

    Directly invoke a REST method in RestApiClient, example: get_conan.
    if receives AuthenticationException (not open method) will ask user for login and password
    and will invoke RestApiClient.get_token() (with LOGIN_RETRIES retries) and retry to call
    get_conan with the new token.
'''


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
        except ForbiddenException as e:
            # User valid but not enough permissions
            if self.user is None or self.rest_client.token is None:
                # token is None when you change user with user command
                # Anonymous is not enough, ask for a user
                self.user_io.out.info('Please log in to perform this action. '
                                      'Execute "conan user" command. '
                                      'If you don\'t have an account sign up here: '
                                      'http://www.conan.io')
                return retry_with_new_token(self, *args, **kwargs)
            else:
                # If our user receives a ForbiddenException propagate it, not
                # log with other user
                raise e
        except AuthenticationException:
            # Token expired or not valid, so clean the token and repeat the call
            # (will be anonymous call but exporting who is calling)
            self._store_login((self.user, None))
            self.rest_client.token = None
            # Set custom headers of mac_digest and username
            self.set_custom_headers(self.user)
            return wrapper(self, *args, **kwargs)

    def retry_with_new_token(self, *args, **kwargs):
        """Try LOGIN_RETRIES to obtain a password from user input for which
        we can get a valid token from api_client. If a token is returned,
        credentials are stored in localdb and rest method is called"""
        for _ in range(LOGIN_RETRIES):
            user, password = self.user_io.request_login(self.user)
            token = None
            try:
                token = self.authenticate(user, password)
            except AuthenticationException:
                if self.user is None:
                    self.user_io.out.error('Wrong user or password')
                else:
                    self.user_io.out.error(
                        'Wrong password for user "%s"' % self.user)
                    self.user_io.out.info(
                        'You can change username with "conan user <username>"')
            if token:
                logger.debug("Got token: %s" % str(token))
                self.rest_client.token = token
                self.user = user
                self._store_login((user, token))
                # Set custom headers of mac_digest and username
                self.set_custom_headers(user)
                return func(self, *args, **kwargs)

        raise AuthenticationException("Too many failed login attempts, bye!")
    return wrapper


class ConanApiAuthManager(object):

    def __init__(self, rest_client, user_io, localdb):
        self.user_io = user_io
        self.rest_client = rest_client
        self.localdb = localdb
        self.user, self.rest_client.token = localdb.get_login()

    @property
    def remote_url(self):
        return self.rest_client.remote_url

    @remote_url.setter
    def remote_url(self, url):
        self.rest_client.remote_url = url

    def _store_login(self, login):
        try:
            self.localdb.set_login(login)
        except Exception as e:
            self.user_io.out.error(
                'Your credentials could not be stored in local cache\n')
            self.user_io.out.debug(str(e) + '\n')

    @staticmethod
    def get_mac_digest():
        sha1 = hashlib.sha1()
        sha1.update(str(get_mac()))
        return str(sha1.hexdigest())

    def set_custom_headers(self, username):
        # First identifies our machine, second the username even if it was not
        # authenticated
        custom_headers = self.rest_client.custom_headers
        custom_headers['X-Client-Anonymous-Id'] = self.get_mac_digest()
        custom_headers['X-Client-Id'] = str(username or "")

    # ######### CONAN API METHODS ##########

    @input_credentials_if_unauthorized
    def upload_conan(self, conan_reference, the_files):
        return self.rest_client.upload_conan(conan_reference, the_files)

    @input_credentials_if_unauthorized
    def upload_package(self, package_reference, the_files):
        return self.rest_client.upload_package(package_reference, the_files)

    @input_credentials_if_unauthorized
    def get_conan_digest(self, conan_reference):
        return self.rest_client.get_conan_digest(conan_reference)

    @input_credentials_if_unauthorized
    def get_conanfile(self, conan_reference):
        return self.rest_client.get_conanfile(conan_reference)

    @input_credentials_if_unauthorized
    def get_package(self, package_reference):
        return self.rest_client.get_package(package_reference)

    @input_credentials_if_unauthorized
    def search(self, pattern, ignorecase):
        return self.rest_client.search(pattern, ignorecase)

    @input_credentials_if_unauthorized
    def remove(self, conan_refernce):
        return self.rest_client.remove_conanfile(conan_refernce)

    @input_credentials_if_unauthorized
    def remove_packages(self, conan_reference, package_ids):
        return self.rest_client.remove_packages(conan_reference, package_ids)

    def authenticate(self, user, password):
        """Get token"""
        try:
            return self.rest_client.authenticate(user, password)
        except UnicodeDecodeError:
            raise ConanException("Password contains not allowed symbols")

