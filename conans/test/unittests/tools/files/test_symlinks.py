import os
import platform

import pytest

from conan import tools
from conan.tools.files import mkdir
from conans.test.utils.test_files import temp_folder


@pytest.fixture
def folders():
    tmp = temp_folder()
    files = ["foo/var/file.txt"]
    outside_folder = temp_folder()
    symlinks = [
        (os.path.join(tmp, "foo/var/file.txt"), "foo/var/other/absolute.txt"),  # Absolute link
        (os.path.join(tmp, "foo/var"), "foo/var/other/other/myfolder"),  # Absolute link folder
        (os.path.join(tmp, "foo/var/file.txt"), "foo/absolute.txt"),  # Absolute link
        ("foo/var/file.txt", "foo/var/other/relative.txt"),  # Relative link
        ("missing.txt", "foo/var/other/broken.txt"),  # Broken link
        (outside_folder, "foo/var/other/absolute_outside"),  # Absolute folder outside the folder
        ("../../../../../outside", "foo/absolute_outside"),  # Relative folder outside the folder
    ]
    # Create the files and symlinks
    for path in files:
        mkdir(None, os.path.dirname(os.path.join(tmp, path)))
        with open(os.path.join(tmp, path), "w") as fl:
            fl.write("foo")

    for link_dst, linked_file in symlinks:
        mkdir(None, os.path.dirname(os.path.join(tmp, linked_file)))
        os.symlink(link_dst, os.path.join(tmp, linked_file))
    return tmp, outside_folder


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks Not in Windows")
def test_absolute_to_relative_symlinks(folders):
    """If a symlink is absolute but relative to a file or folder that is contained in
    the base folder, we can make it relative"""

    folder, outside_folder = folders
    # Transform the absolute symlinks to relative
    tools.files.symlinks.absolute_to_relative_symlinks(None, folder)

    # Check the results
    linked_to = os.readlink(os.path.join(folder, "foo/var/other/absolute.txt")).replace("\\", "/")
    assert linked_to == "../file.txt"

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/other/myfolder")).replace("\\", "/")
    assert linked_to == "../.."

    linked_to = os.readlink(os.path.join(folder, "foo/absolute.txt")).replace("\\", "/")
    assert linked_to == "var/file.txt"

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/relative.txt")).replace("\\", "/")
    assert linked_to == "foo/var/file.txt"

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/broken.txt"))
    assert linked_to == "missing.txt"

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/absolute_outside"))
    assert linked_to == outside_folder


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks Not in Windows")
def test_remove_external_symlinks(folders):

    folder, outside_folder = folders
    # Remove the external symlinks
    tools.files.symlinks.remove_external_symlinks(None, folder)

    # Check the results, these are kept the same
    linked_to = os.readlink(os.path.join(folder, "foo/var/other/absolute.txt"))
    assert linked_to == os.path.join(folder, "foo/var/file.txt")

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/other/myfolder"))
    assert linked_to == os.path.join(folder, "foo/var")

    linked_to = os.readlink(os.path.join(folder, "foo/absolute.txt"))
    assert linked_to == os.path.join(folder, "foo/var/file.txt")

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/relative.txt"))
    assert linked_to == "foo/var/file.txt"

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/broken.txt"))
    assert linked_to == "missing.txt"

    # This one is removed
    assert not os.path.islink(os.path.join(folder, "foo/var/other/absolute_outside"))
    assert not os.path.exists(os.path.join(folder, "foo/var/other/absolute_outside"))

    # This one is removed
    assert not os.path.islink(os.path.join(folder, "foo/absolute_outside"))
    assert not os.path.exists(os.path.join(folder, "foo/absolute_outside"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks Not in Windows")
def test_remove_broken_symlinks(folders):
    folder, outside_folder = folders
    # Remove the external symlinks
    tools.files.symlinks.remove_broken_symlinks(None, folder)

    # Check the results, these are kept the same
    linked_to = os.readlink(os.path.join(folder, "foo/var/other/absolute.txt"))
    assert linked_to == os.path.join(folder, "foo/var/file.txt")

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/other/myfolder"))
    assert linked_to == os.path.join(folder, "foo/var")

    linked_to = os.readlink(os.path.join(folder, "foo/absolute.txt"))
    assert linked_to == os.path.join(folder, "foo/var/file.txt")

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/relative.txt"))
    assert linked_to == "foo/var/file.txt"

    # This one is removed
    assert not os.path.islink(os.path.join(folder, "foo/var/other/broken.txt"))
    assert not os.path.exists(os.path.join(folder, "foo/var/other/broken.txt"))

    linked_to = os.readlink(os.path.join(folder, "foo/var/other/absolute_outside"))
    assert linked_to == outside_folder

    # This is broken also so it is also removed
    assert not os.path.islink(os.path.join(folder, "foo/absolute_outside"))
    assert not os.path.exists(os.path.join(folder, "foo/absolute_outside"))
