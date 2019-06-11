from conans.errors import NotFoundException, RequestErrorException, RecipeNotFoundException, \
    PackageNotFoundException
from conans.server.service.common.common import CommonService


class ConanService(CommonService):
    """Handles authorization and expose methods for REST API"""

    def __init__(self, authorizer, server_store, auth_user):

        self._authorizer = authorizer
        self._server_store = server_store
        self._auth_user = auth_user

    def get_recipe_snapshot(self, ref):
        """Gets a dict with file paths and the md5:
            {filename: md5}
        """
        self._authorizer.check_read_conan(self._auth_user, ref)
        latest_ref = self._get_latest_ref(ref)
        snap = self._server_store.get_recipe_snapshot(latest_ref)
        if not snap:
            raise RecipeNotFoundException(latest_ref)
        return snap

    def get_conanfile_download_urls(self, ref, files_subset=None):
        """Gets a dict with filepaths and the urls:
            {filename: url}
        """
        self._authorizer.check_read_conan(self._auth_user, ref)
        latest_ref = self._get_latest_ref(ref)
        urls = self._server_store.get_download_conanfile_urls(latest_ref,
                                                              files_subset, self._auth_user)
        if not urls:
            raise RecipeNotFoundException(latest_ref)
        return urls

    def get_conanfile_upload_urls(self, ref, filesizes):
        _validate_conan_reg_filenames(list(filesizes.keys()))
        self._authorizer.check_write_conan(self._auth_user, ref)
        latest_ref = self._get_latest_ref(ref)
        urls = self._server_store.get_upload_conanfile_urls(latest_ref, filesizes, self._auth_user)
        return urls

    # Package methods
    def get_package_snapshot(self, pref):
        """Gets a list with filepaths and the urls and md5:
            [filename: {'url': url, 'md5': md5}]
        """
        self._authorizer.check_read_package(self._auth_user, pref)
        pref = self._get_latest_pref(pref)
        snap = self._server_store.get_package_snapshot(pref)
        return snap

    def get_package_download_urls(self, pref, files_subset=None):
        """Gets a list with filepaths and the urls and md5:
            [filename: {'url': url, 'md5': md5}]
        """
        new_pref = self._get_latest_pref(pref)
        self._authorizer.check_read_package(self._auth_user, new_pref)
        urls = self._server_store.get_download_package_urls(new_pref, files_subset=files_subset)
        return urls

    def get_package_upload_urls(self, pref, filesizes):
        """
        :param pref: PackageReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        new_pref = self._get_latest_pref(pref)
        try:
            self._server_store.get_recipe_snapshot(new_pref.ref)
        except NotFoundException:
            raise PackageNotFoundException(new_pref)
        self._authorizer.check_write_package(self._auth_user, new_pref)
        urls = self._server_store.get_upload_package_urls(new_pref, filesizes, self._auth_user)
        return urls


def _validate_conan_reg_filenames(files):
    message = "Invalid conans request"

# Could be partial uploads, so we can't expect for all files to be present
#     # conanfile and digest in files
#     if CONANFILE not in files:
#         # Log something
#         raise RequestErrorException("Missing %s" % CONANFILE)
#     if CONAN_MANIFEST not in files:
#         # Log something
#         raise RequestErrorException("Missing %s" % CONAN_MANIFEST)

    # All contents in same directory (from conan_id)
    for filename in files:
        if ".." in filename:
            # Log something
            raise RequestErrorException(message)
