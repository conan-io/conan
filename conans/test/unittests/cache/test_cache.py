import re
import tempfile

import pytest

from conan.cache.cache import Cache
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
    pattern = rf'{cache_folder}/[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}/[\w@]+'
    return bool(re.match(pattern, str(folder)))


class TestFolders:
    def test_random_reference(self, tmp_cache):
        ref = ConanFileReference.loads('name/version@user/channel')
        ref_layout = tmp_cache.get_reference_layout(ref)
        assert is_random_folder(tmp_cache.base_folder, ref_layout.export())
        assert is_random_folder(tmp_cache.base_folder, ref_layout.export_sources())
        assert is_random_folder(tmp_cache.base_folder, ref_layout.source())

    def test_reference_with_rrev(self, tmp_cache):
        # By default the cache will assign deterministics folders
        ref = ConanFileReference.loads('name/version@user/channel#1111111111')
        ref_layout = tmp_cache.get_reference_layout(ref)
        assert not is_random_folder(tmp_cache.base_folder, ref_layout.export())
        assert not is_random_folder(tmp_cache.base_folder, ref_layout.export_sources())
        assert not is_random_folder(tmp_cache.base_folder, ref_layout.source())

    def test_reference_existing(self, tmp_cache):
        ref = ConanFileReference.loads('name/version@user/channel')
        creation_layout = tmp_cache.get_reference_layout(ref)
        ref = ref.copy_with_rev(revision='111111')

        # If the folders are not moved when assigning the rrev, they will be retrieved as they are
        creation_layout.assign_rrev(ref, move_contents=False)
        ref_layout = tmp_cache.get_reference_layout(ref)
        assert is_random_folder(tmp_cache.base_folder, ref_layout.export())
        assert is_random_folder(tmp_cache.base_folder, ref_layout.export_sources())
        assert is_random_folder(tmp_cache.base_folder, ref_layout.source())

    def test_random_package(self, tmp_cache):
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789')
        pkg_layout = tmp_cache.get_reference_layout(pref.ref).get_package_layout(pref)
        assert is_random_folder(tmp_cache.base_folder, pkg_layout.build())
        assert is_random_folder(tmp_cache.base_folder, pkg_layout.package())

    def test_package_with_prev(self, tmp_cache):
        # By default the cache will assign deterministics folders
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789#999999999')
        pkg_layout = tmp_cache.get_reference_layout(pref.ref).get_package_layout(pref)
        assert not is_random_folder(tmp_cache.base_folder, pkg_layout.build())
        assert not is_random_folder(tmp_cache.base_folder, pkg_layout.package())

    def test_package_existing(self, tmp_cache):
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789')
        creation_layout = tmp_cache.get_reference_layout(pref.ref).get_package_layout(pref)
        pref = pref.copy_with_revs(pref.ref.revision, '999999')

        # If the folders are not moved when assigning the prev, they will be retrieved as they are
        creation_layout.assign_prev(pref, move_contents=False)
        pkg_layout = tmp_cache.get_reference_layout(pref.ref).get_package_layout(pref)
        assert is_random_folder(tmp_cache.base_folder, pkg_layout.build())
        assert is_random_folder(tmp_cache.base_folder, pkg_layout.package())


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
        r1_layout.assign_rrev(ref)
    assert "Pretended reference already exists" == str(excinfo.value)


def test_concurrent_package(tmp_cache):
    # When two jobs are generating the same packageID and it happens that both compute the same prev
    ref = ConanFileReference.loads('name/version#rrev')
    recipe_layout = tmp_cache.get_reference_layout(ref)
    pref = PackageReference.loads(f'{ref.full_str()}:123456789')
    p1_layout = recipe_layout.get_package_layout(pref)
    with p1_layout.lock(blocking=True, wait=True):
        # P1 is building the package and P2 starts to do the same
        p2_layout = recipe_layout.get_package_layout(pref)
        with p2_layout.lock(blocking=True, wait=False):
            pass

        # P2 finishes before, both compute the same package revision
        pref = pref.copy_with_revs(pref.ref.revision, '5555555555')
        p2_layout.assign_prev(pref, move_contents=True)

    # When P1 tries to claim the same revision...
    with pytest.raises(Exception) as excinfo:
        p1_layout.assign_prev(pref)
    assert "Pretended prev already exists" == str(excinfo.value)


def test_concurrent_read_write_recipe(tmp_cache):
    # For whatever the reason, two concurrent jobs want to read and write the recipe
    ref = ConanFileReference.loads('name/version#1111111111')
    r1_layout = tmp_cache.get_reference_layout(ref)
    r2_layout = tmp_cache.get_reference_layout(ref)
    r3_layout = tmp_cache.get_reference_layout(ref)
    with r1_layout.lock(blocking=False, wait=False):
        with r2_layout.lock(blocking=False, wait=False):
            assert str(r1_layout.export()) == str(r2_layout.export())
            # But r3 cannot take ownership
            with pytest.raises(Exception) as excinfo:
                with r3_layout.lock(blocking=True, wait=False):
                    pass
            assert "Resource 'name/version#1111111111' is already blocked" == str(excinfo.value)


def test_concurrent_write_recipe_package(tmp_cache):
    # A job is creating a package while another ones tries to modify the recipe
    pref = PackageReference.loads('name/version#11111111:123456789')
    recipe_layout = tmp_cache.get_reference_layout(pref.ref)
    package_layout = recipe_layout.get_package_layout(pref)

    with package_layout.lock(blocking=True, wait=True):
        # We can read the recipe
        with recipe_layout.lock(blocking=False, wait=False):
            pass

        # But we cannot write
        with pytest.raises(Exception) as excinfo:
            with recipe_layout.lock(blocking=True, wait=False):
                pass
        pattern = rf"Resource '{pref.full_str()}#[0-9a-f\-]+' is already blocked"
        assert re.match(pattern, str(excinfo.value))

    # And the other way around, we can read the recipe and create a package meanwhile
    with recipe_layout.lock(blocking=False, wait=True):
        with package_layout.lock(blocking=True, wait=False):
            pass
