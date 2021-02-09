import tempfile

from conan.cache.cache import Cache
from conan.cache.cache_database import CacheDatabase
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
            recipe_layout2 = cache.get_reference_layout(ref)

            pref = PackageReference.loads(f'{ref.full_str()}:0packageid0')
            package_layout = recipe_layout.get_package_layout(pref)
            print(package_layout.build())
            print(package_layout.package())

            ####
            # We can create another ref-layout and it will take a different random revision
            rl2 = cache.get_reference_layout(ref)
            print(rl2.source())
            p2 = rl2.get_package_layout(pref)
            print(p2.build())

            ### Decide rrev for the first one.
            ref1 = ref.copy_with_rev('111111111')
            recipe_layout.assign_rrev(ref1, move_contents=True)
            print(recipe_layout.export())
            print(recipe_layout.export_sources())
            print(recipe_layout.source())

            ### Decide prev
            pref1 = pref.copy_with_revs(ref1.revision, 'pkg-revision')
            package_layout.assign_prev(pref1, move_contents=True)
            print(package_layout.package())

            ### If I query the database again
            rl3 = cache.get_reference_layout(pref1.ref).get_package_layout(pref1)
            print(rl3.package())
            print(rl3.build())
