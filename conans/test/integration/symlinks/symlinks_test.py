import os
import platform
import textwrap
import unittest

import pytest

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, TurboTestClient
from conans.util.files import load, mkdir, save

conanfile = """
from conan import ConanFile
from conan.tools.files import save, copy
import os

class HelloConan(ConanFile):
    name = "hello"
    version = "0.1"
    exports = "*"

    def build(self):
        save(self, "file1.txt", "hello1")
        os.symlink("file1.txt", "file1.txt.1")
        save(self, "version1/file2.txt", "Hello2")
        os.symlink("version1", "latest")
        os.symlink("latest", "edge")
        os.symlink("empty_folder", "broken_link")
        os.makedirs("other_empty_folder")
        os.symlink("other_empty_folder", "other_link")

    def package(self):
        copy(self, "*.txt*", self.build_folder, self.package_folder)
        copy(self, "*.so*", self.build_folder, self.package_folder)
"""

test_conanfile = """[requires]
hello/0.1@lasote/stable

[imports]
., * -> .
"""


@pytest.mark.xfail(reason="cache2.0 revisit test")
@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
class SymLinksTest(unittest.TestCase):

    def _check(self, client, pref, build=True):
        pkg_layout = client.get_latest_pkg_layout(pref)
        folders = [pkg_layout.package(), client.current_folder]
        if build:
            folders.append(pkg_layout.build())
        for base in folders:
            filepath = os.path.join(base, "file1.txt")
            link = os.path.join(base, "file1.txt.1")
            self.assertEqual(os.readlink(link), "file1.txt")
            file1 = load(filepath)
            self.assertEqual("hello1", file1)
            file1 = load(link)
            self.assertEqual("hello1", file1)
            # Save any different string, random, or the base path
            save(filepath, base)
            self.assertEqual(load(link), base)
            link = os.path.join(base, "latest")
            self.assertEqual(os.readlink(link), "version1")
            filepath = os.path.join(base, "latest/file2.txt")
            file1 = load(filepath)
            self.assertEqual("Hello2", file1)
            filepath = os.path.join(base, "edge/file2.txt")
            file1 = load(filepath)
            self.assertEqual("Hello2", file1)

    def test_basic(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})

        client.run("export . --user=lasote --channel=stable")
        client.run("install conanfile.txt --build")
        pref = PkgReference.loads("hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)

        self._check(client, pref)

        client.run("install conanfile.txt --build")
        self._check(client, pref)

    def test_package_files(self):
        client = TestClient()
        conanfile = """
from conan import ConanFile
from conan.tools.files import copy

class TestConan(ConanFile):
    name = "hello"
    version = "0.1"

    def package(self):
        copy(self, "*", self.build_folder, self.package_folder)
    """
        client.save({"recipe/conanfile.py": conanfile})
        file1 = os.path.join(client.current_folder, "file1.txt")
        file2 = os.path.join(client.current_folder, "version1/file2.txt")
        file11 = os.path.join(client.current_folder, "file1.txt.1")
        latest = os.path.join(client.current_folder, "latest")
        edge = os.path.join(client.current_folder, "edge")
        save(file1, "hello1")
        os.symlink("file1.txt", file11)
        save(file2, "Hello2")
        os.symlink("version1", latest)
        os.symlink("latest", edge)
        client.run("export-pkg  ./recipe  --name=hello --version=0.1 --user=lasote --channel=stable")
        pref = PkgReference.loads("hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)

        self._check(client, pref, build=False)

    def test_export_and_copy(self):
        lib_name = "libtest.so.2"
        lib_contents = "TestLib"
        link_name = "libtest.so"

        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile,
                     lib_name: lib_contents})

        pre_export_link = os.path.join(client.current_folder, link_name)
        os.symlink(lib_name, pre_export_link)

        client.run("export . --user=lasote --channel=stable")
        client.run("install conanfile.txt --build")
        ref = RecipeReference.loads("hello/0.1@lasote/stable")
        pref = PkgReference(ref, NO_SETTINGS_PACKAGE_ID)

        pkg_layout = client.get_latest_pkg_layout(pref)
        ref_layout = client.get_latest_ref_layout(ref)

        for folder in [ref_layout.export(),
                       ref_layout.source(),
                       pkg_layout.build(),
                       pkg_layout.package()]:
            exported_lib = os.path.join(folder, lib_name)
            exported_link = os.path.join(folder, link_name)
            self.assertEqual(os.readlink(exported_link), lib_name)

            self.assertEqual(load(exported_lib), load(exported_link))
            self.assertTrue(os.path.islink(exported_link))

        self._check(client, pref)

    def test_upload(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["admin", "password"])

        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})

        client.run("export . --user=lasote --channel=stable")
        client.run("install conanfile.txt --build")
        pref = PkgReference.loads("hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)

        client.run("upload hello/0.1@lasote/stable -r default")
        client.run('remove "*" -c')
        client.save({"conanfile.txt": test_conanfile}, clean_first=True)
        client.run("install conanfile.txt")
        self._check(client, pref, build=False)

    def test_export_pattern(self):
        conanfile = """from conan import ConanFile
class ConanSymlink(ConanFile):
    name = "ConanSymlink"
    version = "3.0.0"
    exports_sources = %s
"""
        for export_sources in ["['src/*', 'CMakeLists.txt']", "['*', '!*another_directory*']"]:
            client = TestClient()
            client.save({"conanfile.py": conanfile % export_sources,
                         "src/main.cpp": "cpp fake content",
                         "CMakeLists.txt": "cmake fake content",
                         "another_directory/not_to_copy.txt": ""})
            mkdir(os.path.join(client.current_folder, "another_other_directory"))
            symlink_path = os.path.join(client.current_folder, "another_other_directory",
                                        "another_directory")
            symlinked_path = os.path.join(client.current_folder, "another_directory")
            self.assertFalse(os.path.exists(symlink_path))
            self.assertTrue(os.path.exists(symlinked_path))
            os.symlink(symlinked_path, symlink_path)
            client.run("export . --user=danimtb --channel=testing")
            ref = RecipeReference("ConanSymlink", "3.0.0", "danimtb", "testing")
            export_sources = client.get_latest_ref_layout(ref).export_sources()
            cache_other_dir = os.path.join(export_sources, "another_other_directory")
            cache_src = os.path.join(export_sources, "src")
            cache_main = os.path.join(cache_src, "main.cpp")
            cache_cmake = os.path.join(export_sources, "CMakeLists.txt")
            self.assertFalse(os.path.exists(cache_other_dir))
            self.assertTrue(os.path.exists(cache_src))
            self.assertTrue(os.path.exists(cache_main))
            self.assertTrue(os.path.exists(cache_cmake))

    def test_export_ignore_case(self):
        conanfile = """from conan import ConanFile
class ConanSymlink(ConanFile):
    name = "ConanSymlink"
    version = "3.0.0"
    exports_sources = ["*"]
    def package(self):
        copy(self, "*NOT_TO_COPY.TXT", self.source_folder, self.package_folder, ignore_case=%s)
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile % "False",
                     "src/main.cpp": "cpp fake content",
                     "CMakeLists.txt": "cmake fake content",
                     "another_directory/not_to_copy.txt": ""})
        mkdir(os.path.join(client.current_folder, "another_other_directory"))
        symlink_path = os.path.join(client.current_folder, "another_other_directory",
                                    "another_directory")
        symlinked_path = os.path.join(client.current_folder, "another_directory")
        self.assertFalse(os.path.exists(symlink_path))
        self.assertTrue(os.path.exists(symlinked_path))
        os.symlink(symlinked_path, symlink_path)
        client.run("create . danimtb/testing")
        ref = RecipeReference("ConanSymlink", "3.0.0", "danimtb", "testing")
        cache_file = os.path.join(client.get_latest_ref_layout(ref).export_sources(),
                                  "another_directory", "not_to_copy.txt")
        self.assertTrue(os.path.exists(cache_file))
        cache_other_dir = os.path.join(client.get_latest_ref_layout(ref).export_sources(),
                                       "another_other_directory")
        self.assertTrue(os.path.exists(cache_other_dir))
        pref = PkgReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_file = os.path.join(client.get_latest_pkg_layout(pref).package(),
                                    "another_directory", "not_to_copy.txt")
        self.assertFalse(os.path.exists(package_file))
        package_other_dir = os.path.join(client.get_latest_pkg_layout(pref).package(),
                                         "another_other_directory")
        self.assertFalse(os.path.exists(package_other_dir))
        client.save({"conanfile.py": conanfile % "True"})
        client.run("create . danimtb/testing")
        self.assertTrue(os.path.exists(package_file))
        self.assertTrue(os.path.exists(package_other_dir))

    def test_create_keep_folder_symlink(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            class ConanSymlink(ConanFile):
                name = "ConanSymlink"
                version = "3.0.0"
                exports_sources = ["*"]
                def build(self):
                    debug_path = os.path.join(self.build_folder, "debug")
                    assert os.path.exists(debug_path), "Symlinked folder not created!"
            """)

        client = TurboTestClient()
        client.save({"conanfile.py": conanfile})
        client.save({"release/file.cpp": conanfile})
        real_dir_path = os.path.join(client.current_folder, "release")
        symlink_path = os.path.join(client.current_folder, "debug")
        os.symlink(real_dir_path, symlink_path)

        # Verify that the symlink is created correctly
        self.assertEqual(os.path.realpath(symlink_path), real_dir_path)

        ref = RecipeReference.loads("ConanSymlink/3.0.0@user/channel")
        package_layout = client.get_latest_ref_layout(ref)
        # Export the recipe and check that the symlink is still there
        client.export(ref, conanfile=conanfile)
        sf = package_layout.export_sources()
        sf_symlink = os.path.join(sf, "debug")
        self.assertTrue(os.path.islink(sf_symlink))
        self.assertEqual(os.path.realpath(sf_symlink), os.path.join(sf, "release"))

        # Now do the create
        pref = client.create(ref, conanfile=conanfile)
        # Assert that the symlink is preserved when copy to source from exports_sources
        sf = package_layout.source()
        sf_symlink = os.path.join(sf, "debug")
        self.assertTrue(os.path.islink(sf_symlink))
        self.assertEqual(os.path.realpath(sf_symlink), os.path.join(sf, "release"))

        # Assert that the symlink is preserved when copy to build folder
        bf = client.get_latest_pkg_layout(pref).build()
        bf_symlink = os.path.join(bf, "debug")
        self.assertTrue(os.path.islink(bf_symlink))
        self.assertEqual(os.path.realpath(bf_symlink), os.path.join(bf, "release"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
class SymlinkExportSources(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class SymlinksConan(ConanFile):
            name = "symlinks"
            version = "1.0.0"
            exports_sources = "src/*"
        """)

    def test_create_source(self):
        # Reproduces issue: https://github.com/conan-io/conan/issues/5329
        t = TestClient()
        relpath_v1 = os.path.join('src', 'framework', 'Versions', 'v1')
        t.save({'conanfile.py': self.conanfile,
                os.path.join(relpath_v1, 'headers', 'content'): "whatever",
                os.path.join(relpath_v1, 'file'): "content"})

        # Add two levels of symlinks
        os.symlink('v1', os.path.join(t.current_folder, 'src', 'framework', 'Versions', 'Current'))
        os.symlink('Versions/Current/headers',
                   os.path.join(t.current_folder, 'src', 'framework', 'headers'))
        os.symlink('Versions/Current/file',
                   os.path.join(t.current_folder, 'src', 'framework', 'file'))

        # Check that things are in place (locally): file exists and points to local directory
        relpath_content = os.path.join('src', 'framework', 'headers', 'content')
        local_content = os.path.join(t.current_folder, relpath_content)
        self.assertTrue(os.path.exists(local_content))
        self.assertEqual(os.path.realpath(local_content),
                         os.path.join(t.current_folder, relpath_v1, 'headers', 'content'))

        t.run("create . --user=user --channel=channel")

        # Check that things are in place (in the cache): exists and points to 'source' directory
        layout = t.get_latest_ref_layout(RecipeReference.loads("symlinks/1.0.0@user/channel"))
        cache_content = os.path.join(layout.source(), relpath_content)
        self.assertTrue(os.path.exists(cache_content))
        self.assertEqual(os.path.realpath(cache_content),
                         os.path.join(layout.source(), relpath_v1, 'headers', 'content'))
