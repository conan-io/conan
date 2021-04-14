import os
import re
import tempfile

import pytest

from conan.cache.db.packages import PackagesDbTable
from conan.cache.db.references import ReferencesDbTable
from conan.cache.cache import DataCache
from conans.model.ref import ConanFileReference, PackageReference
from conans.test import CONAN_TEST_FOLDER


@pytest.fixture
def cache() -> DataCache:
    with tempfile.TemporaryDirectory(suffix='conans', dir=CONAN_TEST_FOLDER) as tmpdirname:
        locks_directory = os.path.join(tmpdirname, '.locks')
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        cache = DataCache(tmpdirname, db_filename, locks_directory)
        yield cache


def is_random_folder(cache_folder: str, folder: str):
    # TODO: This can be shared and should be agree with the strategy used to generate random folders in the cache
    pattern = rf'{cache_folder}/[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}(/[\w@]+)?'
    return bool(re.match(pattern, str(folder)))


class TestFolders:
    def test_reference_without_rrev(self, cache: DataCache):
        ref = ConanFileReference.loads('name/version@user/channel')

        with pytest.raises(AssertionError) as excinfo:
            _ = cache.get_reference_layout(ref)
        assert "Ask for a reference layout only if the rrev is known" == str(excinfo.value)

        ref_layout, created = cache.get_or_create_reference_layout(ref)
        assert created
        assert is_random_folder(cache.base_folder, ref_layout.export())
        assert is_random_folder(cache.base_folder, ref_layout.export_sources())
        assert is_random_folder(cache.base_folder, ref_layout.source())

    def test_reference_with_rrev(self, cache: DataCache):
        # By default the cache will assign deterministics folders
        ref = ConanFileReference.loads('name/version@user/channel#1111111111')

        with pytest.raises(ReferencesDbTable.DoesNotExist) as excinfo:
            _ = cache.get_reference_layout(ref)
        assert "No entry for reference 'name/version@user/channel#1111111111'" == str(excinfo.value)

        ref_layout, created = cache.get_or_create_reference_layout(ref)
        assert created
        assert not is_random_folder(cache.base_folder, ref_layout.export())
        assert not is_random_folder(cache.base_folder, ref_layout.export_sources())
        assert not is_random_folder(cache.base_folder, ref_layout.source())

    def test_reference_existing(self, cache: DataCache):
        ref = ConanFileReference.loads('name/version@user/channel')
        creation_layout, _ = cache.get_or_create_reference_layout(ref)
        ref = ref.copy_with_rev(revision='111111')

        # If the folders are not moved when assigning the rrev, they will be retrieved as they are
        creation_layout.assign_rrev(ref, move_contents=False)
        ref_layout = cache.get_reference_layout(ref)
        assert is_random_folder(cache.base_folder, ref_layout.export())
        assert is_random_folder(cache.base_folder, ref_layout.export_sources())
        assert is_random_folder(cache.base_folder, ref_layout.source())

    def test_package_without_prev(self, cache: DataCache):
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789')
        cache.get_or_create_reference_layout(pref.ref)

        with pytest.raises(AssertionError) as excinfo:
            _ = cache.get_package_layout(pref)
        assert "Ask for a package layout only if the prev is known" == str(excinfo.value)

        pkg_layout, created = cache.get_or_create_package_layout(pref)
        assert created
        assert is_random_folder(cache.base_folder, pkg_layout.build())
        assert is_random_folder(cache.base_folder, pkg_layout.package())

    def test_package_with_prev(self, cache: DataCache):
        # By default the cache will assign deterministics folders
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789#999999999')
        cache.get_or_create_reference_layout(pref.ref)

        with pytest.raises(PackagesDbTable.DoesNotExist) as excinfo:
            _ = cache.get_package_layout(pref)
        assert "No entry for package 'name/version@user/channel#1111111111:123456789#999999999'" == str(
            excinfo.value)

        pkg_layout, created = cache.get_or_create_package_layout(pref)
        assert created
        assert is_random_folder(cache.base_folder, pkg_layout.build())
        assert not is_random_folder(cache.base_folder, pkg_layout.package())

    def test_package_existing(self, cache: DataCache):
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789')
        cache.get_or_create_reference_layout(pref.ref)
        creation_layout, _ = cache.get_or_create_package_layout(pref)
        pref = pref.copy_with_revs(pref.ref.revision, '999999')

        # If the folders are not moved when assigning the prev, they will be retrieved as they are
        creation_layout.assign_prev(pref, move_contents=False)
        pkg_layout = cache.get_package_layout(pref)
        assert is_random_folder(cache.base_folder, pkg_layout.build())
        assert is_random_folder(cache.base_folder, pkg_layout.package())


def test_create_workflow(cache: DataCache):
    cache_folder = cache.base_folder

    # 1. First we have a reference without revision
    ref = ConanFileReference.loads('name/version@user/channel')
    ref_layout, created = cache.get_or_create_reference_layout(ref)
    assert created
    assert is_random_folder(cache_folder, str(ref_layout.export()))
    assert is_random_folder(cache_folder, str(ref_layout.export_sources()))

    # Without assigning the revision, there are many things we cannot do:
    with pytest.raises(AssertionError) as excinfo:
        pref = PackageReference.loads('name/version@user/channel:123456')
        ref_layout.get_package_layout(pref)
    assert "Before requesting a package, assign the rrev using 'assign_rrev'" == str(excinfo.value)

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
    ref_layout2 = cache.get_reference_layout(ref)
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
    assert str(build_folder) == str(package1_layout.build())  # Build folder is not moved
    assert not is_random_folder(cache_folder, package1_layout.package())


def test_concurrent_package(cache: DataCache):
    # When two jobs are generating the same packageID and it happens that both compute the same prev
    ref = ConanFileReference.loads('name/version#rrev')
    recipe_layout, _ = cache.get_or_create_reference_layout(ref)
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
    with pytest.raises(PackagesDbTable.AlreadyExist) as excinfo:
        p1_layout.assign_prev(pref)
    assert "Package 'name/version#rrev:123456789#5555555555' already exists" == str(excinfo.value)


def test_concurrent_read_write_recipe(cache: DataCache):
    # For whatever the reason, two concurrent jobs want to read and write the recipe
    ref = ConanFileReference.loads('name/version#1111111111')
    r1_layout, _ = cache.get_or_create_reference_layout(ref)
    r2_layout, _ = cache.get_or_create_reference_layout(ref)
    r3_layout, _ = cache.get_or_create_reference_layout(ref)
    with r1_layout.lock(blocking=False, wait=False):
        with r2_layout.lock(blocking=False, wait=False):
            assert str(r1_layout.export()) == str(r2_layout.export())
            # But r3 cannot take ownership
            with pytest.raises(Exception) as excinfo:
                with r3_layout.lock(blocking=True, wait=False):
                    pass
            assert "Resource 'name/version#1111111111' is already blocked" == str(excinfo.value)


def test_concurrent_write_recipe_package(cache: DataCache):
    # A job is creating a package while another ones tries to modify the recipe
    pref = PackageReference.loads('name/version#11111111:123456789')
    recipe_layout, _ = cache.get_or_create_reference_layout(pref.ref)
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
