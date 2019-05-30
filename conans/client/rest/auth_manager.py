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
            try:
                token, _, _, _ = self.authenticate(user, password)
            except AuthenticationException:
                if self.user is None:
                    self._user_io.out.error('Wrong user or password')
                else:
                    self._user_io.out.error(
                        'Wrong password for user "%s"' % self.user)
                    self._user_io.out.info(
                        'You can change username with "conan user <username>"')
            else:
                logger.debug("Got token")
                self._rest_client.token = token
                self.user = user
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
    def check_credentials(self):
        self._rest_client.check_credentials()

    @input_credentials_if_unauthorized
    def upload_recipe(self, ref, files_to_upload, deleted, retry, retry_wait):
        return self._rest_client.upload_recipe(ref, files_to_upload, deleted, retry, retry_wait)

    @input_credentials_if_unauthorized
    def upload_package(self, pref, files_to_upload, deleted, retry, retry_wait):
        return self._rest_client.upload_package(pref, files_to_upload, deleted, retry, retry_wait)

    @input_credentials_if_unauthorized
    def get_recipe_manifest(self, ref):
        return self._rest_client.get_recipe_manifest(ref)

    @input_credentials_if_unauthorized
    def get_package_manifest(self, pref):
        return self._rest_client.get_package_manifest(pref)

    @input_credentials_if_unauthorized
    def get_package(self, pref, dest_folder):
        return self._rest_client.get_package(pref, dest_folder)

    @input_credentials_if_unauthorized
    def get_recipe(self, ref, dest_folder):
        return self._rest_client.get_recipe(ref, dest_folder)

    @input_credentials_if_unauthorized
    def get_recipe_snapshot(self, ref):
        return self._rest_client.get_recipe_snapshot(ref)

    @input_credentials_if_unauthorized
    def get_recipe_sources(self, ref, dest_folder):
        return self._rest_client.get_recipe_sources(ref, dest_folder)

    @input_credentials_if_unauthorized
    def download_files_to_folder(self, urls, dest_folder):
        return self._rest_client.download_files_to_folder(urls, dest_folder)

    @input_credentials_if_unauthorized
    def get_package_info(self, pref):
        return self._rest_client.get_package_info(pref)

    @input_credentials_if_unauthorized
    def get_package_snapshot(self, pref):
        return self._rest_client.get_package_snapshot(pref)

    @input_credentials_if_unauthorized
    def search(self, pattern, ignorecase):
        return self._rest_client.search(pattern, ignorecase)

    @input_credentials_if_unauthorized
    def search_packages(self, ref, query):
        return self._rest_client.search_packages(ref, query)

    @input_credentials_if_unauthorized
    def remove(self, ref):
        return self._rest_client.remove_conanfile(ref)

    @input_credentials_if_unauthorized
    def remove_packages(self, ref, package_ids):
        return self._rest_client.remove_packages(ref, package_ids)

    @input_credentials_if_unauthorized
    def get_recipe_path(self, ref, path):
        return self._rest_client.get_recipe_path(ref, path)

    @input_credentials_if_unauthorized
    def get_package_path(self, pref, path):
        return self._rest_client.get_package_path(pref, path)

    @input_credentials_if_unauthorized
    def get_recipe_revisions(self, ref):
        return self._rest_client.get_recipe_revisions(ref)

    @input_credentials_if_unauthorized
    def get_package_revisions(self, pref):
        return self._rest_client.get_package_revisions(pref)

    @input_credentials_if_unauthorized
    def get_latest_recipe_revision(self, ref):
        return self._rest_client.get_latest_recipe_revision(ref)

    @input_credentials_if_unauthorized
    def get_latest_package_revision(self, pref):
        return self._rest_client.get_latest_package_revision(pref)

    def authenticate(self, user, password):
        if user is None:  # The user is already in DB, just need the passwd
            prev_user = self._localdb.get_username(self._remote.url)
            if prev_user is None:
                raise ConanException("User for remote '%s' is not defined" % self._remote.name)
            else:
                user = prev_user

        try:
            token = self._rest_client.authenticate(user, password)
        except UnicodeDecodeError:
            raise ConanException("Password contains not allowed symbols")

        # Store result in DB
        remote_name, prev_user, user = update_localdb(self._localdb, user, token, self._remote)
        return token, remote_name, prev_user, user
