from collections import defaultdict

from conans.client.rest.rest_client_v1 import RestV1Methods


class RestApiClient(object):
    """
        Rest Api Client for handle remote.
    """

    def __init__(self, output, requester, put_headers=None):

        # Set to instance
        self.token = None
        self.remote_url = None
        self.custom_headers = {}  # Can set custom headers to each request
        self._output = output
        self.requester = requester
        # Remote manager will set it to True or False dynamically depending on the remote
        self.verify_ssl = True
        self._put_headers = put_headers

        self._capabilities = defaultdict(list)

    def _get_api(self):
        if self.remote_url not in self._capabilities:
            tmp = RestV1Methods(self.remote_url, self.token, self.custom_headers, self._output,
                                self.requester, self.verify_ssl, self._put_headers)
            _, _, cap = tmp.server_info()
            self._capabilities[self.remote_url] = cap

        # FIXME: ONLY CONNECT TO APIV2 THE CLIENT WHEN THE PROTOCOL IS STABLE
        # from conans import API_V2, CHECKSUM_DEPLOY
        # from conans.client.rest.rest_client_v2 import RestV2Methods
        #if API_V2 in self._capabilities[self.remote_url]:
        #    checksum_deploy = CHECKSUM_DEPLOY in self._capabilities[self.remote_url]
        #    return RestV2Methods(self.remote_url, self.token, self.custom_headers, self._output,
        #                         self.requester, self.verify_ssl, self._put_headers,
        #                         checksum_deploy)
        #else:
        return RestV1Methods(self.remote_url, self.token, self.custom_headers, self._output,
                             self.requester, self.verify_ssl, self._put_headers)

    def get_conan_manifest(self, conan_reference):
        return self._get_api().get_conan_manifest(conan_reference)

    def get_package_manifest(self, package_reference):
        return self._get_api().get_package_manifest(package_reference)

    def get_package_info(self, package_reference):
        return self._get_api().get_package_info(package_reference)

    def get_recipe(self, conan_reference, dest_folder):
        return self._get_api().get_recipe(conan_reference, dest_folder)

    def get_recipe_sources(self, conan_reference, dest_folder):
        return self._get_api().get_recipe_sources(conan_reference, dest_folder)

    def get_package(self, package_reference, dest_folder):
        return self._get_api().get_package(package_reference, dest_folder)

    def get_path(self, conan_reference, package_id, path):
        return self._get_api().get_path(conan_reference, package_id, path)

    def upload_recipe(self, conan_reference, the_files, retry, retry_wait, policy, remote_manifest):
        return self._get_api().upload_recipe(conan_reference, the_files, retry, retry_wait,
                                             policy, remote_manifest)

    def upload_package(self, package_reference, the_files, retry, retry_wait, no_overwrite):
        return self._get_api().upload_package(package_reference, the_files, retry, retry_wait,
                                              no_overwrite)

    def authenticate(self, user, password):
        return self._get_api().authenticate(user, password)

    def check_credentials(self):
        return self._get_api().check_credentials()

    def search(self, pattern=None, ignorecase=True):
        return self._get_api().search(pattern, ignorecase)

    def search_packages(self, reference, query):
        return self._get_api().search_packages(reference, query)

    def remove_conanfile(self, conan_reference):
        return self._get_api().remove_conanfile(conan_reference)

    def remove_packages(self, conan_reference, package_ids=None):
        return self._get_api().remove_packages(conan_reference, package_ids)

    def server_info(self):
        return self._get_api().server_info()
