import os
import platform
import textwrap
import unittest

import pytest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer, TurboTestClient
from conans.util.files import load, mkdir, save

conanfile = """
from conans import ConanFile
from conans.util.files import save
import os

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"

    def build(self):
        save("file1.txt", "Hello1")
        os.symlink("file1.txt", "file1.txt.1")
        save("version1/file2.txt", "Hello2")
        os.symlink("version1", "latest")
        os.symlink("latest", "edge")
        os.symlink("empty_folder", "broken_link")
        os.makedirs("other_empty_folder")
        os.symlink("other_empty_folder", "other_link")

    def package(self):
        self.copy("*.txt*", links=True)
        self.copy("*.so*", links=True)
"""

test_conanfile = """[requires]
Hello/0.1@lasote/stable

[imports]
., * -> .
"""


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
class SymLinksTest(unittest.TestCase):

    def _check(self, client, ref, build=True):
        folders = [client.cache.package_layout(ref.ref).package(ref), client.current_folder]
        if build:
            folders.append(client.cache.package_layout(ref.ref).build(ref))
        for base in folders:
            filepath = os.path.join(base, "file1.txt")
            link = os.path.join(base, "file1.txt.1")
            self.assertEqual(os.readlink(link), "file1.txt")
            file1 = load(filepath)
            self.assertEqual("Hello1", file1)
            file1 = load(link)
            self.assertEqual("Hello1", file1)
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

        client.run("export . lasote/stable")
        client.run("install conanfile.txt --build")
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)

        self._check(client, pref)

        client.run("install conanfile.txt --build")
        self._check(client, pref)

    def test_package_files(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package(self):
        self.copy("*", symlinks=True)
    """
        client.save({"recipe/conanfile.py": conanfile})
        file1 = os.path.join(client.current_folder, "file1.txt")
        file2 = os.path.join(client.current_folder, "version1/file2.txt")
        file11 = os.path.join(client.current_folder, "file1.txt.1")
        latest = os.path.join(client.current_folder, "latest")
        edge = os.path.join(client.current_folder, "edge")
        save(file1, "Hello1")
        os.symlink("file1.txt", file11)
        save(file2, "Hello2")
        os.symlink("version1", latest)
        os.symlink("latest", edge)
        client.run("export-pkg ./recipe Hello/0.1@lasote/stable")
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)

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

        client.run("export . lasote/stable")
        client.run("install conanfile.txt --build")
        client.run("copy Hello/0.1@lasote/stable team/testing --all")
        ref = ConanFileReference.loads("Hello/0.1@lasote/stable")
        team_ref = ConanFileReference.loads("Hello/0.1@team/testing")
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        team_pref = PackageReference(team_ref, NO_SETTINGS_PACKAGE_ID)

        for folder in [client.cache.package_layout(ref).export(),
                       client.cache.package_layout(ref).source(),
                       client.cache.package_layout(ref).build(pref),
                       client.cache.package_layout(ref).package(pref),
                       client.cache.package_layout(team_ref).export(),
                       client.cache.package_layout(team_ref).package(team_pref)]:
            exported_lib = os.path.join(folder, lib_name)
            exported_link = os.path.join(folder, link_name)
            self.assertEqual(os.readlink(exported_link), lib_name)

            self.assertEqual(load(exported_lib), load(exported_link))
            self.assertTrue(os.path.islink(exported_link))

        self._check(client, pref)

    def test_upload(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        client.save({"conanfile.py": conanfile,
                     "conanfile.txt": test_conanfile})

        client.run("export . lasote/stable")
        client.run("install conanfile.txt --build")
        pref = PackageReference.loads("Hello/0.1@lasote/stable:%s" % NO_SETTINGS_PACKAGE_ID)

        client.run("upload Hello/0.1@lasote/stable --all")
        client.run('remove "*" -f')
        client.save({"conanfile.txt": test_conanfile}, clean_first=True)
        client.run("install conanfile.txt")
        self._check(client, pref, build=False)

    def test_export_pattern(self):
        conanfile = """from conans import ConanFile
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
            client.run("export . danimtb/testing")
            ref = ConanFileReference("ConanSymlink", "3.0.0", "danimtb", "testing")
            export_sources = client.cache.package_layout(ref).export_sources()
            cache_other_dir = os.path.join(export_sources, "another_other_directory")
            cache_src = os.path.join(export_sources, "src")
            cache_main = os.path.join(cache_src, "main.cpp")
            cache_cmake = os.path.join(export_sources, "CMakeLists.txt")
            self.assertFalse(os.path.exists(cache_other_dir))
            self.assertTrue(os.path.exists(cache_src))
            self.assertTrue(os.path.exists(cache_main))
            self.assertTrue(os.path.exists(cache_cmake))

    def test_export_ignore_case(self):
        conanfile = """from conans import ConanFile
class ConanSymlink(ConanFile):
    name = "ConanSymlink"
    version = "3.0.0"
    exports_sources = ["*"]
    def package(self):
        self.copy("*NOT_TO_COPY.TXT", ignore_case=%s)
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
        ref = ConanFileReference("ConanSymlink", "3.0.0", "danimtb", "testing")
        cache_file = os.path.join(client.cache.package_layout(ref).export_sources(),
                                  "another_directory", "not_to_copy.txt")
        self.assertTrue(os.path.exists(cache_file))
        cache_other_dir = os.path.join(client.cache.package_layout(ref).export_sources(),
                                       "another_other_directory")
        self.assertTrue(os.path.exists(cache_other_dir))
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID)
        package_file = os.path.join(client.cache.package_layout(pref.ref).package(pref),
                                    "another_directory", "not_to_copy.txt")
        self.assertFalse(os.path.exists(package_file))
        package_other_dir = os.path.join(client.cache.package_layout(pref.ref).package(pref),
                                         "another_other_directory")
        self.assertFalse(os.path.exists(package_other_dir))
        client.save({"conanfile.py": conanfile % "True"})
        client.run("create . danimtb/testing")
        self.assertTrue(os.path.exists(package_file))
        self.assertTrue(os.path.exists(package_other_dir))

    def test_create_keep_folder_symlink(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile
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

        ref = ConanFileReference.loads("ConanSymlink/3.0.0@user/channel")
        package_layout = client.cache.package_layout(ref)
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
        bf = client.cache.package_layout(pref.ref).build(pref)
        bf_symlink = os.path.join(bf, "debug")
        self.assertTrue(os.path.islink(bf_symlink))
        self.assertEqual(os.path.realpath(bf_symlink), os.path.join(bf, "release"))


@pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
class SymlinkExportSources(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

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

        t.run("create . user/channel")

        # Check that things are in place (in the cache): exists and points to 'source' directory
        layout = t.cache.package_layout(ConanFileReference.loads("symlinks/1.0.0@user/channel"))
        cache_content = os.path.join(layout.source(), relpath_content)
        self.assertTrue(os.path.exists(cache_content))
        self.assertEqual(os.path.realpath(cache_content),
                         os.path.join(layout.source(), relpath_v1, 'headers', 'content'))
