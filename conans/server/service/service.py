import re
from fnmatch import translate

from conans.errors import RequestErrorException, NotFoundException, ForbiddenException, \
    ConanException
import os
import jwt
from conans.util.files import mkdir, list_folder_subdirs
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.log import logger
from conans.search.search import search_packages, _partial_match


class FileUploadDownloadService(object):
    """Handles authorization from token and upload and download files"""

    def __init__(self, updown_auth_manager, base_store_folder):
        self.updown_auth_manager = updown_auth_manager
        self.base_store_folder = base_store_folder

    def get_file_path(self, filepath, token):
        try:
            encoded_path, _, user = self.updown_auth_manager.get_resource_info(token)
            if not self._valid_path(filepath, encoded_path):
                logger.info("Invalid path file!! %s: %s" % (user, filepath))
                raise NotFoundException("File not found")
            logger.debug("Get file: user=%s path=%s" % (user, filepath))
            file_path = os.path.normpath(os.path.join(self.base_store_folder, encoded_path))
            return file_path
        except (jwt.ExpiredSignature, jwt.DecodeError, AttributeError):
            raise NotFoundException("File not found")

    def put_file(self, file_saver, abs_filepath, token, upload_size):
        """
        file_saver is an object with the save() method without parameters
        """
        try:
            encoded_path, filesize, user = self.updown_auth_manager.get_resource_info(token)
            # Check size
            if upload_size != filesize:
                logger.debug("Invalid size file!!: %s: %s" % (user, abs_filepath))
                raise RequestErrorException("Bad file size")

            abs_encoded_path = os.path.abspath(os.path.join(self.base_store_folder, encoded_path))
            if not self._valid_path(abs_filepath, abs_encoded_path):
                raise NotFoundException("File not found")
            logger.debug("Put file: %s: %s" % (user, abs_filepath))
            mkdir(os.path.dirname(abs_filepath))
            if os.path.exists(abs_filepath):
                os.remove(abs_filepath)
            file_saver.save(os.path.dirname(abs_filepath))

        except (jwt.ExpiredSignature, jwt.DecodeError, AttributeError):
            raise NotFoundException("File not found")

    def _valid_path(self, filepath, encoded_path):
        if encoded_path == filepath:
            path = os.path.join(self.base_store_folder, encoded_path)
            path = os.path.normpath(path)
            # Protect from path outside storage "../.."
            if not path.startswith(self.base_store_folder):
                return False
            return True
        else:
            return False


class SearchService(object):

    def __init__(self, authorizer, server_store, auth_user):
        self._authorizer = authorizer
        self._server_store = server_store
        self._auth_user = auth_user

    def search_packages(self, reference, query):
        self._authorizer.check_read_conan(self._auth_user, reference)
        info = search_packages(self._server_store, reference, query)
        return info

    def search_recipes(self, pattern=None, ignorecase=True):

        def get_ref(_pattern):
            if not isinstance(_pattern, ConanFileReference):
                try:
                    r = ConanFileReference.loads(_pattern)
                except (ConanException, TypeError):
                    r = None
            else:
                r = _pattern
            return r

        def get_folders_levels(_pattern):
            """If a reference with revisions is detected compare with 5 levels of subdirs"""
            r = get_ref(_pattern)
            return 5 if r and r.revision else 4

        # Check directly if it is a reference
        ref = get_ref(pattern)
        if ref:
            # Avoid resolve latest revision if a version range is passed or we are performing a
            # package remove (all revisions)
            path = self._server_store.conan(ref, resolve_latest=False)
            if self._server_store.path_exists(path):
                return [ref]

        # Conan references in main storage
        if pattern:
            pattern = str(pattern)
            b_pattern = translate(pattern)
            b_pattern = re.compile(b_pattern, re.IGNORECASE) if ignorecase else re.compile(b_pattern)

        subdirs = list_folder_subdirs(basedir=self._server_store.store, level=get_folders_levels(pattern))
        if not pattern:
            return sorted([ConanFileReference(*folder.split("/")) for folder in subdirs])
        else:
            ret = []
            for subdir in subdirs:
                conan_ref = ConanFileReference(*subdir.split("/"))
                if _partial_match(b_pattern, conan_ref):
                    ret.append(conan_ref)

            return sorted(ret)

    def search(self, pattern=None, ignorecase=True):
        """ Get all the info about any package
            Attributes:
                pattern = wildcards like opencv/*
        """
        references = self.search_recipes(pattern, ignorecase)
        filtered = []
        # Filter out restricted items
        for conan_ref in references:
            try:
                self._authorizer.check_read_conan(self._auth_user, conan_ref)
                filtered.append(conan_ref)
            except ForbiddenException:
                pass
        return filtered


class ConanService(object):
    """Handles authorization and expose methods for REST API"""

    def __init__(self, authorizer, server_store, auth_user):

        self._authorizer = authorizer
        self._server_store = server_store
        self._auth_user = auth_user

    def get_recipe_snapshot(self, reference):
        """Gets a dict with filepaths and the md5:
            {filename: md5}
        """
        self._authorizer.check_read_conan(self._auth_user, reference)
        snap = self._server_store.get_recipe_snapshot(reference)
        if not snap:
            raise NotFoundException("conanfile not found")
        return snap

    def get_conanfile_download_urls(self, reference, files_subset=None):
        """Gets a dict with filepaths and the urls:
            {filename: url}
        """
        self._authorizer.check_read_conan(self._auth_user, reference)
        urls = self._server_store.get_download_conanfile_urls(reference,
                                                              files_subset,
                                                              self._auth_user)
        if not urls:
            raise NotFoundException("conanfile not found")
        return urls

    def get_conanfile_upload_urls(self, reference, filesizes):
        _validate_conan_reg_filenames(list(filesizes.keys()))
        self._authorizer.check_write_conan(self._auth_user, reference)
        urls = self._server_store.get_upload_conanfile_urls(reference,
                                                            filesizes,
                                                            self._auth_user)
        return urls

    def remove_conanfile(self, reference):
        self._authorizer.check_delete_conan(self._auth_user, reference)
        self._server_store.remove_conanfile(reference)

    def remove_packages(self, reference, package_ids_filter):
        for package_id in package_ids_filter:
            ref = PackageReference(reference, package_id)
            self._authorizer.check_delete_package(self._auth_user, ref)
        if not package_ids_filter:  # Remove all packages, check that we can remove conanfile
            self._authorizer.check_delete_conan(self._auth_user, reference)

        self._server_store.remove_packages(reference, package_ids_filter)

    def remove_conanfile_files(self, reference, files):
        self._authorizer.check_delete_conan(self._auth_user, reference)
        self._server_store.remove_conanfile_files(reference, files)

    # Package methods
    def get_package_snapshot(self, package_reference):
        """Gets a list with filepaths and the urls and md5:
            [filename: {'url': url, 'md5': md5}]
        """
        self._authorizer.check_read_package(self._auth_user, package_reference)
        snap = self._server_store.get_package_snapshot(package_reference)
        return snap

    def get_package_download_urls(self, package_reference, files_subset=None):
        """Gets a list with filepaths and the urls and md5:
            [filename: {'url': url, 'md5': md5}]
        """
        self._authorizer.check_read_package(self._auth_user, package_reference)
        urls = self._server_store.get_download_package_urls(package_reference,
                                                            files_subset=files_subset)
        return urls

    def get_package_upload_urls(self, package_reference, filesizes):
        """
        :param package_reference: PackageReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        try:
            self._server_store.get_recipe_snapshot(package_reference.conan)
        except NotFoundException:
            raise NotFoundException("There are no remote conanfiles like %s"
                                    % str(package_reference.conan))
        self._authorizer.check_write_package(self._auth_user, package_reference)
        urls = self._server_store.get_upload_package_urls(package_reference,
                                                          filesizes, self._auth_user)
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
