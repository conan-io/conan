from conans import CHECKSUM_DEPLOY, REVISIONS, ONLY_V2, OAUTH_TOKEN
from conans.client.rest.rest_client_v1 import RestV1Methods
from conans.client.rest.rest_client_v2 import RestV2Methods
from conans.errors import OnlyV2Available
from conans.search.search import filter_packages
from conans.util.log import logger


class RestApiClient(object):
    """
        Rest Api Client for handle remote.
    """

    def __init__(self, output, requester, revisions_enabled, put_headers=None):

        # Set to instance
        self.token = None
        self.refresh_token = None
        self.remote_url = None
        self.custom_headers = {}  # Can set custom headers to each request
        self._output = output
        self.requester = requester

        # Remote manager will set it to True or False dynamically depending on the remote
        self.verify_ssl = True
        self._put_headers = put_headers
        self._revisions_enabled = revisions_enabled

        self._cached_capabilities = {}

    def _get_api(self):
        if self.remote_url not in self._cached_capabilities:
            tmp = RestV1Methods(self.remote_url, self.token, self.custom_headers, self._output,
                                self.requester, self.verify_ssl, self._put_headers)
            cap = tmp.server_capabilities()
            self._cached_capabilities[self.remote_url] = cap
            logger.debug("REST: Cached capabilities for the remote: %s" % cap)
            if not self._revisions_enabled and ONLY_V2 in cap:
                raise OnlyV2Available(self.remote_url)

        if self._revisions_enabled and REVISIONS in self._cached_capabilities.get(self.remote_url,
                                                                                  []):
            checksum_deploy = CHECKSUM_DEPLOY in self._cached_capabilities.get(self.remote_url, [])
            return RestV2Methods(self.remote_url, self.token, self.custom_headers, self._output,
                                 self.requester, self.verify_ssl, self._put_headers,
                                 checksum_deploy)
        else:
            return RestV1Methods(self.remote_url, self.token, self.custom_headers, self._output,
                                 self.requester, self.verify_ssl, self._put_headers)

    def get_recipe_manifest(self, ref):
        return self._get_api().get_recipe_manifest(ref)

    def get_package_manifest(self, pref):
        return self._get_api().get_package_manifest(pref)

    def get_package_info(self, pref):
        return self._get_api().get_package_info(pref)

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
        return self._get_api().upload_recipe(ref, files_to_upload, deleted, retry,
                                             retry_wait)

    def upload_package(self, pref, files_to_upload, deleted, retry, retry_wait):
        return self._get_api().upload_package(pref, files_to_upload, deleted, retry, retry_wait)

    def authenticate(self, user, password):
        api_v1 = RestV1Methods(self.remote_url, self.token, self.custom_headers, self._output,
                               self.requester, self.verify_ssl, self._put_headers)

        if self.refresh_token and self.token:
            token, refresh_token = api_v1.refresh_token(self.token, self.refresh_token)
        else:
            if OAUTH_TOKEN in self._cached_capabilities.get(self.remote_url, []):
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

    def search_packages(self, reference, query):
        # Do not send the query to the server, as it will fail
        # https://github.com/conan-io/conan/issues/4951
        package_infos = self._get_api().search_packages(reference, query=None)
        return filter_packages(query, package_infos)

    def remove_conanfile(self, ref):
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

    def get_latest_package_revision(self, pref):
        return self._get_api().get_latest_package_revision(pref)
