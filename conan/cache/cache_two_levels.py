import os
import shutil
from io import StringIO
from typing import Tuple

from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from conan.cache.cache_implementation_readonly import CacheImplementationReadOnly
from conan.cache.package_layout import PackageLayout
from conan.cache.recipe_layout import RecipeLayout
from conan.locks.locks_manager import LocksManager
from conans.model.ref import PackageReference, ConanFileReference
from ._tables.packages import Packages
from ._tables.references import References


class CacheTwoLevels(Cache):
    """
    Wrapper for a two-level cache implementation. Under the hood it instantiates two cache objects,
    one of them configured to be read-only. The read-only cache is a fallback for read operations
    while the other is the one for any write operation.
    """

    def __init__(self, workspace_cache: CacheImplementation, user_cache: CacheImplementationReadOnly,
                 locks_manager: LocksManager):
        assert isinstance(user_cache, CacheImplementationReadOnly), "Expected read-only instance"
        self._workspace = workspace_cache
        self._user_cache = user_cache
        self._locks_manager = locks_manager

    def dump(self, output: StringIO):
        self._workspace.dump(output)
        self._user_cache.dump(output)

    def _fetch_reference(self, ref: ConanFileReference) -> RecipeLayout:
        """ Copies a reference from the user-cache to the workspace one, and returns the layout from
            the one in the workspace
        """
        user_reference = self._user_cache.get_reference_layout(ref)
        with user_reference.lock(blocking=False):  # From the perspective of the user-cache it's read
            ws_reference, _ = self._workspace.get_or_create_reference_layout(ref)

            # Export path is required for every recipe
            ws_export = str(ws_reference.export())
            us_export = str(user_reference.export())
            shutil.rmtree(ws_export, ignore_errors=True)
            shutil.copytree(src=us_export, dst=ws_export, symlinks=True,
                            ignore_dangling_symlinks=True)

            # Optionally the recipe can have 'source' and 'export_sources'
            for it in ('source', 'export_sources'):
                ws_path = str(getattr(ws_reference, it)())
                us_path = str(getattr(user_reference, it)())
                shutil.rmtree(ws_path, ignore_errors=True)
                if os.path.exists(us_path):
                    shutil.copytree(src=us_path, dst=ws_path, symlinks=True,
                                    ignore_dangling_symlinks=True)
        return ws_reference

    def _get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        """
        Try with workspace cache, if not try with remote, if neither raise References.DoesNotExist
        """
        try:
            return self._workspace.get_reference_layout(ref)
        except References.DoesNotExist:
            return self._user_cache.get_reference_layout(ref)

    def get_or_create_reference_layout(self, ref: ConanFileReference) -> Tuple[RecipeLayout, bool]:
        if ref.revision:
            try:
                return self.get_reference_layout(ref), False
            except References.DoesNotExist:
                pass
        return self._workspace.get_or_create_reference_layout(ref)

    def _get_package_layout(self, pref: PackageReference) -> PackageLayout:
        """
        Retrieve the package_layout for the given package reference. If it exists it returns the one
        from the workspace cache and, if not, the one from the user cache. It will raise a
        Packages.DoesNotExist exception otherwise.
        """
        try:
            return self._workspace.get_package_layout(pref)
        except (Packages.DoesNotExist, References.DoesNotExist):
            return self._user_cache.get_package_layout(pref)

    def get_or_create_package_layout(self, pref: PackageReference) -> Tuple[PackageLayout, bool]:
        if pref.revision:
            try:
                return self.get_package_layout(pref), False
            except Packages.DoesNotExist:
                pass

        # TODO: lock?
        # Copy the reference from the user-cache to the workspace-cache (if not already there)
        try:
            ws_layout = self._workspace.get_reference_layout(pref.ref)
        except References.DoesNotExist:
            ws_layout = self._fetch_reference(pref.ref)

        return ws_layout.get_package_layout(pref), True
