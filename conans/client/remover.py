import os

from conans.client.cache.remote_registry import Remote
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import SYSTEM_REQS, rm_conandir
from conans.search.search import filter_outdated, search_packages, search_recipes
from conans.util.log import logger


class DiskRemover(object):
    def __init__(self, paths):
        self._paths = paths

    def _remove(self, path, ref, msg=""):
        try:
            logger.debug("REMOVE: folder %s" % path)
            rm_conandir(path)
        except OSError:
            error_msg = "Folder busy (open or some file open): %s" % path
            raise ConanException("%s: Unable to remove %s\n\t%s" % (repr(ref), msg, error_msg))

    def _remove_file(self, path, ref, msg=""):
        try:
            logger.debug("REMOVE: file %s" % path)
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            error_msg = "File busy (open): %s" % path
            raise ConanException("Unable to remove %s %s\n\t%s" % (repr(ref), msg, error_msg))

    def remove_recipe(self, ref):
        self.remove_src(ref)
        self._remove(self._paths.export(ref), ref, "export folder")
        self._remove(self._paths.export_sources(ref), ref, "export_source folder")
        for f in self._paths.conanfile_lock_files(ref):
            try:
                os.remove(f)
            except OSError:
                pass

    def remove(self, ref):
        self.remove_recipe(ref)
        self.remove_builds(ref)
        self.remove_packages(ref)
        self._remove(self._paths.conan(ref), ref)

    def remove_src(self, ref):
        self._remove(self._paths.source(ref), ref, "src folder")

    def remove_builds(self, ref, ids=None):
        if not ids:
            path = self._paths.builds(ref)
            for build in self._paths.conan_builds(ref):
                self._remove(os.path.join(path, build), ref, "build folder:%s" % build)
            self._remove(path, ref, "builds")
        else:
            for id_ in ids:
                # Removal build IDs should be those of the build_id if present
                pkg_path = self._paths.build(PackageReference(ref, id_))
                self._remove(pkg_path, ref, "package:%s" % id_)

    def remove_packages(self, ref, ids_filter=None):
        if not ids_filter:  # Remove all
            path = self._paths.packages(ref)
            # Necessary for short_paths removal
            for package in self._paths.conan_packages(ref):
                self._remove(os.path.join(path, package), ref, "package folder:%s" % package)
            self._remove(path, ref, "packages")
            self._remove_file(self._paths.system_reqs(ref), ref, SYSTEM_REQS)
        else:
            for id_ in ids_filter:  # remove just the specified packages
                pref = PackageReference(ref, id_)
                pkg_folder = self._paths.package(pref)
                self._remove(pkg_folder, ref, "package:%s" % id_)
                self._remove_file(pkg_folder + ".dirty", ref, "dirty flag")
                self._remove_file(self._paths.system_reqs_package(pref), ref,
                                  "%s/%s" % (id_, SYSTEM_REQS))


class ConanRemover(object):
    """ Class responsible for removing locally/remotely conans, package folders, etc. """

    def __init__(self, cache, remote_manager, user_io):
        self._user_io = user_io
        self._cache = cache
        self._remote_manager = remote_manager
        self._registry = cache.registry

    def _remote_remove(self, ref, package_ids, remote):
        assert(isinstance(remote, Remote))
        if package_ids is None:
            result = self._remote_manager.remove(ref, remote)
            return result
        else:
            tmp = self._remote_manager.remove_packages(ref, package_ids, remote)
            return tmp

    def _local_remove(self, ref, src, build_ids, package_ids):
        if self._cache.installed_as_editable(ref):
            raise ConanException("Package '{r}' is installed as editable, unlink it first using "
                                 "command 'conan link {r} --remove'".format(r=ref))

        # Make sure to clean the locks too
        self._cache.remove_package_locks(ref)
        remover = DiskRemover(self._cache)
        if src:
            remover.remove_src(ref)
        if build_ids is not None:
            remover.remove_builds(ref, build_ids)
        if package_ids is not None:
            remover.remove_packages(ref, package_ids)
            for package_id in package_ids:
                pref = PackageReference(ref, package_id)
                self._registry.prefs.remove(pref)
        if not src and build_ids is None and package_ids is None:
            remover.remove(ref)
            self._registry.refs.remove(ref, quiet=True)
            self._registry.prefs.remove_all(ref)

    def remove(self, pattern, remote_name, src=None, build_ids=None, package_ids_filter=None,
               force=False, packages_query=None, outdated=False):
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
            remote = self._registry.remotes.get(remote_name)
            refs = self._remote_manager.search_recipes(remote, pattern)
        else:
            refs = search_recipes(self._cache, pattern)
        if not refs:
            self._user_io.out.warn("No package recipe matches '%s'" % str(pattern))
            return

        deleted_refs = []
        for ref in refs:
            assert isinstance(ref, ConanFileReference)
            package_ids = package_ids_filter
            if packages_query or outdated:
                # search packages
                if remote_name:
                    packages = self._remote_manager.search_packages(remote, ref, packages_query)
                else:
                    packages = search_packages(self._cache, ref, packages_query)
                if outdated:
                    if remote_name:
                        recipe_hash = self._remote_manager.get_conan_manifest(ref, remote).summary_hash
                    else:
                        recipe_hash = self._cache.package_layout(ref).load_manifest().summary_hash

                    packages = filter_outdated(packages, recipe_hash)
                if package_ids_filter:
                    package_ids = [p for p in packages if p in package_ids_filter]
                else:
                    package_ids = list(packages.keys())
                if not package_ids:
                    self._user_io.out.warn("No matching packages to remove for %s"
                                           % ref.full_repr())
                    continue

            if self._ask_permission(ref, src, build_ids, package_ids, force):
                deleted_refs.append(ref)
                if remote_name:
                    self._remote_remove(ref, package_ids, remote)
                else:
                    deleted_refs.append(ref)
                    self._local_remove(ref, src, build_ids, package_ids)

        if not remote_name:
            self._cache.delete_empty_dirs(deleted_refs)

    def _ask_permission(self, ref, src, build_ids, package_ids_filter, force):
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
                                             % (", ".join(aux_str), str(ref)))
