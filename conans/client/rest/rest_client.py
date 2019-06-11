from collections import defaultdict

from conans import CHECKSUM_DEPLOY, REVISIONS, ONLY_V2
from conans.client.rest.rest_client_v1 import RestV1Methods
from conans.client.rest.rest_client_v2 import RestV2Methods
from conans.errors import OnlyV2Available


class RestApiClient(object):
    """
        Rest Api Client for handle remote.
    """

    def __init__(self, output, requester, revisions_enabled, put_headers=None):

        # Set to instance
        self.token = None
        self.remote_url = None
        self.custom_headers = {}  # Can set custom headers to each request
        self._output = output
        self.requester = requester

        # Remote manager will set it to True or False dynamically depending on the remote
        self.verify_ssl = True
        self._put_headers = put_headers
        self._revisions_enabled = revisions_enabled

        self._cached_capabilities = defaultdict(list)

    def _get_api(self):
        if self.remote_url not in self._cached_capabilities:
            tmp = RestV1Methods(self.remote_url, self.token, self.custom_headers, self._output,
                                self.requester, self.verify_ssl, self._put_headers)
            _, _, cap = tmp.server_info()
            self._cached_capabilities[self.remote_url] = cap
            if not self._revisions_enabled and ONLY_V2 in cap:
                raise OnlyV2Available(self.remote_url)

        if self._revisions_enabled and REVISIONS in self._cached_capabilities[self.remote_url]:
            checksum_deploy = CHECKSUM_DEPLOY in self._cached_capabilities[self.remote_url]
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
        return self._get_api().authenticate(user, password)

    def check_credentials(self):
        return self._get_api().check_credentials()

    def search(self, pattern=None, ignorecase=True):
        return self._get_api().search(pattern, ignorecase)

    def search_packages(self, reference, query):
        return self._get_api().search_packages(reference, query)

    def remove_conanfile(self, ref):
        return self._get_api().remove_conanfile(ref)

    def remove_packages(self, ref, package_ids=None):
        return self._get_api().remove_packages(ref, package_ids)

    def server_info(self):
        return self._get_api().server_info()

    def get_recipe_revisions(self, ref):
        return self._get_api().get_recipe_revisions(ref)

    def get_package_revisions(self, pref):
        return self._get_api().get_package_revisions(pref)

    def get_latest_recipe_revision(self, ref):
        return self._get_api().get_latest_recipe_revision(ref)

    def get_latest_package_revision(self, pref):
        return self._get_api().get_latest_package_revision(pref)
