import os

from conans.errors import ConanException
from conans.util.log import logger
from conans.model.ref import PackageReference
from conans.paths import SYSTEM_REQS, rm_conandir
from conans.model.ref import ConanFileReference
from conans.search.search import filter_outdated, DiskSearchManager
from conans.client.remote_registry import RemoteRegistry


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
        self._remove(self._paths.export(conan_ref), conan_ref, "export folder")
        self._remove(self._paths.export_sources(conan_ref), conan_ref, "export_source folder")
        self._remove(self._paths.conan(conan_ref), conan_ref)
        for f in self._paths.conanfile_lock_files(conan_ref):
            try:
                os.remove(f)
            except OSError:
                pass

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
                # Removal build IDs should be those of the build_id if present
                pkg_path = self._paths.build(PackageReference(conan_ref, id_))
                self._remove(pkg_path, conan_ref, "package:%s" % id_)

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

    def __init__(self, client_cache, remote_manager, user_io, remote_proxy):
        self._user_io = user_io
        self._remote_proxy = remote_proxy
        self._client_cache = client_cache
        self._remote_manager = remote_manager

    def _remote_remove(self, reference, package_ids):
        if package_ids is None:
            self._remote_proxy.remove(reference)
        else:
            self._remote_proxy.remove_packages(reference, package_ids)

    def _local_remove(self, reference, src, build_ids, package_ids):
        remover = DiskRemover(self._client_cache)
        if src:
            remover.remove_src(reference)
        if build_ids is not None:
            remover.remove_builds(reference, build_ids)
        if package_ids is not None:
            remover.remove_packages(reference, package_ids)
        if not src and build_ids is None and package_ids is None:
            remover.remove(reference)
            registry = self._remote_proxy.registry
            registry.remove_ref(reference, quiet=True)

    def remove(self, pattern, remote, src=None, build_ids=None, package_ids_filter=None, force=False,
               packages_query=None, outdated=False):
        """ Remove local/remote conans, package folders, etc.
        @param src: Remove src folder
        @param pattern: it could be OpenCV* or OpenCV or a ConanFileReference
        @param build_ids: Lists with ids or empty for all. (Its a filter)
        @param package_ids_filter: Lists with ids or empty for all. (Its a filter)
        @param force: if True, it will be deleted without requesting anything
        @param packages_query: Only if src is a reference. Query settings and options
        """

        if remote and (build_ids is not None or src):
            raise ConanException("Remotes don't have 'build' or 'src' folder, just packages")

        if remote:
            remote = RemoteRegistry(self._client_cache.registry, self._user_io.out).remote(remote)
            references = self._remote_manager.search_recipes(remote, pattern)
        else:
            disk_search = DiskSearchManager(self._client_cache)
            references = disk_search.search_recipes(pattern)
        if not references:
            self._user_io.out.warn("No package recipe matches '%s'" % str(pattern))
            return

        deleted_refs = []
        for reference in references:
            assert isinstance(reference, ConanFileReference)
            package_ids = package_ids_filter
            if packages_query or outdated:
                # search packages
                if remote:
                    packages = self._remote_manager.search_packages(remote, reference, packages_query)
                else:
                    packages = disk_search.search_packages(reference, packages_query)
                if outdated:
                    if remote:
                        recipe_hash = self._remote_proxy.get_conan_digest(reference).summary_hash
                    else:
                        recipe_hash = self._client_cache.load_manifest(reference).summary_hash
                    packages = filter_outdated(packages, recipe_hash)
                if package_ids_filter:
                    package_ids = [p for p in packages if p in package_ids_filter]
                else:
                    package_ids = list(packages.keys())
                if not package_ids:
                    self._user_io.out.warn("No matching packages to remove for %s"
                                           % str(reference))
                    continue

            if self._ask_permission(reference, src, build_ids, package_ids, force):
                deleted_refs.append(reference)
                if remote:
                    self._remote_remove(reference, package_ids)
                else:
                    deleted_refs.append(reference)
                    self._local_remove(reference, src, build_ids, package_ids)

        if not remote:
            self._client_cache.delete_empty_dirs(deleted_refs)

    def _ask_permission(self, conan_ref, src, build_ids, package_ids_filter, force):
        def stringlist(alist):
            return ", ".join(['"%s"' % p for p in alist])

        if force:
            return True
        aux_str = []
        if src:
            aux_str.append(" src folder")
        if build_ids is not None:
            if build_ids:
                aux_str.append(" %s builds" % stringlist(build_ids))
            else:
                aux_str.append(" all builds")
        if package_ids_filter is not None:
            if package_ids_filter:
                aux_str.append(" %s packages" % stringlist(package_ids_filter))
            else:  # All packages to remove, no filter
                aux_str.append(" all packages")
        return self._user_io.request_boolean("Are you sure you want to delete%s from '%s'"
                                             % (", ".join(aux_str), str(conan_ref)))
