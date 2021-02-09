import tempfile

import pytest

from conan.cache.cache_database import CacheDatabase
from conan.cache.cache import Cache
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference


class TestCache:

    def test_xxxx(self):
        locks_manager = LocksManager.create('memory')
        backend = CacheDatabase(':memory:')

        with tempfile.TemporaryDirectory() as tmpdirname:
            print(tmpdirname)
            cache = Cache.create('memory', tmpdirname, locks_manager)

            ref = ConanFileReference.loads('name/version@user/channel')
            recipe_layout = cache.get_reference_layout(ref)
            print(recipe_layout.export())
            print(recipe_layout.export_sources())
            print(recipe_layout.source())

            pref = PackageReference.loads(f'{ref.full_str()}:0packageid0')
            package_layout = recipe_layout.get_package_layout(pref)
            print(package_layout.build())
            print(package_layout.package())
