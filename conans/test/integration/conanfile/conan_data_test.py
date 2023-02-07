import os
import sys
import textwrap
import unittest

import pytest
import yaml
from bottle import static_file

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.test_files import tgz_with_contents
from conans.test.utils.tools import TestClient, StoppableThreadBottle
from conans.util.files import md5sum, sha1sum, sha256sum, load


class ConanDataTest(unittest.TestCase):

    def test_conan_exports_kept(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Lib(ConanFile):
                exports = "myfile.txt"
            """)
        conandata = textwrap.dedent("""
            foo:
              bar: "as"
            """)
        client.save({"conanfile.py": conanfile,
                     "myfile.txt": "bar",
                     "conandata.yml": conandata})
        ref = RecipeReference.loads("lib/0.1@user/testing")
        client.run(f"export . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
        export_folder = client.get_latest_ref_layout(ref).export()
        exported_data = os.path.join(export_folder, "conandata.yml")
        data = yaml.safe_load(load(exported_data))
        self.assertEqual(data, {"foo": {"bar": "as"}})
        self.assertTrue(os.path.exists(os.path.join(export_folder, "myfile.txt")))

    def test_conan_data_everywhere(self):
        client = TestClient()
        conanfile = """from conan import ConanFile

class Lib(ConanFile):

    def _assert_data(self):
        assert(self.conan_data["sources"]["all"]["url"] == "the url")
        assert(self.conan_data["sources"]["all"]["other"] == "field")
        self.output.info("My URL: {}".format(self.conan_data["sources"]["all"]["url"]))

    def configure(self):
        self._assert_data()

    def config_options(self):
        self._assert_data()

    def source(self):
        self._assert_data()

    def build(self):
        self._assert_data()

    def package(self):
        self._assert_data()

    def package_info(self):
        self._assert_data()
"""
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": """
sources:
  all:
    url: "the url"
    other: "field"
"""})
        ref = RecipeReference.loads("lib/0.1@user/testing")
        client.run(f"create . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
        self.assertIn("File 'conandata.yml' found. Exporting it...", client.out)
        self.assertIn("My URL:", client.out)
        export_folder = client.get_latest_ref_layout(ref).export()
        self.assertTrue(os.path.exists(os.path.join(export_folder, "conandata.yml")))

        # Transitive loaded?
        client.save({"conanfile.txt": "[requires]\n{}".format(ref)}, clean_first=True)
        client.run("install . ")
        self.assertIn("My URL:", client.out)
        client.run("install . --build='*'")
        self.assertIn("My URL:", client.out)

    @pytest.mark.slow
    @pytest.mark.local_bottle
    def test_conan_data_as_source_newtools(self):
        tgz_path = tgz_with_contents({"foo.txt": "foo"})
        if sys.version_info.major == 3 and sys.version_info.minor >= 9:
            # Python 3.9 changed the tar algorithm. Conan tgz will have different checksums
            # https://github.com/conan-io/conan/issues/8020
            md5_value = "f1d0dee6f0bf5b7747c013dd26183cdb"
            sha1_value = "d45ca9ad171ca9baa93f4da99904036aa71b0ddb"
            sha256_value = "b6880ef494974b8413a107429bde8d6b81a85c45a600040f5334a1d300c203b5"
        else:
            md5_value = "babc50837f9aaf46e134455966230e3e"
            sha1_value = "1e5b8ff7ae58b40d698fe3d4da6ad2a47ec6f4f3"
            sha256_value = "3ff04581cb0e2f9e976a9baad036f4ca9d884907c3d9382bb42a8616d3c20e42"
        self.assertEqual(md5_value, md5sum(tgz_path))
        self.assertEqual(sha1_value, sha1sum(tgz_path))
        self.assertEqual(sha256_value, sha256sum(tgz_path))

        # Instance stoppable thread server and add endpoints
        thread = StoppableThreadBottle()

        @thread.server.get("/myfile.tar.gz")
        def get_file():
            return static_file(os.path.basename(tgz_path), root=os.path.dirname(tgz_path),
                               mimetype="")

        thread.run_server()

        client = TestClient()
        conanfile = textwrap.dedent("""
                from conan import ConanFile
                from conan.tools.files import get

                class Lib(ConanFile):
                    def source(self):
                        data = self.conan_data["sources"]["all"]
                        get(self, **data)
                        self.output.info("OK!")
                """)
        conandata = textwrap.dedent("""
                sources:
                  all:
                    url: "http://localhost:{}/myfile.tar.gz"
                    md5: "{}"
                    sha1: "{}"
                    sha256: "{}"
                """)
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": conandata.format(thread.port, md5_value, sha1_value,
                                                       sha256_value)})
        ref = RecipeReference.loads("lib/0.1@user/testing")
        client.run(f"create . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}")
        self.assertIn("OK!", client.out)

        latest_rrev = client.cache.get_latest_recipe_reference(ref)
        ref_layout = client.cache.ref_layout(latest_rrev)
        source_folder = ref_layout.source()
        downloaded_file = os.path.join(source_folder, "foo.txt")
        self.assertEqual("foo", load(downloaded_file))

    def test_invalid_yml(self):
        client = TestClient()
        conanfile = """from conan import ConanFile

class Lib(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": ">>>> ::"})
        ref = RecipeReference.loads("lib/0.1@user/testing")
        client.run(f"create . --name={ref.name} --version={ref.version} --user={ref.user} --channel={ref.channel}", assert_error=True)
        self.assertIn("ERROR: Error loading conanfile at", client.out)
        self.assertIn(": Invalid yml format at conandata.yml: while scanning a block scalar",
                      client.out)

    def test_conan_data_development_flow(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                def layout(self):
                    self.folders.build = "tmp/build"

                def _assert_data(self):
                    assert(self.conan_data["sources"]["all"]["url"] == "this url")
                    assert(self.conan_data["sources"]["all"]["other"] == "field")
                    self.output.info("My URL: {}".format(self.conan_data["sources"]["all"]["url"]))

                def source(self):
                    self._assert_data()

                def build(self):
                    self._assert_data()

                def package(self):
                    self._assert_data()
            """)
        conandata = textwrap.dedent("""
            sources:
              all:
                url: "this url"
                other: "field"
        """)
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": conandata})
        client.run("source .")
        self.assertIn("My URL: this url", client.out)
        client.run("build . -of=tmp/build")
        self.assertIn("My URL: this url", client.out)
        client.run("export-pkg . --name=name --version=version")
        self.assertIn("My URL: this url", client.out)


class TestConanDataUpdate:
    """
    testing the update_conandata() method
    """
    def test_conandata_update(self):
        """ test the update_conandata() helper
        """
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import update_conandata
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def export(self):
                    update_conandata(self, {"sources": {"0.1": {"commit": 123, "type": "git"},
                                                        "0.2": {"url": "new"}
                                                       }
                                           })

                def source(self):
                    data = self.conan_data["sources"]
                    self.output.info("0.1-commit: {}!!".format(data["0.1"]["commit"]))
                    self.output.info("0.1-type: {}!!".format(data["0.1"]["type"]))
                    self.output.info("0.1-url: {}!!".format(data["0.1"]["url"]))
                    self.output.info("0.2-url: {}!!".format(data["0.2"]["url"]))
            """)
        conandata = textwrap.dedent("""\
            sources:
                "0.1":
                    url: myurl
                    commit: 234
            """)
        c.save({"conanfile.py": conanfile,
                "conandata.yml": conandata})
        c.run("create .")
        assert "pkg/0.1: 0.1-commit: 123!!" in c.out
        assert "pkg/0.1: 0.1-type: git!!" in c.out
        assert "pkg/0.1: 0.1-url: myurl!!" in c.out
        assert "pkg/0.1: 0.2-url: new!!" in c.out

    def test_conandata_update_error(self):
        """ test the update_conandata() helper fails if used outside export()
        """
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import update_conandata
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def source(self):
                    update_conandata(self, {})
            """)
        c.save({"conanfile.py": conanfile})
        c.run("create .", assert_error=True)
        assert "The 'update_conandata()' can only be used in the 'export()' method" in c.out

    def test_conandata_create_if_not_exist(self):
        """ test the update_conandata() creates the file if it doesn't exist
        """
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import update_conandata
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def export(self):
                    update_conandata(self, {"data": "value"})
            """)
        c.save({"conanfile.py": conanfile})
        c.run("export .")  # It doesn't fail
        assert "pkg/0.1: Calling export()" in c.out
