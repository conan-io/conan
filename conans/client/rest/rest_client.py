from conans import CHECKSUM_DEPLOY, REVISIONS, OAUTH_TOKEN
from conans.client.rest.rest_client_v2 import RestV2Methods
from conans.errors import AuthenticationException, ConanException


class RestApiClientFactory(object):

    def __init__(self, requester, config):
        self._requester = requester
        self._config = config
        self._cached_capabilities = {}

    def new(self, remote, token, refresh_token, custom_headers):
        tmp = RestApiClient(remote, token, refresh_token, custom_headers,
                            self._requester, self._config,
                            self._cached_capabilities)
        return tmp


class RestApiClient(object):
    """
        Rest Api Client for handle remote.
    """

    def __init__(self, remote, token, refresh_token, custom_headers, requester,
                 config, cached_capabilities):

        # Set to instance
        self._token = token
        self._refresh_token = refresh_token
        self._remote_url = remote.url
        self._custom_headers = custom_headers
        self._requester = requester

        self._verify_ssl = remote.verify_ssl
        self._config = config

        # This dict is shared for all the instances of RestApiClient
        self._cached_capabilities = cached_capabilities

    def _capable(self, capability, user=None, password=None):
        capabilities = self._cached_capabilities.get(self._remote_url)
        if capabilities is None:
            tmp = RestV2Methods(self._remote_url, self._token, self._custom_headers,
                                self._requester, self._config, self._verify_ssl)
            capabilities = tmp.server_capabilities(user, password)
            self._cached_capabilities[self._remote_url] = capabilities
        return capability in capabilities

    def _get_api(self):
        revisions = self._capable(REVISIONS)

        if not revisions:
            # TODO: port conan_v2_error to 1.X if not revisions
            raise ConanException("The remote doesn't support revisions. "
                                 "Conan 2.0 is no longer compatible with "
                                 "remotes that don't accept revisions.")
        checksum_deploy = self._capable(CHECKSUM_DEPLOY)
        return RestV2Methods(self._remote_url, self._token, self._custom_headers,
                             self._requester, self._config, self._verify_ssl,
                             checksum_deploy)

    def get_recipe(self, ref, dest_folder):
        return self._get_api().get_recipe(ref, dest_folder)

    def get_recipe_snapshot(self, ref):
        return self._get_api().get_recipe_snapshot(ref)

    def get_recipe_sources(self, ref, dest_folder):
        return self._get_api().get_recipe_sources(ref, dest_folder)

    def get_package(self, pref, dest_folder):
        return self._get_api().get_package(pref, dest_folder)

    def upload_recipe(self, ref, files_to_upload, deleted):
        return self._get_api().upload_recipe(ref, files_to_upload, deleted)

    def upload_package(self, pref, files_to_upload):
        return self._get_api().upload_package(pref, files_to_upload)

    def authenticate(self, user, password):
        api_v2 = RestV2Methods(self._remote_url, self._token, self._custom_headers,
                               self._requester, self._config, self._verify_ssl)

        if self._refresh_token and self._token:
            token, refresh_token = api_v2.refresh_token(self._token, self._refresh_token)
        else:
            try:
                # Check capabilities can raise also 401 until the new Artifactory is released
                oauth_capable = self._capable(OAUTH_TOKEN, user, password)
            except AuthenticationException:
                oauth_capable = False

            if oauth_capable:
                # Artifactory >= 6.13.X
                token, refresh_token = api_v2.authenticate_oauth(user, password)
            else:
                token = api_v2.authenticate(user, password)
                refresh_token = None

        return token, refresh_token

    def check_credentials(self):
        return self._get_api().check_credentials()

    def search(self, pattern=None, ignorecase=True):
        return self._get_api().search(pattern, ignorecase)

    def search_packages(self, reference):
        return self._get_api().search_packages(reference)

    def remove_recipe(self, ref):
        return self._get_api().remove_recipe(ref)

    def remove_all_packages(self, ref):
        return self._get_api().remove_all_packages(ref)

    def remove_packages(self, prefs):
        return self._get_api().remove_packages(prefs)

    def server_capabilities(self):
        return self._get_api().server_capabilities()

    def get_recipe_revisions_references(self, ref):
        return self._get_api().get_recipe_revisions_references(ref)

    def get_package_revisions_references(self, pref, headers=None):
        return self._get_api().get_package_revisions_references(pref, headers=headers)

    def get_latest_recipe_reference(self, ref):
        return self._get_api().get_latest_recipe_reference(ref)

    def get_latest_package_reference(self, pref, headers):
        return self._get_api().get_latest_package_reference(pref, headers=headers)

    def get_recipe_revision_reference(self, ref):
        return self._get_api().get_recipe_revision_reference(ref)

    def get_package_revision_reference(self, pref):
        return self._get_api().get_package_revision_reference(pref)
