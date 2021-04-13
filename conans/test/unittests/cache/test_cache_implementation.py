import os
import re
import tempfile

import pytest

from conan.cache._tables.packages import Packages
from conan.cache._tables.references import References
from conan.cache.cache_implementation import CacheImplementation
from conans.model.ref import ConanFileReference, PackageReference
from conans.test import CONAN_TEST_FOLDER


@pytest.fixture
def cache_implementation() -> CacheImplementation:
    with tempfile.TemporaryDirectory(suffix='conans', dir=CONAN_TEST_FOLDER) as tmpdirname:
        locks_directory = os.path.join(tmpdirname, '.locks')
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        cache = CacheImplementation(tmpdirname, db_filename, locks_directory)
        yield cache


def is_random_folder(cache_folder: str, folder: str):
    # TODO: This can be shared and should be agree with the strategy used to generate random folders in the cache
    pattern = rf'{cache_folder}/[a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}}(/[\w@]+)?'
    return bool(re.match(pattern, str(folder)))


class TestFolders:
    def test_reference_without_rrev(self, cache_implementation: CacheImplementation):
        ref = ConanFileReference.loads('name/version@user/channel')

        with pytest.raises(AssertionError) as excinfo:
            _ = cache_implementation.get_reference_layout(ref)
        assert "Ask for a reference layout only if the rrev is known" == str(excinfo.value)

        ref_layout, created = cache_implementation.get_or_create_reference_layout(ref)
        assert created
        assert is_random_folder(cache_implementation.base_folder, ref_layout.export())
        assert is_random_folder(cache_implementation.base_folder, ref_layout.export_sources())
        assert is_random_folder(cache_implementation.base_folder, ref_layout.source())

    def test_reference_with_rrev(self, cache_implementation: CacheImplementation):
        # By default the cache will assign deterministics folders
        ref = ConanFileReference.loads('name/version@user/channel#1111111111')

        with pytest.raises(References.DoesNotExist) as excinfo:
            _ = cache_implementation.get_reference_layout(ref)
        assert "No entry for reference 'name/version@user/channel#1111111111'" == str(excinfo.value)

        ref_layout, created = cache_implementation.get_or_create_reference_layout(ref)
        assert created
        assert not is_random_folder(cache_implementation.base_folder, ref_layout.export())
        assert not is_random_folder(cache_implementation.base_folder, ref_layout.export_sources())
        assert not is_random_folder(cache_implementation.base_folder, ref_layout.source())

    def test_reference_existing(self, cache_implementation: CacheImplementation):
        ref = ConanFileReference.loads('name/version@user/channel')
        creation_layout, _ = cache_implementation.get_or_create_reference_layout(ref)
        ref = ref.copy_with_rev(revision='111111')

        # If the folders are not moved when assigning the rrev, they will be retrieved as they are
        creation_layout.assign_rrev(ref, move_contents=False)
        ref_layout = cache_implementation.get_reference_layout(ref)
        assert is_random_folder(cache_implementation.base_folder, ref_layout.export())
        assert is_random_folder(cache_implementation.base_folder, ref_layout.export_sources())
        assert is_random_folder(cache_implementation.base_folder, ref_layout.source())

    def test_package_without_prev(self, cache_implementation: CacheImplementation):
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789')
        cache_implementation.get_or_create_reference_layout(pref.ref)

        with pytest.raises(AssertionError) as excinfo:
            _ = cache_implementation.get_package_layout(pref)
        assert "Ask for a package layout only if the prev is known" == str(excinfo.value)

        pkg_layout, created = cache_implementation.get_or_create_package_layout(pref)
        assert created
        assert is_random_folder(cache_implementation.base_folder, pkg_layout.build())
        assert is_random_folder(cache_implementation.base_folder, pkg_layout.package())

    def test_package_with_prev(self, cache_implementation: CacheImplementation):
        # By default the cache will assign deterministics folders
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789#999999999')
        cache_implementation.get_or_create_reference_layout(pref.ref)

        with pytest.raises(Packages.DoesNotExist) as excinfo:
            _ = cache_implementation.get_package_layout(pref)
        assert "No entry for package 'name/version@user/channel#1111111111:123456789#999999999'" == str(
            excinfo.value)

        pkg_layout, created = cache_implementation.get_or_create_package_layout(pref)
        assert created
        assert is_random_folder(cache_implementation.base_folder, pkg_layout.build())
        assert not is_random_folder(cache_implementation.base_folder, pkg_layout.package())

    def test_package_existing(self, cache_implementation: CacheImplementation):
        pref = PackageReference.loads('name/version@user/channel#1111111111:123456789')
        cache_implementation.get_or_create_reference_layout(pref.ref)
        creation_layout, _ = cache_implementation.get_or_create_package_layout(pref)
        pref = pref.copy_with_revs(pref.ref.revision, '999999')

        # If the folders are not moved when assigning the prev, they will be retrieved as they are
        creation_layout.assign_prev(pref, move_contents=False)
        pkg_layout = cache_implementation.get_package_layout(pref)
        assert is_random_folder(cache_implementation.base_folder, pkg_layout.build())
        assert is_random_folder(cache_implementation.base_folder, pkg_layout.package())


def test_create_workflow(cache_implementation: CacheImplementation):
    cache_folder = cache_implementation.base_folder

    # 1. First we have a reference without revision
    ref = ConanFileReference.loads('name/version@user/channel')
    ref_layout, created = cache_implementation.get_or_create_reference_layout(ref)
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
    ref_layout2 = cache_implementation.get_reference_layout(ref)
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
