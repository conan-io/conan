import shutil
from io import StringIO

from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.cache.package_layout import PackageLayout
from conan.cache.recipe_layout import RecipeLayout
from conan.locks.locks_manager import LocksManager
from conans.model.ref import PackageReference, ConanFileReference
from ._tables.folders import Folders, ConanFolders
from ._tables.packages import Packages
from ._tables.references import References


class CacheTwoLevels(Cache):
    """
    Wrapper for a two-level cache implementation. Under the hood it instantiates two cache objects,
    one of them configured to be read-only. The read-only cache is a fallback for read operations
    while the other is the one for any write operation.
    """

    def __init__(self, workspace_cache: CacheImplementation, user_cache: CacheImplementation,
                 locks_manager: LocksManager):
        self._workspace = workspace_cache
        self._user_cache = user_cache
        self._locks_manager = locks_manager

    def dump(self, output: StringIO):
        self._workspace.dump(output)
        self._user_cache.dump(output)

    def _fetch_reference(self, ref: ConanFileReference):
        """ Copies a reference from the user-cache to the workspace one """
        self._user_cache.db.try_get_reference_directory(ref)
        user_reference = self._user_cache.get_reference_layout(ref)
        with user_reference.lock(blocking=True):
            ws_reference = self._workspace.get_reference_layout(ref)
            for it in ('export', 'source', 'export_sources'):
                shutil.rmtree(getattr(ws_reference, it), ignore_errors=True)
                shutil.copytree(src=getattr(user_reference, it), dst=getattr(ws_reference, it),
                                symlinks=True, ignore_dangling_symlinks=True)

    def get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        """
        Try with workspace cache, if not try with remote, if neither create in workspace cache
        """
        # TODO: lock
        try:
            self._workspace.db.try_get_reference_directory(ref)
            return self._workspace.get_reference_layout(ref)
        except References.DoesNotExist:
            try:
                self._user_cache.db.try_get_reference_directory(ref)
                return self._user_cache.get_reference_layout(ref)
            except References.DoesNotExist:
                return self._workspace.get_reference_layout(ref)

    def _get_package_layout(self, pref: PackageReference) -> PackageLayout:
        """
        Retrieve the package_layout for the given package reference. If it exists it will use the
        same logic as for the reference layout, if it doesn't exists, then it will create the
        package layout in the workspace cache and it will ensure that the corresponding recipe
        reference exists in the workspace cache as well.
        """
        # TODO: lock
        try:
            self._workspace.db.try_get_package_reference_directory(pref, ConanFolders.PKG_PACKAGE)
            return self._workspace.get_package_layout(pref)
        except References.DoesNotExist:
            # TODO: Copy the reference from the user-cache (if it exists) and
            # TODO: copy the package from the user-cache (if it exists) or create it here.
            pass

        except Packages.DoesNotExist:
            # TODO: Copy the package from the user-cache (if it exists) or create it here
            try:
                self._user_cache.db.try_get_package_reference_directory(pref,
                                                                        ConanFolders.PKG_PACKAGE)
                return self._user_cache.get_package_layout(pref)
            except References.DoesNotExist:
                return self._workspace.get_reference_layout(pref.ref).get_package_layout(pref)
            except Packages.DoesNotExist:
                # We will create the package layout in the workspace cache, we need to ensure that
                # the corresponding reference exists
                # TODO: We need an actual fetch here
                ws_ref_layout = self._workspace.get_reference_layout(pref.ref)
                return self._workspace.get_reference_layout(pref.ref).get_package_layout(pref)
