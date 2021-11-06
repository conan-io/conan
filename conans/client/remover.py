import os
from io import StringIO

from conans.cli.output import ConanOutput
from conans.client.cache.remote_registry import Remote
from conans.client.userio import UserInput
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.errors import NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.ref import ConanFileReference, check_valid_ref
from conans.paths import SYSTEM_REQS
from conans.search.search import search_packages, search_recipes
from conans.util.files import rmdir
from conans.util.log import logger


class DiskRemover(object):

    def _remove(self, path, ref, msg=""):
        try:
            logger.debug("REMOVE: folder %s" % path)
            rmdir(path)
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

    def remove_recipe(self, package_layout, output):
        self.remove_src(package_layout)
        package_layout.export_remove()
        for f in package_layout.conanfile_lock_files(output=output):
            try:
                os.remove(f)
            except OSError:
                pass

    def remove(self, package_layout, output):
        self.remove_recipe(package_layout, output=output)
        self.remove_builds(package_layout)
        self.remove_packages(package_layout)
        self._remove(package_layout.base_folder(), package_layout.ref)

    def remove_src(self, package_layout):
        package_layout.sources_remove()

    def remove_builds(self, package_layout, ids=None):
        if not ids:
            path = package_layout.builds()
            for build in package_layout.conan_builds():
                self._remove(os.path.join(path, build), package_layout.ref,
                             "build folder:%s" % build)
            self._remove(path, package_layout.ref, "builds")
        else:
            for id_ in ids:
                # Removal build IDs should be those of the build_id if present
                pkg_path = package_layout.build(PkgReference(package_layout.ref, id_))
                self._remove(pkg_path, package_layout.ref, "package:%s" % id_)

    def remove_packages(self, package_layout, ids_filter=None):
        if not ids_filter:  # Remove all
            path = package_layout.packages()
            # Necessary for short_paths removal
            for package_id in package_layout.package_ids():
                pref = PkgReference(package_layout.ref, package_id)
                package_layout.package_remove(pref)
            self._remove(path, package_layout.ref, "packages")
            self._remove_file(package_layout.system_reqs(), package_layout.ref, SYSTEM_REQS)
        else:
            for package_id in ids_filter:  # remove just the specified packages
                pref = PkgReference(package_layout.ref, package_id)
                if not package_layout.package_exists(pref):
                    raise PackageNotFoundException(pref)
                package_layout.package_remove(pref)
                self._remove_file(package_layout.system_reqs_package(pref), package_layout.ref,
                                  "%s/%s" % (package_id, SYSTEM_REQS))


class ConanRemover(object):
    """ Class responsible for removing locally/remotely conans, package folders, etc. """

    def __init__(self, app):
        self._app = app
        self._user_input = UserInput(app.cache.config.non_interactive)
        self._cache = app.cache
        self._remote_manager = app.remote_manager

    def _remote_remove(self, ref, package_ids, remote):
        assert (isinstance(remote, Remote))
        if package_ids is None:
            result = self._remote_manager.remove_recipe(ref, remote)
            return result
        else:
            tmp = self._remote_manager.remove_packages(ref, package_ids, remote)
            return tmp

    @staticmethod
    def _message_removing_editable(ref):
        return "Package '{r}' is installed as editable, remove it first using " \
               "command 'conan editable remove {r}'".format(r=ref)

    # TODO: cache2.0 refactor this part when we can change the implementation of search_packages
    def _get_revisions_to_remove(self, ref, ids, all_package_revisions):
        folders_to_remove = []
        if len(ids) == 0:
            folders_to_remove = all_package_revisions
        for package_id in ids:
            _tmp = package_id.split("#") if "#" in package_id else (package_id, None)
            package_id, revision = _tmp
            _pref = PkgReference(ref, package_id, revision=revision)
            prev = self._cache.get_package_revisions(_pref)
            if not prev:
                raise PackageNotFoundException(_pref)
            folders_to_remove.extend(prev)
        return folders_to_remove

    # TODO: cache2.0 remove everything for the moment and consider other arguments
    #  in the future in case they remain
    def _local_remove(self, ref, src, build_ids, package_ids):
        if self._cache.installed_as_editable(ref):
            ConanOutput().warning(self._message_removing_editable(ref))
            return

        remove_recipe = False if package_ids is not None or build_ids is not None else True
        pkg_ids = self._cache.get_package_references(ref)
        all_package_revisions = []
        for pkg_id in pkg_ids:
            all_package_revisions.extend(self._cache.get_package_revisions(pkg_id))

        prev_remove = []
        prev_remove_build = []

        if package_ids is not None:
            prev_remove = self._get_revisions_to_remove(ref, package_ids, all_package_revisions)

        if build_ids is not None:
            prev_remove_build = self._get_revisions_to_remove(ref, build_ids, all_package_revisions)

        if src:
            recipe_layout = self._cache.ref_layout(ref)
            recipe_layout.sources_remove()

        if package_ids is None and build_ids is None:
            for package in all_package_revisions:
                package_layout = self._cache.pkg_layout(package)
                self._cache.remove_package_layout(package_layout)
        else:
            # for -p argument we remove the whole package, for -b just the build folder
            for package in prev_remove:
                package_layout = self._cache.pkg_layout(package)
                self._cache.remove_package_layout(package_layout)

            for package in prev_remove_build:
                package_layout = self._cache.pkg_layout(package)
                package_layout.build_remove()

        if not src and remove_recipe:
            ref_layout = self._cache.ref_layout(ref)
            self._cache.remove_recipe_layout(ref_layout)

    def remove(self, pattern, src=None, build_ids=None, package_ids_filter=None,
               force=False, packages_query=None):
        """ Remove local/remote conans, package folders, etc.
        @param src: Remove src folder
        @param pattern: it could be OpenCV* or OpenCV or a ConanFileReference
        @param build_ids: Lists with ids or empty for all. (Its a filter)
        @param package_ids_filter: Lists with ids or empty for all. (Its a filter)
        @param force: if True, it will be deleted without requesting anything
        @param packages_query: Only if src is a reference. Query settings and options
        """

        if self._app.selected_remote and (build_ids is not None or src):
            raise ConanException("Remotes don't have 'build' or 'src' folder, just packages")

        is_reference = check_valid_ref(pattern)
        input_ref = ConanFileReference.loads(pattern) if is_reference else None

        if not input_ref and packages_query is not None:
            raise ConanException("query parameter only allowed with a valid recipe "
                                 "reference as the search pattern.")

        if input_ref and package_ids_filter and not input_ref.revision:
            for package_id in package_ids_filter:
                if "#" in package_id:
                    raise ConanException("Specify a recipe revision if you specify a package "
                                         "revision")

        if self._app.selected_remote:
            if input_ref:
                refs = [input_ref]
            else:
                refs = self._remote_manager.search_recipes(self._app.selected_remote, pattern)
        else:
            if input_ref:
                # TODO: cache2.0 do we want to get all revisions or just the latest?
                #  remove all for the moment
                # TODO: cache2.0 raising the not found exceptions here but we should refactor all
                #  of this for conan 2.0 now that we only have revisions enabled
                refs = self._cache.get_recipe_revisions(input_ref)
                if not refs:
                    raise RecipeNotFoundException(input_ref)
                for ref in refs:
                    if self._cache.installed_as_editable(ref):
                        raise ConanException(self._message_removing_editable(ref))
            else:
                refs = search_recipes(self._cache, pattern)
                if not refs:
                    ConanOutput().warning("No package recipe matches '%s'" % str(pattern))
                    return

        deleted_refs = []
        for ref in refs:
            assert isinstance(ref, ConanFileReference)
            package_ids = package_ids_filter
            if packages_query:
                # search packages
                if self._app.selected_remote:
                    packages = self._remote_manager.search_packages(self._app.selected_remote,
                                                                    ref, packages_query)
                else:
                    pkg_ids = self._cache.get_package_references(ref)
                    all_package_revs = []
                    for pkg in pkg_ids:
                        all_package_revs.extend(self._cache.get_package_revisions(pkg))
                    packages_layouts = [self._cache.pkg_layout(pref) for pref in all_package_revs]
                    packages = search_packages(packages_layouts, packages_query)
                if package_ids_filter:
                    package_ids = [p for p in packages if p in package_ids_filter]
                else:
                    package_ids = packages
                if not package_ids:
                    ConanOutput().warning("No matching packages to remove for %s"
                                              % ref.full_str())
                    continue

            if self._ask_permission(ref, src, build_ids, package_ids, force):
                try:
                    if self._app.selected_remote:
                        self._remote_remove(ref, package_ids, self._app.selected_remote)
                    else:
                        self._local_remove(ref, src, build_ids, package_ids)
                except NotFoundException:
                    # If we didn't specify a pattern but a concrete ref, fail if there is no
                    # ref to remove
                    if input_ref:
                        raise
                else:
                    deleted_refs.append(ref)

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
        return self._user_input.request_boolean("Are you sure you want to delete%s from '%s'"
                                                 % (", ".join(aux_str), str(ref)))
