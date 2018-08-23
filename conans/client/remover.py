import os

from conans.client.remote_registry import Remote
from conans.errors import ConanException
from conans.util.log import logger
from conans.model.ref import PackageReference
from conans.paths import SYSTEM_REQS, rm_conandir
from conans.model.ref import ConanFileReference
from conans.search.search import filter_outdated, search_recipes,\
    search_packages


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
            logger.debug("Removing file %s" % path)
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            error_msg = "File busy (open): %s" % path
            raise ConanException("Unable to remove %s %s\n\t%s"
                                 % (repr(conan_ref), msg, error_msg))

    def remove_recipe(self, conan_ref):
        self.remove_src(conan_ref)
        self._remove(self._paths.export(conan_ref), conan_ref, "export folder")
        self._remove(self._paths.export_sources(conan_ref), conan_ref, "export_source folder")
        for f in self._paths.conanfile_lock_files(conan_ref):
            try:
                os.remove(f)
            except OSError:
                pass

    def remove(self, conan_ref):
        self.remove_recipe(conan_ref)
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
                # Removal build IDs should be those of the build_id if present
                pkg_path = self._paths.build(PackageReference(conan_ref, id_))
                self._remove(pkg_path, conan_ref, "package:%s" % id_)

    def remove_packages(self, conan_ref, ids_filter=None):
        if not ids_filter:  # Remove all
            path = self._paths.packages(conan_ref)
            # Necessary for short_paths removal
            for package in self._paths.conan_packages(conan_ref):
                self._remove(os.path.join(path, package), conan_ref, "package folder:%s" % package)
            self._remove(path, conan_ref, "packages")
            self._remove_file(self._paths.system_reqs(conan_ref), conan_ref, SYSTEM_REQS)
        else:
            for id_ in ids_filter:  # remove just the specified packages
                package_ref = PackageReference(conan_ref, id_)
                pkg_folder = self._paths.package(package_ref)
                self._remove(pkg_folder, conan_ref, "package:%s" % id_)
                self._remove_file(pkg_folder + ".dirty", conan_ref, "dirty flag")
                self._remove_file(self._paths.system_reqs_package(package_ref),
                                  conan_ref, "%s/%s" % (id_, SYSTEM_REQS))


class ConanRemover(object):
    """ Class responsible for removing locally/remotely conans, package folders, etc. """

    def __init__(self, client_cache, remote_manager, user_io, remote_registry):
        self._user_io = user_io
        self._client_cache = client_cache
        self._remote_manager = remote_manager
        self._registry = remote_registry

    def _remote_remove(self, reference, package_ids, remote):
        assert(isinstance(remote, Remote))
        if package_ids is None:
            result = self._remote_manager.remove(reference, remote)
            current_remote = self._registry.get_recipe_remote(reference)
            if current_remote == remote:
                self._registry.remove_ref(reference)
            return result
        else:
            return self._remote_manager.remove_packages(reference, package_ids, remote)

    def _local_remove(self, reference, src, build_ids, package_ids):
        # Make sure to clean the locks too
        self._client_cache.remove_package_locks(reference)
        remover = DiskRemover(self._client_cache)
        if src:
            remover.remove_src(reference)
        if build_ids is not None:
            remover.remove_builds(reference, build_ids)
        if package_ids is not None:
            remover.remove_packages(reference, package_ids)
        if not src and build_ids is None and package_ids is None:
            remover.remove(reference)
            self._registry.remove_ref(reference, quiet=True)

    def remove(self, pattern, remote_name, src=None, build_ids=None, package_ids_filter=None, force=False,
               packages_query=None, outdated=False):
        """ Remove local/remote conans, package folders, etc.
        @param src: Remove src folder
        @param pattern: it could be OpenCV* or OpenCV or a ConanFileReference
        @param build_ids: Lists with ids or empty for all. (Its a filter)
        @param package_ids_filter: Lists with ids or empty for all. (Its a filter)
        @param force: if True, it will be deleted without requesting anything
        @param packages_query: Only if src is a reference. Query settings and options
        """

        if remote_name and (build_ids is not None or src):
            raise ConanException("Remotes don't have 'build' or 'src' folder, just packages")

        if remote_name:
            remote = self._registry.remote(remote_name)
            references = self._remote_manager.search_recipes(remote, pattern)
        else:
            references = search_recipes(self._client_cache, pattern)
        if not references:
            self._user_io.out.warn("No package recipe matches '%s'" % str(pattern))
            return

        deleted_refs = []
        for reference in references:
            assert isinstance(reference, ConanFileReference)
            package_ids = package_ids_filter
            if packages_query or outdated:
                # search packages
                if remote_name:
                    packages = self._remote_manager.search_packages(remote, reference, packages_query)
                else:
                    packages = search_packages(self._client_cache, reference, packages_query)
                if outdated:
                    if remote_name:
                        recipe_hash = self._remote_manager.get_conan_manifest(reference, remote).summary_hash
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
                if remote_name:
                    self._remote_remove(reference, package_ids, remote)
                else:
                    deleted_refs.append(reference)
                    self._local_remove(reference, src, build_ids, package_ids)

        if not remote_name:
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
