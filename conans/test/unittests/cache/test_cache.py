import re
import tempfile

import pytest

from conan.cache.cache import Cache
from conan.cache.cache_database import CacheDatabase
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference


@pytest.fixture
def tmp_cache():
    # TODO: Move to some shared location for fixtures
    locks_manager = LocksManager.create('memory')
    with tempfile.TemporaryDirectory() as tmpdirname:
        cache = Cache.create('memory', tmpdirname, locks_manager)
        yield cache


def is_random_folder(cache_folder: str, folder):
    # TODO: This can be shared and should be agree with the strategy used to generate random folders in the cache
    pattern = rf'{cache_folder}/[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}/\w+'
    return bool(re.match(pattern, str(folder)))


def test_create_workflow(tmp_cache):
    cache_folder = tmp_cache.base_folder

    # 1. First we have a reference without revision
    ref = ConanFileReference.loads('name/version@user/channel')
    ref_layout = tmp_cache.get_reference_layout(ref)
    export_folder = ref_layout.export()
    assert is_random_folder(cache_folder, export_folder)
    export_sources_folder = ref_layout.export_sources()
    assert is_random_folder(cache_folder, export_sources_folder)

    # Without assigning the revision, there are many things we cannot do:
    with pytest.raises(AssertionError) as excinfo:
        pref = PackageReference.loads('name/version@user/channel:123456')
        ref_layout.get_package_layout(pref)
    assert "When requesting a package, the rrev is already known" == str(excinfo.value)

    # Of course the reference must match
    with pytest.raises(AssertionError) as excinfo:
        pref = PackageReference.loads('other/version@user/channel:123456')
        ref_layout.get_package_layout(pref)
    assert "Only for the same reference" == str(excinfo.value)

    # 2. Once we know the revision, we update information for the 'recipe_layout'
    rrev = '123456789'
    ref = ref.copy_with_rev(revision=rrev)
    ref_layout.assign_rrev(ref, move_contents=True)

    # Data and information is moved to the new (and final location)
    assert not is_random_folder(cache_folder, ref_layout.export())
    assert not is_random_folder(cache_folder, ref_layout.export_sources())

    # If the reference is in the cache, we can retrieve it.
    ref_layout2 = tmp_cache.get_reference_layout(ref)
    assert str(ref_layout.export()) == str(ref_layout2.export())
    assert str(ref_layout.export_sources()) == str(ref_layout2.export_sources())

    # 3. We can retrieve layouts for packages
    # Revision must match
    with pytest.raises(AssertionError) as excinfo:
        pref = PackageReference.loads(f'{str(ref)}#otherrrev:123456')
        ref_layout.get_package_layout(pref)
    assert "Ensure revision is the same" == str(excinfo.value)

    pref = PackageReference.loads(f'{ref.full_str()}:99999999')
    package1_layout = ref_layout.get_package_layout(pref)
    build_folder = package1_layout.build()
    assert is_random_folder(cache_folder, build_folder)
    package_folder = package1_layout.package()
    assert is_random_folder(cache_folder, package_folder)

    # Other package will have other random directories (also for the same packageID)
    package2_layout = ref_layout.get_package_layout(pref)
    build2_folder = package2_layout.build()
    package2_folder = package2_layout.package()
    assert is_random_folder(cache_folder, build2_folder)
    assert is_random_folder(cache_folder, package2_folder)
    assert str(build_folder) != str(build2_folder)
    assert str(package_folder) != str(package2_folder)

    # 4. After building the package we know the 'prev' and we can assign it
    pref = pref.copy_with_revs(pref.ref.revision, '5555555555555')
    package1_layout.assign_prev(pref, move_contents=True)

    # Data and information is moved to the new (and final location)
    assert not is_random_folder(cache_folder,
                                package1_layout.build())  # FIXME: This folder shouldn't be moved.
    assert not is_random_folder(cache_folder, package1_layout.package())


def test_concurrent_export(tmp_cache):
    # It can happen that two jobs are creating the same recipe revision.
    ref = ConanFileReference.loads('name/version')
    r1_layout = tmp_cache.get_reference_layout(ref)
    with r1_layout.lock(blocking=True, wait=False):
        # R1 is exporting the information, and R2 starts to do the same
        r2_layout = tmp_cache.get_reference_layout(ref)
        with r2_layout.lock(blocking=True, wait=False):
            pass

        # And both found the same revision, but R2 is faster
        ref = ref.copy_with_rev(revision='1234567890')
        r2_layout.assign_rrev(ref, move_contents=True)

    # When R1 wants to claim that revision...
    with pytest.raises(Exception) as excinfo:
        r1_layout.assign_rrev(ref, move_contents=True)
    assert "Pretended reference already exists" == str(excinfo.value)


class TestCache:

    def test_recipe_reader(self):
        pass

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
