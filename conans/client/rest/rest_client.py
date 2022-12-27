from conans import CHECKSUM_DEPLOY, REVISIONS, ONLY_V2, OAUTH_TOKEN, MATRIX_PARAMS
from conans.client.rest.rest_client_v1 import RestV1Methods
from conans.client.rest.rest_client_v2 import RestV2Methods
from conans.errors import OnlyV2Available, AuthenticationException
from conans.search.search import filter_packages
from conans.util.log import logger


class RestApiClientFactory(object):

    def __init__(self, output, requester, config, artifacts_properties=None):
        self._output = output
        self._requester = requester
        self._config = config
        self._artifacts_properties = artifacts_properties
        self._cached_capabilities = {}

    def new(self, remote, token, refresh_token, custom_headers):
        tmp = RestApiClient(remote, token, refresh_token, custom_headers,
                            self._output, self._requester, self._config,
                            self._cached_capabilities,
                            self._artifacts_properties)
        return tmp


class RestApiClient(object):
    """
        Rest Api Client for handle remote.
    """

    def __init__(self, remote, token, refresh_token, custom_headers, output, requester,
                 config, cached_capabilities, artifacts_properties=None):

        # Set to instance
        self._token = token
        self._refresh_token = refresh_token
        self._remote_url = remote.url
        self._custom_headers = custom_headers
        self._output = output
        self._requester = requester

        self._verify_ssl = remote.verify_ssl
        self._artifacts_properties = artifacts_properties
        self._revisions_enabled = config.revisions_enabled
        self._config = config

        # This dict is shared for all the instances of RestApiClient
        self._cached_capabilities = cached_capabilities

    def _capable(self, capability, user=None, password=None):
        capabilities = self._cached_capabilities.get(self._remote_url)
        if capabilities is None:
            tmp = RestV1Methods(self._remote_url, self._token, self._custom_headers, self._output,
                                self._requester, self._config, self._verify_ssl,
                                self._artifacts_properties)
            capabilities = tmp.server_capabilities(user, password)
            self._cached_capabilities[self._remote_url] = capabilities
            logger.debug("REST: Cached capabilities for the remote: %s" % capabilities)
            if not self._revisions_enabled and ONLY_V2 in capabilities:
                raise OnlyV2Available(self._remote_url)
        return capability in capabilities

    def _get_api(self):
        revisions = self._capable(REVISIONS)
        matrix_params = self._capable(MATRIX_PARAMS)
        if self._revisions_enabled and revisions:
            checksum_deploy = self._capable(CHECKSUM_DEPLOY)
            return RestV2Methods(self._remote_url, self._token, self._custom_headers, self._output,
                                 self._requester, self._config, self._verify_ssl,
                                 self._artifacts_properties, checksum_deploy, matrix_params)
        else:
            return RestV1Methods(self._remote_url, self._token, self._custom_headers, self._output,
                                 self._requester, self._config, self._verify_ssl,
                                 self._artifacts_properties, matrix_params)

    def get_recipe_manifest(self, ref):
        return self._get_api().get_recipe_manifest(ref)

    def get_package_manifest(self, pref):
        return self._get_api().get_package_manifest(pref)

    def get_package_info(self, pref, headers):
        return self._get_api().get_package_info(pref, headers=headers)

    def get_recipe(self, ref, dest_folder):
        return self._get_api().get_recipe(ref, dest_folder)

    def get_recipe_snapshot(self, ref):
        return self._get_api().get_recipe_snapshot(ref)

    def get_recipe_sources(self, ref, dest_folder):
        return self._get_api().get_recipe_sources(ref, dest_folder)

    def get_package(self, pref, dest_folder):
        return self._get_api().get_package(pref, dest_folder)

    def get_package_snapshot(self, ref):
        return self._get_api().get_package_snapshot(ref)

    def get_recipe_path(self, ref, path):
        return self._get_api().get_recipe_path(ref, path)

    def get_package_path(self, pref, path):
        return self._get_api().get_package_path(pref, path)

    def upload_recipe(self, ref, files_to_upload, deleted, retry, retry_wait):
        return self._get_api().upload_recipe(ref, files_to_upload, deleted, retry, retry_wait)

    def upload_package(self, pref, files_to_upload, deleted, retry, retry_wait):
        return self._get_api().upload_package(pref, files_to_upload, deleted, retry, retry_wait)

    def authenticate(self, user, password):
        api_v1 = RestV1Methods(self._remote_url, self._token, self._custom_headers, self._output,
                               self._requester, self._config, self._verify_ssl,
                               self._artifacts_properties)

        if self._refresh_token and self._token:
            token, refresh_token = api_v1.refresh_token(self._token, self._refresh_token)
        else:
            try:
                # Check capabilities can raise also 401 until the new Artifactory is released
                oauth_capable = self._capable(OAUTH_TOKEN, user, password)
            except AuthenticationException:
                oauth_capable = False

            if oauth_capable:
                # Artifactory >= 6.13.X
                token, refresh_token = api_v1.authenticate_oauth(user, password)
            else:
                token = api_v1.authenticate(user, password)
                refresh_token = None

        return token, refresh_token

    def check_credentials(self):
        return self._get_api().check_credentials()

    def search(self, pattern=None, ignorecase=True):
        return self._get_api().search(pattern, ignorecase)

    def search_packages(self, reference):
        return self._get_api().search_packages(reference)

    def remove_recipe(self, ref):
        return self._get_api().remove_conanfile(ref)

    def remove_packages(self, ref, package_ids=None):
        return self._get_api().remove_packages(ref, package_ids)

    def server_capabilities(self):
        return self._get_api().server_capabilities()

    def get_recipe_revisions(self, ref):
        return self._get_api().get_recipe_revisions(ref)

    def get_package_revisions(self, pref):
        return self._get_api().get_package_revisions(pref)

    def get_latest_recipe_revision(self, ref):
        return self._get_api().get_latest_recipe_revision(ref)

    def get_latest_package_revision(self, pref, headers):
        return self._get_api().get_latest_package_revision(pref, headers=headers)
