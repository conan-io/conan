import os
import re
import textwrap
import unittest
from collections import OrderedDict

import pytest

from conan.internal.paths import CONANFILE
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer
from conans.util.files import save


class SourceTest(unittest.TestCase):

    def test_local_flow_patch(self):
        # https://github.com/conan-io/conan/issues/2327
        conanfile = """from conan import ConanFile
from conan.tools.files import save, load
import os
class TestexportConan(ConanFile):
    name = "test"
    version = "0.1"

    exports = "mypython.py"
    exports_sources = "patch.patch"

    def source(self):
        save(self, "hello/hello.h", "my hello header!")
        patch = os.path.join(self.source_folder, "patch.patch")
        self.output.info("PATCH: %s" % load(self, patch))
        header = os.path.join(self.source_folder, "hello/hello.h")
        self.output.info("HEADER: %s" % load(self, header))
        python = os.path.join(self.recipe_folder, "mypython.py")
        self.output.info("PYTHON: %s" % load(self, python))
"""
        client = TestClient(light=True)
        client.save({"conanfile.py": conanfile,
                     "patch.patch": "mypatch",
                     "mypython.py": "mypython"})
        client.run("source .")
        self.assertIn("conanfile.py (test/0.1): PATCH: mypatch", client.out)
        self.assertIn("conanfile.py (test/0.1): HEADER: my hello header!", client.out)
        self.assertIn("conanfile.py (test/0.1): PYTHON: mypython", client.out)

        client.run("create . ")
        self.assertIn("test/0.1: PATCH: mypatch", client.out)
        self.assertIn("test/0.1: HEADER: my hello header!", client.out)
        self.assertIn("test/0.1: PYTHON: mypython", client.out)

    def test_apply_patch(self):
        # https://github.com/conan-io/conan/issues/2327
        # Test if a patch can be applied in source() both in create
        # and local flow
        client = TestClient(light=True)
        conanfile = """from conan import ConanFile
from conan.tools.files import load
import os
class Pkg(ConanFile):
    exports_sources = "*"
    def source(self):
        patch = os.path.join(self.source_folder, "mypatch")
        self.output.info("PATCH: %s" % load(self, patch))
"""
        client.save({"conanfile.py": conanfile,
                     "mypatch": "this is my patch"})
        client.run("source .")
        self.assertIn("PATCH: this is my patch", client.out)
        client.run("source .")
        self.assertIn("PATCH: this is my patch", client.out)
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("PATCH: this is my patch", client.out)

    def test_source_warning_os_build(self):
        # https://github.com/conan-io/conan/issues/2368
        conanfile = '''from conan import ConanFile
class ConanLib(ConanFile):
    pass
'''
        client = TestClient(light=True)
        client.save({CONANFILE: conanfile})
        client.run("source .")
        self.assertNotIn("This package defines both 'os' and 'os_build'", client.out)

    def test_source_with_path_errors(self):
        client = TestClient(light=True)
        client.save({"conanfile.txt": "contents"}, clean_first=True)

        # Path with conanfile.txt
        client.run("source conanfile.txt", assert_error=True)
        self.assertIn(
            "A conanfile.py is needed, %s is not acceptable"
            % os.path.join(client.current_folder, "conanfile.txt"),
            client.out)

    def test_source_local_cwd(self):
        conanfile = '''
import os
from conan import ConanFile

class ConanLib(ConanFile):
    name = "hello"
    version = "0.1"

    def source(self):
        self.output.info("Running source!")
        self.output.info("cwd=>%s" % os.getcwd())
'''
        client = TestClient(light=True)
        client.save({CONANFILE: conanfile})

        client.run("install .")
        client.run("source .")
        self.assertIn("conanfile.py (hello/0.1): Calling source()", client.out)
        self.assertIn("conanfile.py (hello/0.1): cwd=>%s" % client.current_folder, client.out)

    def test_local_source(self):
        conanfile = '''
from conan import ConanFile
from conans.util.files import save

class ConanLib(ConanFile):

    def source(self):
        self.output.info("Running source!")
        err
        save("file1.txt", "Hello World")
'''
        # First, failing source()
        client = TestClient(light=True)
        client.save({CONANFILE: conanfile})

        client.run("source .", assert_error=True)
        self.assertIn("conanfile.py: Running source!", client.out)
        self.assertIn("ERROR: conanfile.py: Error in source() method, line 9", client.out)

        # Fix the error and repeat
        client.save({CONANFILE: conanfile.replace("err", "")})
        client.run("source .")
        self.assertIn("conanfile.py: Calling source() in", client.out)
        self.assertIn("conanfile.py: Running source!", client.out)
        self.assertEqual("Hello World", client.load("file1.txt"))

    def test_retrieve_exports_sources(self):
        # For Conan 2.0 if we install a package from a remote and we want to upload to other
        # remote we need to download the sources, as we consider revisions immutable, let's
        # iterate through the remotes to get the sources from the first match
        servers = OrderedDict()
        for index in range(2):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})

        client = TestClient(servers=servers, inputs=3*["user", "password"])
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "sources.cpp": "sources"})
        client.run("create . --name=hello --version=0.1")
        rrev = client.exported_recipe_revision()
        client.run("upload hello/0.1 -r server0")
        # Ensure we uploaded it
        assert re.search(r"Uploading recipe 'hello/0.1#.*' \(.*\)", client.out)
        assert re.search(r"Uploading package 'hello/0.1#.*' \(.*\)", client.out)
        client.run("remove * -c")

        # install from server0 that has the sources, upload to server1 (does not have the package)
        # download the sources from server0
        client.run("install --requires=hello/0.1@ -r server0")
        client.run("upload hello/0.1 -r server1")
        self.assertIn("Sources downloaded from 'server0'", client.out)

        # install from server1 that has the sources, upload to server1
        # Will not download sources, revision already in server
        client.run("remove * -c")
        client.run("install --requires=hello/0.1@ -r server1")
        client.run("upload hello/0.1 -r server1")
        assert f"'hello/0.1#{rrev}' already in server, skipping upload" in client.out
        self.assertNotIn("Sources downloaded from 'server0'", client.out)

        # install from server0 and build
        # download sources from server0
        client.run("remove * -c")
        client.run("install --requires=hello/0.1@ -r server0 --build='*'")
        self.assertIn("Sources downloaded from 'server0'", client.out)

    def test_source_method_called_once(self):
        """
        Test that the source() method will be executed just once, and the source code will
        be shared for all the package builds.
        """

        conanfile = textwrap.dedent('''
            import os
            from conan import ConanFile
            from conans.util.files import save

            class ConanLib(ConanFile):

                def source(self):
                    save(os.path.join(self.source_folder, "main.cpp"), "void main() {}")
                    self.output.info("Running source!")
            ''')

        client = TestClient()
        client.save({CONANFILE: conanfile})

        client.run("create . --name=lib --version=1.0")
        assert "Running source!" in client.out

        client.run("create . --name=lib --version=1.0")
        assert "Running source!" not in client.out

        client.run("create . --name=lib --version=1.0 -s build_type=Debug")
        assert "Running source!" not in client.out

    def test_source_method_called_again_if_left_dirty(self):
        """
        If we fail in retreiving sources make sure the source() method will be called
        next time we create
        """

        conanfile = textwrap.dedent('''
            import os
            from conan import ConanFile

            class ConanLib(ConanFile):

                def source(self):
                    self.output.info("Running source!")
                    assert False
            ''')

        client = TestClient(light=True)
        client.save({CONANFILE: conanfile})

        client.run("create . --name=lib --version=1.0", assert_error=True)
        assert "Running source!" in client.out

        client.run("create . --name=lib --version=1.0", assert_error=True)
        assert "Running source!" in client.out
        assert "Source folder is corrupted, forcing removal" in client.out


class TestSourceWithoutDefaultProfile:
    # https://github.com/conan-io/conan/issues/12371
    @pytest.fixture()
    def client(self):
        c = TestClient()
        # The ``source()`` should still receive necessary configuration
        save(c.cache.new_config_path, "tools.files.download:retry=MYCACHE")
        # Make sure we don't have default profile
        os.remove(c.cache.default_profile_path)
        return c

    def test_source_without_default_profile(self, client):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                def source(self):
                    c = self.conf.get("tools.files.download:retry")
                    self.output.info("CACHE:{}!!".format(c))
                """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        assert "conanfile.py: Calling source()" in client.out
        assert "CACHE:MYCACHE!!" in client.out

    def test_source_with_layout(self, client):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def layout(self):
                    cmake_layout(self)
                def source(self):
                    c = self.conf.get("tools.files.download:retry")
                    self.output.info("CACHE:{}!!".format(c))
                """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        assert "conanfile.py: Calling source()" in client.out
        assert "CACHE:MYCACHE!!" in client.out


def test_source_python_requires():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("pytool", "0.1")})
    c.run("export . ")
    c.run("upload * -r=default -c")
    c.run("remove * -c")

    c.save({"conanfile.py": GenConanfile().with_python_requires("pytool/0.1")}, clean_first=True)
    c.run("source . ")
    assert "pytool/0.1: Not found in local cache, looking in remotes" in c.out
    assert "pytool/0.1: Downloaded recipe" in c.out


@pytest.mark.parametrize("attribute", ["info", "settings", "options"])
def test_source_method_forbidden_attributes(attribute):
    conanfile = textwrap.dedent(f"""
    from conan import ConanFile
    class Package(ConanFile):
        def source(self):
            self.output.info(self.{attribute})
    """)
    client = TestClient(light=True)
    client.save({"conanfile.py": conanfile})

    client.run("source .", assert_error=True)
    assert f"'self.{attribute}' access in 'source()' method is forbidden" in client.out
