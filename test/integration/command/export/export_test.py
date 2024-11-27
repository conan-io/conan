import json
import os
import platform
import stat
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.model.manifest import FileTreeManifest
from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import CONANFILE, CONAN_MANIFEST
from conan.test.utils.tools import TestClient, GenConanfile
from conans.util.files import load, save


class ExportSettingsTest(unittest.TestCase):

    def test_export_without_full_reference(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --user=lasote --channel=stable", assert_error=True)
        self.assertIn("conanfile didn't specify name", client.out)

        client.save({"conanfile.py": GenConanfile("lib")})
        client.run("export . --user=lasote --channel=stable", assert_error=True)
        self.assertIn("conanfile didn't specify version", client.out)

        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=lib --version=1.0 --user=lasote --channel=channel")
        self.assertIn("lib/1.0@lasote/channel: Exported", client.out)

        client.save({"conanfile.py": GenConanfile("lib", "1.0")})
        client.run("export . --user=lasote")
        self.assertIn("lib/1.0@lasote: Exporting package recipe", client.out)

    def test_export_read_only(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class TestConan(ConanFile):
                name = "hello"
                version = "1.2"
                exports = "file1.txt"
                exports_sources = "file2.txt"
            """)
        client.save({CONANFILE: conanfile,
                     "file1.txt": "",
                     "file2.txt": ""})
        mode1 = os.stat(os.path.join(client.current_folder, "file1.txt")).st_mode
        mode2 = os.stat(os.path.join(client.current_folder, "file2.txt")).st_mode
        os.chmod(os.path.join(client.current_folder, "file1.txt"), mode1 & ~stat.S_IWRITE)
        os.chmod(os.path.join(client.current_folder, "file2.txt"), mode2 & ~stat.S_IWRITE)

        client.run("export . --user=lasote --channel=stable")

        layout = client.exported_layout()
        export_path = layout.export()
        export_src_path = layout.export_sources()

        self.assertEqual(load(os.path.join(export_path, "file1.txt")), "")
        self.assertEqual(load(os.path.join(export_src_path, "file2.txt")), "")
        with self.assertRaises(IOError):
            save(os.path.join(export_path, "file1.txt"), "")
        with self.assertRaises(IOError):
            save(os.path.join(export_src_path, "file2.txt"), "")

        os.chmod(os.path.join(client.current_folder, "file1.txt"), mode1 | stat.S_IWRITE)
        os.chmod(os.path.join(client.current_folder, "file2.txt"), mode2 | stat.S_IWRITE)
        client.save({CONANFILE: conanfile,
                     "file1.txt": "file1",
                     "file2.txt": "file2"})
        client.run("export . --user=lasote --channel=stable")

        layout = client.exported_layout()
        export_path = layout.export()
        export_src_path = layout.export_sources()

        self.assertEqual(load(os.path.join(export_path, "file1.txt")), "file1")
        self.assertEqual(load(os.path.join(export_src_path, "file2.txt")), "file2")
        client.run("install --requires=hello/1.2@lasote/stable --build=missing")
        self.assertIn("hello/1.2@lasote/stable: Generating the package", client.out)

        client.save({CONANFILE: conanfile,
                     "file1.txt": "",
                     "file2.txt": ""})
        os.chmod(os.path.join(client.current_folder, "file1.txt"), mode1 & ~stat.S_IWRITE)
        os.chmod(os.path.join(client.current_folder, "file2.txt"), mode2 & ~stat.S_IWRITE)
        client.run("export . --user=lasote --channel=stable")

        layout = client.exported_layout()
        export_path = layout.export()
        export_src_path = layout.export_sources()

        self.assertEqual(load(os.path.join(export_path, "file1.txt")), "")
        self.assertEqual(load(os.path.join(export_src_path, "file2.txt")), "")
        client.run("install --requires=hello/1.2@lasote/stable --build=hello*")
        self.assertIn("hello/1.2@lasote/stable: Generating the package", client.out)

    def test_code_parent(self):
        # when referencing the parent, the relative folder "sibling" will be kept
        base = """
import os
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):
    name = "hello"
    version = "1.2"
    def export(self):
        copy(self, "*.txt", src=os.path.join(self.recipe_folder, ".."),
             dst=self.export_folder)
"""
        for conanfile in (base, base.replace("../*.txt", "../sibling*")):
            client = TestClient()
            client.save({"recipe/conanfile.py": conanfile,
                         "sibling/file.txt": "Hello World!"})
            client.current_folder = os.path.join(client.current_folder, "recipe")
            client.run("export . --user=lasote --channel=stable")
            layout = client.exported_layout()
            export_path = layout.export()
            content = load(os.path.join(export_path, "sibling/file.txt"))
            self.assertEqual("Hello World!", content)

    def test_code_sibling(self):
        # if provided a path with slash, it will use as a export base
        client = TestClient()
        conanfile = """
import os
from conan import ConanFile
from conan.tools.files import copy
class TestConan(ConanFile):
    name = "hello"
    version = "1.2"
    def export(self):
        copy(self, "*.txt", src=os.path.join(self.recipe_folder, "..", "sibling"),
             dst=self.export_folder)
"""
        files = {"recipe/conanfile.py": conanfile,
                 "sibling/file.txt": "Hello World!"}
        client.save(files)
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . --user=lasote --channel=stable")
        layout = client.exported_layout()
        export_path = layout.export()
        content = load(os.path.join(export_path, "file.txt"))
        self.assertEqual("Hello World!", content)

    def test_code_several_sibling(self):
        # if provided a path with slash, it will use as a export base
        client = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy
            class TestConan(ConanFile):
                name = "hello"
                version = "1.2"
                # exports_sources = "../test/src/*", "../cpp/*", "../include/*"
                def export_sources(self):
                    copy(self, "*", src=os.path.join(self.recipe_folder, "..", "test", "src"),
                         dst=self.export_sources_folder)
                    copy(self, "*", src=os.path.join(self.recipe_folder, "..", "cpp"),
                         dst=self.export_sources_folder)
                    copy(self, "*", src=os.path.join(self.recipe_folder, "..", "include"),
                         dst=self.export_sources_folder)

            """)
        client.save({"recipe/conanfile.py": conanfile,
                     "test/src/file.txt": "Hello World!",
                     "cpp/file.cpp": "Hello World!",
                     "include/file.h": "Hello World!"})
        client.current_folder = os.path.join(client.current_folder, "recipe")
        client.run("export . --user=lasote --channel=stable")
        layout = client.exported_layout()
        export_path = layout.export_sources()
        self.assertEqual(sorted(['file.txt', 'file.cpp', 'file.h']),
                         sorted(os.listdir(export_path)))

    @parameterized.expand([("myconanfile.py", ), ("Conanfile.py", )])
    def test_filename(self, filename):
        client = TestClient()
        client.save({filename: GenConanfile("hello", "1.2")})
        client.run("export %s --user=user --channel=stable" % filename)
        self.assertIn("hello/1.2@user/stable: Exported", client.out)
        layout = client.exported_layout()
        export_path = layout.export()
        conanfile = load(os.path.join(export_path, "conanfile.py"))
        self.assertIn("name = 'hello'", conanfile)
        manifest = load(os.path.join(export_path, "conanmanifest.txt"))
        self.assertIn('conanfile.py: 5dc49e518e15f3889cb2e097ce4d1dff', manifest)

    def test_exclude_basic(self):
        client = TestClient()
        conanfile = """
from conan import ConanFile
class TestConan(ConanFile):
    name = "hello"
    version = "1.2"
    exports = "*.txt", "!*file1.txt"
    exports_sources = "*.cpp", "!*temp.cpp"
"""

        client.save({CONANFILE: conanfile,
                     "file.txt": "",
                     "file1.txt": "",
                     "file.cpp": "",
                     "file_temp.cpp": ""})
        client.run("export . --user=lasote --channel=stable")
        layout = client.exported_layout()
        export_path = layout.export()
        exports_sources_path = layout.export_sources()
        self.assertTrue(os.path.exists(os.path.join(export_path, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(export_path, "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(exports_sources_path, "file.cpp")))
        self.assertFalse(os.path.exists(os.path.join(exports_sources_path, "file_temp.cpp")))

    def test_exclude_folders(self):
        client = TestClient()
        conanfile = """
from conan import ConanFile
class TestConan(ConanFile):
    name = "hello"
    version = "1.2"
    exports = "*.txt", "!*/temp/*"
"""

        client.save({CONANFILE: conanfile,
                     "file.txt": "",
                     "any/temp/file1.txt": "",
                     "other/sub/file2.txt": ""})
        client.run("export . --user=lasote --channel=stable")
        layout = client.exported_layout()
        export_path = layout.export()
        self.assertTrue(os.path.exists(os.path.join(export_path, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(export_path, "any/temp/file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(export_path, "other/sub/file2.txt")))


class ExportTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.files = {"conanfile.py": GenConanfile("hello0", "0.1").with_exports("*"),
                      "main.cpp": "MyMain",
                      "CMakeLists.txt": "MyCmake",
                      "executable": "myexe"}
        self.ref = RecipeReference("hello0", "0.1", "lasote", "stable")
        self.client.save(self.files)
        self.client.run("export . --user=lasote --channel=stable")

    def test_basic(self):
        reg_path = self.client.exported_layout().export()
        manif = FileTreeManifest.load(reg_path)

        self.assertIn('%s: Exported' % str(self.ref),
                      self.client.out)
        self.assertIn('%s: Exported to cache folder: %s' % (str(self.ref), reg_path), self.client.out)
        self.assertTrue(os.path.exists(reg_path))

        for name in list(self.files.keys()):
            self.assertTrue(os.path.exists(os.path.join(reg_path, name)))

        expected_sums = {'CMakeLists.txt': '3cf710785270c7e98a30d4a90ea66492',
                         'conanfile.py': '5dbbe4328efa3342baba2a7ca961ede1',
                         'executable': 'db299d5f0d82f113fad627a21f175e59',
                         'main.cpp': 'd9c03c934a4b3b1670775c17c26f39e9'}
        self.assertEqual(expected_sums, manif.file_sums)

    def test_case_sensitive(self):
        self.ref = RecipeReference("hello0", "0.1", "lasote", "stable")
        self.client.save({"conanfile.py": GenConanfile("hello0", "0.1").with_exports("*")})
        self.client.run("export . --user=lasote --channel=stable")
        self.assertIn("hello0/0.1@lasote/stable: Exported", self.client.out)

    def test_export_filter(self):
        self.client.save({CONANFILE: GenConanfile("openssl", "2.0.1")})
        self.client.run("export . --user=lasote --channel=stable")
        layout = self.client.exported_layout()
        export_path = layout.export()
        self.assertEqual(sorted(os.listdir(export_path)), [CONANFILE, CONAN_MANIFEST])

        content = """
from conan import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ('*.txt', '*.h')
"""
        self.client.save({CONANFILE: content})
        self.client.run("export . --user=lasote --channel=stable")
        layout = self.client.exported_layout()
        export_path = layout.export()
        self.assertEqual(sorted(os.listdir(export_path)), ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST])

        # Now exports being a list instead a tuple
        content = """
from conan import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    exports = ['*.txt', '*.h']
"""
        self.client.save({CONANFILE: content})
        self.client.run("export . --user=lasote --channel=stable")
        layout = self.client.exported_layout()
        export_path = layout.export()
        self.assertEqual(sorted(os.listdir(export_path)),
                         ['CMakeLists.txt', CONANFILE, CONAN_MANIFEST])


class ExportMetadataTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Lib(ConanFile):
            revision_mode = "{revision_mode}"
        """)

    summary_hash = "e87f5e4174765cc6e0cc6f24109d65ef"

    def test_revision_mode_hash(self):
        t = TestClient()
        t.save({'conanfile.py': self.conanfile.format(revision_mode="hash")})

        ref = RecipeReference.loads("name/version@user/channel")
        t.run(f"export . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
        layout = t.exported_layout()
        self.assertEqual(layout.reference.revision, self.summary_hash)

    def test_revision_mode_invalid(self):
        conanfile = self.conanfile.format(revision_mode="auto")

        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run("export . --name=name --version=version", assert_error=True)
        self.assertIn("ERROR: Revision mode should be one of 'hash' (default) or 'scm'", t.out)

    def test_export_no_params(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0")})
        client.run('export .')
        self.assertIn("lib/1.0: Exported", client.out)

    def test_export_with_name_and_version(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})

        client.run('export . --name=lib --version=1.0')
        self.assertIn("lib/1.0: Exported", client.out)

    def test_export_with_only_user_channel(self):
        """This should be the recommended way and only from Conan 2.0"""
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("lib").with_version("1.0")})

        client.run('export .  --version= --user=user --channel=channel')
        self.assertIn("lib/1.0@user/channel: Exported", client.out)

    def test_export_conflict_no_user_channel(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})

        client.run('export . --name=pkg --version=0.1 --user=user --channel=channel')
        self.assertIn("pkg/0.1@user/channel: Exported", client.out)
        client.run('export . --name=pkg --version=0.1 --user=other --channel=stable')
        self.assertIn("pkg/0.1@other/stable: Exported", client.out)
        client.run('export . --name=pkg --version=0.1')
        self.assertIn("pkg/0.1: Exported", client.out)
        client.run('export . --name=pkg --version=0.1')
        self.assertIn("pkg/0.1: Exported", client.out)


@pytest.mark.skipif(platform.system() != "Linux", reason="Needs case-sensitive filesystem")
def test_export_casing():
    # https://github.com/conan-io/conan/issues/8583
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            exports = "file1", "FILE1"
            exports_sources = "test", "TEST"
        """)
    client.save({"conanfile.py": conanfile,
                 "test": "some lowercase",
                 "TEST": "some UPPERCASE",
                 "file1": "file1 lowercase",
                 "FILE1": "file1 UPPERCASE"
                 })
    assert client.load("test") == "some lowercase"
    assert client.load("TEST") == "some UPPERCASE"
    assert client.load("file1") == "file1 lowercase"
    assert client.load("FILE1") == "file1 UPPERCASE"
    client.run("export . --name=pkg --version=0.1")
    layout = client.exported_layout()
    export_src_folder = layout.export_sources()
    assert load(os.path.join(export_src_folder, "test")) == "some lowercase"
    assert load(os.path.join(export_src_folder, "TEST")) == "some UPPERCASE"
    exports_folder = layout.export()
    assert load(os.path.join(exports_folder, "file1")) == "file1 lowercase"
    assert load(os.path.join(exports_folder, "FILE1")) == "file1 UPPERCASE"


def test_export_invalid_refs():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("export . --name=pkg% --version=0.1", assert_error=True)
    assert "ERROR: Invalid package name 'pkg%'" in c.out
    c.run("export . --name=pkg --version=0.1%", assert_error=True)
    assert "ERROR: Invalid package version '0.1%'" in c.out
    c.run("export . --name=pkg --version=0.1 --user=user%", assert_error=True)
    assert "ERROR: Invalid package user 'user%'" in c.out
    c.run("export . --name=pkg --version=0.1 --user=user --channel=channel%", assert_error=True)
    assert "ERROR: Invalid package channel 'channel%'" in c.out


def test_allow_temp_uppercase():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("export . --name=Pkg --version=0.1", assert_error=True)
    assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out
    c.save_home({"global.conf": "core:allow_uppercase_pkg_names=True"})
    c.run("export . --name=Pkg --version=0.1")
    assert "WARN: Package name 'Pkg/0.1' has uppercase, " \
           "and has been allowed by temporary config." in c.out


def test_warn_special_chars_refs():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("export . --name=pkg.name --version=0.1")
    assert "WARN: Name containing special chars is discouraged 'pkg.name'" in c.out
    c.run("export . --name=name --version=0.1 --user=user+some")
    assert "WARN: User containing special chars is discouraged 'user+some'" in c.out
    c.run("export . --name=pkg.name --version=0.1 --user=user --channel=channel+some")
    assert "WARN: Channel containing special chars is discouraged 'channel+some'" in c.out


def test_export_json():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile()})
    c.run("export . --name=foo --version=0.1 --format json")
    info = json.loads(c.stdout)
    assert info["reference"] == "foo/0.1#4d670581ccb765839f2239cc8dff8fbd"
    assert len(info) == 1  # Only "reference" key yet
