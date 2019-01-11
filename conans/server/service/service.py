import os
import re
from fnmatch import translate

import jwt

from conans import load
from conans.errors import ConanException, ForbiddenException, NotFoundException, \
    RequestErrorException
from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANINFO
from conans.search.search import _partial_match, filter_packages
from conans.util.files import list_folder_subdirs, mkdir
from conans.util.log import logger


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

    def search_packages(self, reference, query, v2_compatibility_mode):
        self._authorizer.check_read_conan(self._auth_user, reference)
        info = search_packages(self._server_store, reference, query, v2_compatibility_mode)
        return info

    def search_recipes(self, pattern=None, ignorecase=True):

        def get_ref(_pattern):
            if not isinstance(_pattern, ConanFileReference):
                try:
                    ref_ = ConanFileReference.loads(_pattern)
                except (ConanException, TypeError):
                    ref_ = None
            else:
                ref_ = _pattern
            return ref_

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

        subdirs = list_folder_subdirs(basedir=self._server_store.store, level=5)
        if not pattern:
            return sorted([ConanFileReference(*folder.split("/")) for folder in subdirs])
        else:
            ret = []
            for subdir in subdirs:
                ref = ConanFileReference(*subdir.split("/"))
                if _partial_match(b_pattern, ref):
                    ret.append(ref)

            return sorted(ret)

    def search(self, pattern=None, ignorecase=True):
        """ Get all the info about any package
            Attributes:
                pattern = wildcards like opencv/*
        """
        refs = self.search_recipes(pattern, ignorecase)
        filtered = []
        # Filter out restricted items
        for ref in refs:
            try:
                self._authorizer.check_read_conan(self._auth_user, ref)
                filtered.append(ref)
            except ForbiddenException:
                pass
        return filtered


class ConanService(object):
    """Handles authorization and expose methods for REST API"""

    def __init__(self, authorizer, server_store, auth_user):

        self._authorizer = authorizer
        self._server_store = server_store
        self._auth_user = auth_user

    def get_recipe_snapshot(self, ref):
        """Gets a dict with filepaths and the md5:
            {filename: md5}
        """
        self._authorizer.check_read_conan(self._auth_user, ref)
        snap = self._server_store.get_recipe_snapshot(ref)
        if not snap:
            raise NotFoundException("conanfile not found")
        return snap

    def get_conanfile_download_urls(self, ref, files_subset=None):
        """Gets a dict with filepaths and the urls:
            {filename: url}
        """
        self._authorizer.check_read_conan(self._auth_user, ref)
        urls = self._server_store.get_download_conanfile_urls(ref, files_subset, self._auth_user)
        if not urls:
            raise NotFoundException("conanfile not found")
        return urls

    def get_conanfile_upload_urls(self, ref, filesizes):
        _validate_conan_reg_filenames(list(filesizes.keys()))
        self._authorizer.check_write_conan(self._auth_user, ref)
        urls = self._server_store.get_upload_conanfile_urls(ref, filesizes, self._auth_user)
        return urls

    def remove_conanfile(self, ref):
        self._authorizer.check_delete_conan(self._auth_user, ref)
        self._server_store.remove_conanfile(ref)

    def remove_packages(self, ref, package_ids_filter):
        """If the revision is not specified it will remove the packages from all the recipes
        (v1 compatibility)"""
        for package_id in package_ids_filter:
            pref = PackageReference(ref, package_id)
            self._authorizer.check_delete_package(self._auth_user, pref)
        if not package_ids_filter:  # Remove all packages, check that we can remove conanfile
            self._authorizer.check_delete_conan(self._auth_user, ref)

        if ref.revision:
            references = [ref]
        else:
            references = self._server_store.get_recipe_revisions(ref)

        for ref in references:
            self._server_store.remove_packages(ref, package_ids_filter)

    def remove_package(self, pref):
        self._authorizer.check_delete_package(self._auth_user, pref)

        if not pref.ref.revision:
            recipe_revisions = self._server_store.get_recipe_revisions(pref.ref)
        else:
            recipe_revisions = [pref.ref, ]

        for ref in recipe_revisions:
            if not pref.revision:
                pref = PackageReference(ref, pref.id)
                package_revisions = [r.revision
                                     for r in self._server_store.get_package_revisions(pref)]
            else:
                package_revisions = [pref.revision]

            for prev in package_revisions:
                full_pref = PackageReference(ref, pref.id, prev)
                self._server_store.remove_package(full_pref)

    def remove_all_packages(self, ref):
        if ref.revision:
            refs = [ref]
        else:
            refs = self._server_store.get_recipe_revisions(ref)
        for ref in refs:
            self._server_store.remove_all_packages(ref)

    def remove_conanfile_files(self, ref, files):
        self._authorizer.check_delete_conan(self._auth_user, ref)
        self._server_store.remove_conanfile_files(ref, files)

    def remove_conanfile_file(self, ref, path):
        self.remove_conanfile_files(ref, [path])

    # Package methods
    def get_package_snapshot(self, pref):
        """Gets a list with filepaths and the urls and md5:
            [filename: {'url': url, 'md5': md5}]
        """
        self._authorizer.check_read_package(self._auth_user, pref)
        snap = self._server_store.get_package_snapshot(pref)
        return snap

    def get_package_download_urls(self, pref, files_subset=None):
        """Gets a list with filepaths and the urls and md5:
            [filename: {'url': url, 'md5': md5}]
        """
        self._authorizer.check_read_package(self._auth_user, pref)
        urls = self._server_store.get_download_package_urls(pref, files_subset=files_subset)
        return urls

    def get_package_upload_urls(self, pref, filesizes):
        """
        :param pref: PackageReference
        :param filesizes: {filepath: bytes}
        :return {filepath: url} """
        try:
            self._server_store.get_recipe_snapshot(pref.ref)
        except NotFoundException:
            raise NotFoundException("There are no remote conanfiles like %s" % str(pref.ref))
        self._authorizer.check_write_package(self._auth_user, pref)
        urls = self._server_store.get_upload_package_urls(pref, filesizes, self._auth_user)
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


def search_packages(paths, ref, query, v2_compatibility_mode):
    """ Return a dict like this:

            {package_ID: {name: "OpenCV",
                           version: "2.14",
                           settings: {os: Windows}}}
    param ref: ConanFileReference object
    """
    if not os.path.exists(paths.conan(ref)):
        raise NotFoundException("Recipe not found: %s" % str(ref))
    infos = _get_local_infos_min(paths, ref, v2_compatibility_mode)
    return filter_packages(query, infos)


def _get_local_infos_min(paths, ref, v2_compatibility_mode=False):

    result = {}

    if not ref.revision and v2_compatibility_mode:
        recipe_revisions = paths.get_recipe_revisions(ref)
    else:
        recipe_revisions = [ref]

    for recipe_revision in recipe_revisions:
        packages_path = paths.packages(recipe_revision)
        subdirs = list_folder_subdirs(packages_path, level=1)
        for package_id in subdirs:
            if package_id in result:
                continue
            # Read conaninfo
            try:
                pref = PackageReference(ref, package_id)
                info_path = os.path.join(paths.package(pref, short_paths=None), CONANINFO)
                if not os.path.exists(info_path):
                    raise NotFoundException("")
                conan_info_content = load(info_path)
                info = ConanInfo.loads(conan_info_content)
                conan_vars_info = info.serialize_min()
                result[package_id] = conan_vars_info

            except Exception as exc:  # FIXME: Too wide
                logger.error("Package %s has no ConanInfo file" % str(pref))
                if str(exc):
                    logger.error(str(exc))
    return result
