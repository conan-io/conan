import os

from conans.errors import ConanException
from conans.util.log import logger
from conans.model.ref import PackageReference
from conans.paths import SYSTEM_REQS, rm_conandir
from conans.model.ref import ConanFileReference


class DiskRemover(object):
    def __init__(self, paths):
        self._paths = paths

    def _remove(self, path, conan_ref, msg=""):
        try:
            logger.debug("Removing folder %s" % path)
            rm_conandir(path)
        except OSError:
            error_msg = "Folder busy (open or some file open): %s" % path
            raise ConanException("%s: Unable to remove %s\n\t%s"
                                 % (repr(conan_ref), msg, error_msg))

    def _remove_file(self, path, conan_ref, msg=""):
        try:
            logger.debug("Removing folder %s" % path)
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            error_msg = "File busy (open): %s" % path
            raise ConanException("Unable to remove %s %s\n\t%s"
                                 % (repr(conan_ref), msg, error_msg))

    def remove(self, conan_ref):
        self.remove_src(conan_ref)
        self.remove_builds(conan_ref)
        self.remove_packages(conan_ref)
        self._remove(self._paths.conan(conan_ref), conan_ref)

    def remove_src(self, conan_ref):
        self._remove(self._paths.source(conan_ref), conan_ref, "src folder")

    def remove_builds(self, conan_ref, ids=None):
        if not ids:
            path = self._paths.builds(conan_ref)
            for build in self._paths.conan_builds(conan_ref):
                self._remove(os.path.join(path, build), conan_ref, "build folder:%s" % build)
            self._remove(path, conan_ref, "builds")
        else:
            for id_ in ids:
                self._remove(self._paths.build(PackageReference(conan_ref, id_)), conan_ref,
                             "package:%s" % id_)

    def remove_packages(self, conan_ref, ids_filter=None):
        if not ids_filter:  # Remove all
            path = self._paths.packages(conan_ref)
            for package in self._paths.conan_packages(conan_ref):
                self._remove(os.path.join(path, package), conan_ref, "package folder:%s" % package)
            self._remove(path, conan_ref, "packages")
            self._remove_file(self._paths.system_reqs(conan_ref), conan_ref, SYSTEM_REQS)
        else:
            for id_ in ids_filter:  # remove just the specified packages
                package_ref = PackageReference(conan_ref, id_)
                self._remove(self._paths.package(package_ref), conan_ref, "package:%s" % id_)
                self._remove_file(self._paths.system_reqs_package(package_ref),
                                  conan_ref, "%s/%s" % (id_, SYSTEM_REQS))


class ConanRemover(object):
    """ Class responsible for removing locally/remotely conans, package folders, etc. """

    def __init__(self, client_cache, search_manager, user_io, remote_proxy):
        self._user_io = user_io
        self._remote_proxy = remote_proxy
        self._client_cache = client_cache
        self._search_manager = search_manager

    def remove(self, pattern, src=None, build_ids=None, package_ids_filter=None, force=False):
        """ Remove local/remote conans, package folders, etc.
        @param pattern: it could be OpenCV* or OpenCV
        @param package_ids_filter: Lists with ids or empty for all. (Its a filter)
        @param force: if True, it will be deleted without requesting anything
        """

        has_remote = self._remote_proxy._remote_name
        if has_remote:
            if build_ids is not None or src:
                raise ConanException("Remotes don't have 'build' or 'src' folder, just packages")
            search_info = self._remote_proxy.search(pattern)
        else:
            search_info = self._search_manager.search(pattern)

        if not search_info:
            self._user_io.out.warn("No package recipe reference matches with %s pattern" % pattern)
            return

        deleted_refs = []
        for conan_ref in search_info:
            assert(isinstance(conan_ref, ConanFileReference))
            if self._ask_permission(conan_ref, src, build_ids, package_ids_filter, force):
                if has_remote:
                    if package_ids_filter is None:
                        self._remote_proxy.remove(conan_ref)
                    else:
                        self._remote_proxy.remove_packages(conan_ref, package_ids_filter)
                else:
                    deleted_refs.append(conan_ref)
                    remover = DiskRemover(self._client_cache)
                    if src:
                        remover.remove_src(conan_ref)
                    if build_ids is not None:
                        remover.remove_builds(conan_ref, build_ids)
                    if package_ids_filter is not None:
                        remover.remove_packages(conan_ref, package_ids_filter)
                    if not src and build_ids is None and package_ids_filter is None:
                        remover.remove(conan_ref)
                        registry = self._remote_proxy.registry
                        registry.remove_ref(conan_ref, quiet=True)

        if not has_remote:
            self._client_cache.delete_empty_dirs(deleted_refs)

    def _ask_permission(self, conan_ref, src, build_ids, package_ids_filter, force):
        if force:
            return True
        aux_str = []
        if src:
            aux_str.append(" src folder")
        if build_ids is not None:
            if build_ids:
                aux_str.append(" %s builds" % build_ids)
            else:
                aux_str.append(" all builds")
        if package_ids_filter is not None:
            if package_ids_filter:
                aux_str.append(" %s package" % package_ids_filter)
            else:  # All packages to remove, no filter
                aux_str.append(" all packages")
        return self._user_io.request_boolean("Are you sure you want to delete%s from '%s'"
                                             % (", ".join(aux_str), str(conan_ref)))
