import os
import platform
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import PACKAGE_TGZ_NAME
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, TestServer, TurboTestClient
from conans.util.files import load, rmdir, chdir, save

links_conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.files import copy

    class HelloConan(ConanFile):
        name = "hello"
        version = "0.1"
        exports_sources = "*"

        def package(self):
            copy(self, "*", self.build_folder, self.package_folder)
    """)


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
def test_complete_round_trip():
    """ a full round trip with a in package symlink, that is maintained all the way to
    the server and re-deployed in the client
    the symlink is relative just "link.txt" -> "midlink.txt" -> "target.txt" (local)
    """
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": links_conanfile,
            "target.txt": "hello world!"})
    os.symlink("target.txt", os.path.join(c.current_folder, "midlink.txt"))
    os.symlink("midlink.txt", os.path.join(c.current_folder, "link.txt"))
    assert c.load("link.txt") == "hello world!"

    c.run("create .")

    def checker(folder):
        with chdir(folder):
            assert os.path.exists("target.txt")
            assert os.readlink("link.txt") == "midlink.txt"
            assert os.readlink("midlink.txt") == "target.txt"
            assert load("link.txt") == "hello world!"

    ref = RecipeReference.loads("hello/0.1")
    checker(c.get_latest_ref_layout(ref).source())
    pref = c.get_latest_package_reference(ref)
    pkg_layout = c.get_latest_pkg_layout(pref)
    checker(pkg_layout.build())
    checker(pkg_layout.package())

    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.save({}, clean_first=True)
    c.run("install --requires=hello/0.1 --deployer=full_deploy")
    checker(os.path.join(c.current_folder, "full_deploy", "host", "hello", "0.1"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
def test_complete_round_trip_broken_link():
    """ same as above but with a broken one
    link.txt->midlink.txt->(broken)
    """
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": links_conanfile})
    os.symlink("target.txt", os.path.join(c.current_folder, "midlink.txt"))
    os.symlink("midlink.txt", os.path.join(c.current_folder, "link.txt"))

    c.run("create .")

    def checker(folder):
        with chdir(folder):
            assert not os.path.exists("target.txt")
            assert os.readlink("link.txt") == "midlink.txt"
            assert os.readlink("midlink.txt") == "target.txt"

    ref = RecipeReference.loads("hello/0.1")
    checker(c.get_latest_ref_layout(ref).source())
    pref = c.get_latest_package_reference(ref)
    pkg_layout = c.get_latest_pkg_layout(pref)
    checker(pkg_layout.build())
    checker(pkg_layout.package())

    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.save({}, clean_first=True)
    c.run("install --requires=hello/0.1 --deployer=full_deploy")
    checker(os.path.join(c.current_folder, "full_deploy", "host", "hello", "0.1"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
def test_complete_round_trip_external_link():
    """ same as above but with a broken one
    link.txt->midlink.txt->/abs/path/to/target.txt
    """
    c = TestClient(default_server_user=True)
    target = os.path.join(temp_folder(), "target.txt")
    save(target, "foo")

    c.save({"conanfile.py": links_conanfile})
    os.symlink(target, os.path.join(c.current_folder, "midlink.txt"))
    os.symlink("midlink.txt", os.path.join(c.current_folder, "link.txt"))

    c.run("create .")

    def checker(folder):
        with chdir(folder):
            assert "target.txt" not in os.listdir(".")
            assert not os.path.exists("target.txt")
            assert os.readlink("link.txt") == "midlink.txt"
            assert os.readlink("midlink.txt") == target
            assert load("link.txt") == "foo"

    ref = RecipeReference.loads("hello/0.1")
    checker(c.get_latest_ref_layout(ref).source())
    pref = c.get_latest_package_reference(ref)
    pkg_layout = c.get_latest_pkg_layout(pref)
    checker(pkg_layout.build())
    checker(pkg_layout.package())

    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.save({}, clean_first=True)
    c.run("install --requires=hello/0.1 --deployer=full_deploy")
    checker(os.path.join(c.current_folder, "full_deploy", "host", "hello", "0.1"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
def test_complete_round_trip_folders():
    """ similar to above, but with 2 folder symlinks and one file symlink
    # Reproduces issue: https://github.com/conan-io/conan/issues/5329
    """
    c = TestClient(default_server_user=True)

    c.save({"conanfile.py": links_conanfile,
            "src/framework/Versions/v1/headers/content": "myheader!",
            "src/framework/Versions/v1/file": "myfile!"})

    # Add two levels of symlinks
    os.symlink('v1', os.path.join(c.current_folder, 'src', 'framework', 'Versions', 'Current'))
    os.symlink('Versions/Current/headers',
               os.path.join(c.current_folder, 'src', 'framework', 'headers'))
    os.symlink('Versions/Current/file',
               os.path.join(c.current_folder, 'src', 'framework', 'file'))

    c.run("create .")

    def checker(folder):
        with chdir(folder):
            assert os.readlink("src/framework/Versions/Current") == "v1"
            assert os.readlink("src/framework/headers") == "Versions/Current/headers"
            assert os.readlink("src/framework/file") == "Versions/Current/file"
            assert os.path.exists("src/framework/Versions/v1/headers/content")
            assert os.path.exists("src/framework/Versions/v1/file")

            assert load("src/framework/file") == "myfile!"
            assert load("src/framework/headers/content") == "myheader!"

    ref = RecipeReference.loads("hello/0.1")
    checker(c.get_latest_ref_layout(ref).source())
    pref = c.get_latest_package_reference(ref)
    pkg_layout = c.get_latest_pkg_layout(pref)
    checker(pkg_layout.build())
    checker(pkg_layout.package())

    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.save({}, clean_first=True)
    c.run("install --requires=hello/0.1 --deployer=full_deploy")
    checker(os.path.join(c.current_folder, "full_deploy", "host", "hello", "0.1"))


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
@pytest.mark.parametrize("package_files",
                         [{"files": ["foo/bar/folder/file.txt",
                                     "foo/bar/folder/other/other_file.txt"],
                           "symlinks": [("../file.txt", "foo/bar/folder/other/file2.txt")]},
                          # relative ../ symlink
                          {"files": ["foo/bar/file/file.txt"],
                           "symlinks": [(temp_folder(), "foo/symlink_folder")]},  # absolute symlink
                          {"files": ["folder/file.txt"],
                           "symlinks": [("folder", "folder2"),
                                        ("file.txt", "folder/file2.txt")]},  # single level symlink
                          {"files": ["foo/bar/file/file.txt"],
                           "symlinks": [("bar/file", "foo/symlink_folder"),
                                        ("foo/symlink_folder/file.txt", "file2.txt")]},
                          # double level symlink
                          ])
def test_package_with_symlinks(package_files):

    client = TurboTestClient(default_server_user=True)
    client2 = TurboTestClient(servers=client.servers)
    client.save({"conanfile.py": links_conanfile})

    for path in package_files["files"]:
        client.save({path: "foo contents"})

    for link_dest, link_file in package_files["symlinks"]:
        os.symlink(link_dest, os.path.join(client.current_folder, link_file))

    pref = client.create(RecipeReference.loads("hello/0.1"), conanfile=False)

    def assert_folder_symlinks(base_folder):
        with chdir(base_folder):
            for f in package_files["files"]:
                assert os.path.exists(f)
            for link_dst, link in package_files["symlinks"]:
                assert os.readlink(link) == link_dst
                if os.path.isfile(link):
                    assert load(link) == "foo contents"

    # Check exported sources are there
    ref_layout = client.get_latest_ref_layout(pref.ref)
    assert_folder_symlinks(ref_layout.export_sources())
    assert_folder_symlinks(ref_layout.source())

    # Check files have been copied to the build
    pkg_layout = client.get_latest_pkg_layout(pref)
    assert_folder_symlinks(pkg_layout.build())
    assert_folder_symlinks(pkg_layout.package())

    client.run("upload '*' -c -r default")
    client.run("remove * -c")

    # Client 2 install
    client2.run("install --requires=hello/0.1 --deployer=full_deploy")
    # Check package files are there
    package_folder = client2.get_latest_pkg_layout(pref).package()
    assert_folder_symlinks(package_folder)
    assert_folder_symlinks(os.path.join(client2.current_folder, "full_deploy", "host", "hello", "0.1"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Symlinks not in Windows")
def test_exports_does_not_follow_symlink():
    tmp = temp_folder()
    linked_abs_folder = tmp
    save(os.path.join(tmp, "source.cpp"), "foo")
    client = TurboTestClient(default_server_user=True)
    conanfile = GenConanfile()\
        .with_package('copy(self, "*", self.source_folder, self.package_folder)')\
        .with_exports_sources("*")\
        .with_import("from conan.tools.files import copy")
    client.save({"conanfile.py": conanfile, "foo.txt": "bar"})
    os.symlink(linked_abs_folder, os.path.join(client.current_folder, "linked_folder"))
    pref = client.create(RecipeReference.loads("lib/1.0"), conanfile=False)
    exports_sources_folder = client.get_latest_ref_layout(pref.ref).export_sources()
    assert os.path.islink(os.path.join(exports_sources_folder, "linked_folder"))
    assert os.path.exists(os.path.join(exports_sources_folder, "linked_folder", "source.cpp"))

    # Check files have been copied to the build
    build_folder = client.get_latest_pkg_layout(pref).build()
    assert os.path.islink(os.path.join(build_folder, "linked_folder"))
    assert os.path.exists(os.path.join(build_folder, "linked_folder", "source.cpp"))

    # Check package files are there
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.islink(os.path.join(package_folder, "linked_folder"))
    assert os.path.exists(os.path.join(package_folder, "linked_folder", "source.cpp"))

    # Check that the manifest doesn't contain the symlink nor the source.cpp
    contents = load(os.path.join(package_folder, "conanmanifest.txt"))
    assert "foo.txt" in contents
    assert "linked_folder" not in contents
    assert "source.cpp" not in contents

    # Now is a broken link, but the files are not in the cache, just a broken link
    rmdir(linked_abs_folder)
    assert not os.path.exists(os.path.join(exports_sources_folder, "linked_folder", "source.cpp"))
    assert not os.path.exists(os.path.join(build_folder, "linked_folder", "source.cpp"))
    assert not os.path.exists(os.path.join(package_folder, "linked_folder", "source.cpp"))


@pytest.mark.skipif(platform.system() != "Linux", reason="Only linux")
def test_package_symlinks_zero_size():
    server = TestServer()
    client = TurboTestClient(servers={"default": server}, inputs=["admin", "password"])

    conanfile = """
import os
from conan import ConanFile
from conan.tools.files import save

class HelloConan(ConanFile):

    def package(self):
        # Link to file.txt and then remove it
        save(self, os.path.join(self.package_folder, "file.txt"), "contents")
        os.symlink("file.txt", os.path.join(self.package_folder, "link.txt"))
"""
    ref = RecipeReference.loads("lib/1.0@conan/stable")
    # By default it is not allowed
    pref = client.create(ref, conanfile=conanfile)
    # Upload, it will create the tgz
    client.upload_all(ref)

    # We can uncompress it without warns
    p_folder = client.get_latest_pkg_layout(pref).download_package()
    tgz = os.path.join(p_folder, PACKAGE_TGZ_NAME)
    client.run_command('gzip -d "{}"'.format(tgz))
    client.run_command('tar tvf "{}"'.format(os.path.join(p_folder, "conan_package.tar")))
    lines = str(client.out).splitlines()
    """
-rw-r--r-- 0/0               8 1970-01-01 01:00 file.txt
lrw-r--r-- 0/0               0 1970-01-01 01:00 link.txt -> file.txt
    """

    assert "link.txt" in " ".join(lines)
    for line in lines:
        if ".txt" not in line:
            continue

        size = int([i for i in line.split(" ") if i][2])
        if "link.txt" in line:
            assert int(size) == 0
        elif "file.txt":
            assert int(size) > 0
