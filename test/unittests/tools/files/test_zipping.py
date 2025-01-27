import zipfile
import tarfile
from os.path import join, exists

import pytest

from conan.tools.files import unzip
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conans.util.files import save
from conan.errors import ConanException


def test_impossible_to_import_untargz():
    with pytest.raises(ImportError) as exc:
        from conan.tools.files import untargz


def create_example_zip(root_file=True, subfolder=False):
    tmp_dir = temp_folder()
    archive = join(tmp_dir, "zipfile.zip")
    zf = zipfile.ZipFile(archive, mode="w")
    if root_file:
        foo_txt = join(tmp_dir, "foo.txt")
        save(foo_txt, "foo-content")
        zf.write(foo_txt, "foo.txt")
    if subfolder:
        src_bar_txt = join(tmp_dir, "src", "bar.txt")
        save(src_bar_txt, "bar-content")
        zf.write(src_bar_txt, join("src", "bar.txt"))
    zf.close()
    return archive


def test_unzip():
    archive = create_example_zip(subfolder=True)
    conanfile = ConanFileMock({})

    # Unzip and check permissions are kept
    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir)
    assert exists(join(dest_dir, "foo.txt"))
    assert exists(join(dest_dir, "src", "bar.txt"))


def test_unzip_with_pattern():
    archive = create_example_zip(subfolder=True)
    conanfile = ConanFileMock({})

    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir, pattern="foo.txt")
    assert exists(join(dest_dir, "foo.txt"))
    assert not exists(join(dest_dir, "src", "bar.txt"))


def test_unzip_with_strip_root():
    archive = create_example_zip(root_file=False, subfolder=True)
    conanfile = ConanFileMock({})

    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir, strip_root=True)
    assert exists(join(dest_dir, "bar.txt"))


def test_unzip_with_strip_root_fails():
    archive = create_example_zip(root_file=True, subfolder=True)
    conanfile = ConanFileMock({})

    dest_dir = temp_folder()
    with pytest.raises(ConanException) as error:
        unzip(conanfile, archive, dest_dir, strip_root=True)
    assert "The zip file contains more than 1 folder in the root" in str(error.value)


def test_unzip_with_strip_root_and_pattern():
    archive = create_example_zip(root_file=True, subfolder=True)
    conanfile = ConanFileMock({})

    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir, pattern="src/*", strip_root=True)
    assert exists(join(dest_dir, "bar.txt"))
    assert not exists(join(dest_dir, "foo.txt"))


def create_example_tar(root_file=True, subfolder=False):
    tmp_dir = temp_folder()
    tar_path = join(tmp_dir, "file.tgz")
    tar = tarfile.open(tar_path, "w:gz")
    if root_file:
        foo_txt = join(tmp_dir, "foo.txt")
        save(foo_txt, "foo-content")
        tar.add(foo_txt, "foo.txt")
    if subfolder:
        src_bar_txt = join(tmp_dir, "src", "bar.txt")
        save(src_bar_txt, "bar-content")
        tar.add(src_bar_txt, join("src", "bar.txt"))
    tar.close()
    return tar_path


def test_untargz():
    archive = create_example_tar(subfolder=True)
    conanfile = ConanFileMock({})

    # Unzip and check permissions are kept
    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir)
    assert exists(join(dest_dir, "foo.txt"))
    assert exists(join(dest_dir, "src", "bar.txt"))


def test_untargz_with_pattern():
    archive = create_example_tar(subfolder=True)
    conanfile = ConanFileMock({})

    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir, pattern="foo.txt")
    assert exists(join(dest_dir, "foo.txt"))
    assert not exists(join(dest_dir, "src", "bar.txt"))


def test_untargz_with_strip_root():
    archive = create_example_tar(root_file=False, subfolder=True)
    conanfile = ConanFileMock({})

    # Unzip and check permissions are kept
    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir, strip_root=True)
    assert exists(join(dest_dir, "bar.txt"))


def test_untargz_with_strip_root_fails():
    archive = create_example_tar(root_file=True, subfolder=True)
    conanfile = ConanFileMock({})

    # Unzip and check permissions are kept
    dest_dir = temp_folder()
    with pytest.raises(ConanException) as error:
        unzip(conanfile, archive, dest_dir, strip_root=True)
    assert "The tgz file contains more than 1 folder in the root" in str(error.value)


def test_untargz_with_strip_root_and_pattern():
    archive = create_example_tar(root_file=True, subfolder=True)
    conanfile = ConanFileMock({})

    # Unzip and check permissions are kept
    dest_dir = temp_folder()
    unzip(conanfile, archive, dest_dir, pattern="src/*", strip_root=True)
    assert exists(join(dest_dir, "bar.txt"))
    assert not exists(join(dest_dir, "foo.txt"))
