import os
import platform

import pytest

from conans.model.manifest import FileTreeManifest
from conan.test.utils.test_files import temp_folder
from conans.util.files import load, md5, save


@pytest.mark.skipif(platform.system() == "Windows", reason="decent symlinks only")
def test_symlinks_manifest():
    """ The symlinks are coded in the manifest, the key is the path of the symlink and the hash
        is the hash of the contents or empty string if this is a broken symlink"""
    tmp_dir = temp_folder()
    save(os.path.join(tmp_dir, "foo.txt"), "bar")
    os.symlink("foo.txt", os.path.join(tmp_dir, "foofake.txt"))
    os.symlink("foo_missing.txt", os.path.join(tmp_dir, "var.txt"))
    manifest = FileTreeManifest.create(tmp_dir)

    manifest.save(tmp_dir)
    read_manifest = FileTreeManifest.load(tmp_dir)
    assert read_manifest.file_sums == {'foo.txt': '37b51d194a7513e45b56f6524f2d51f2',
                                       'foofake.txt': '4fd8cc85ca9eebd2fa3c550069ce2846',
                                       'var.txt': '6cc1cda38d517f2e5e47a803a343d17d'}


def test_tree_manifest():
    tmp_dir = temp_folder()
    files = {"one.ext": "aalakjshdlkjahsdlkjahsdljkhsadljkhasljkdhlkjashd",
             "path/to/two.txt": "asdas13123",
             "two.txt": "asdasdasdasdasdasd",
             "folder/damn.pyc": "binarythings",
             "folder/damn.pyo": "binarythings2",
             "pythonfile.pyc": "binarythings3"}
    for filename, content in files.items():
        save(os.path.join(tmp_dir, filename), content)

    manifest = FileTreeManifest.create(tmp_dir)

    manifest.save(tmp_dir)
    readed_manifest = FileTreeManifest.load(tmp_dir)

    assert readed_manifest.time == manifest.time
    assert readed_manifest == manifest
    # Not included the pycs or pyo
    assert set(manifest.file_sums.keys()) == {'folder/damn.pyc', 'folder/damn.pyo', 'one.ext',
                                              'path/to/two.txt', 'pythonfile.pyc', 'two.txt'}

    for filepath, md5readed in manifest.file_sums.items():
        content = files[filepath]
        assert md5(content), md5readed


def test_already_pyc_in_manifest():
    tmp_dir = temp_folder()
    save(os.path.join(tmp_dir, "man.txt"), "1478122267\nconanfile.pyc: "
                                           "2bcac725a0e6843ef351f4d18cf867ec\n"
                                           "conanfile.py: 2bcac725a0e6843ef351f4d18cf867ec\n"
                                           "conanfile.pyo: 2bcac725a0e6843ef351f4d18cf867ec\n")

    read_manifest = FileTreeManifest.loads(load(os.path.join(tmp_dir, "man.txt")))
    # Not included the pycs or pyo
    assert set(read_manifest.file_sums.keys()) == {"conanfile.py", "conanfile.pyc", "conanfile.pyo"}


def test_special_chars():
    tmp_dir = temp_folder()
    save(os.path.join(tmp_dir, "conanmanifest.txt"), "1478122267\nsome: file.py: 123\n")
    read_manifest = FileTreeManifest.load(tmp_dir)
    assert read_manifest.file_sums["some: file.py"] == "123"


def test_pycache_included():
    tmp_dir = temp_folder()
    files = {"__pycache__/damn.py": "binarythings",
             "pythonfile.pyc": "binarythings3"}
    for filename, content in files.items():
        save(os.path.join(tmp_dir, filename), content)

    manifest = FileTreeManifest.create(tmp_dir)
    manifest = repr(manifest)
    assert "pythonfile.pyc" in manifest
    assert "__pycache__/damn.py" in manifest
