import os
import shutil
import sys
import textwrap
import unittest

import pytest
import yaml

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import tgz_with_contents
from conan.test.utils.tools import TestClient, GenConanfile
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

    def test_conan_data_as_source_newtools(self):
        client = TestClient()
        file_server = TestFileServer()
        client.servers["file_server"] = file_server

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

        shutil.copy2(tgz_path, file_server.store)

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
                    url: "{}/myfile.tar.gz"
                    md5: "{}"
                    sha1: "{}"
                    sha256: "{}"
                """)
        client.save({"conanfile.py": conanfile,
                     "conandata.yml": conandata.format(file_server.fake_url, md5_value, sha1_value,
                                                       sha256_value)})

        client.run(f"create . --name=pkg --version=0.1")
        self.assertIn("OK!", client.out)

        ref_layout = client.exported_layout()
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


def test_conandata_trim():
    """ test the explict trim_conandata() helper
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import trim_conandata

        class Pkg(ConanFile):
            name = "pkg"
            def export(self):
                trim_conandata(self)
        """)
    conandata_yml = textwrap.dedent("""\
        sources:
          "1.0":
            url: "url1"
            sha256: "sha1"
        patches:
          "1.0":
            - patch_file: "patches/some_patch"
              base_path: "source_subfolder"
        something: else
          """)
    c.save({"conanfile.py": conanfile,
            "conandata.yml": conandata_yml})
    c.run("export . --version=1.0")
    layout = c.exported_layout()
    data1 = load(os.path.join(layout.export(), "conandata.yml"))
    assert "pkg/1.0: Exported: pkg/1.0#70612e15e4fc9af1123fe11731ac214f" in c.out
    conandata_yml2 = textwrap.dedent("""\
        sources:
         "1.0":
           url: "url1"
           sha256: "sha1"
         "1.1":
           url: "url2"
           sha256: "sha2"
        patches:
         "1.1":
           - patch_file: "patches/some_patch2"
             base_path: "source_subfolder"
         "1.0":
           - patch_file: "patches/some_patch"
             base_path: "source_subfolder"
        something: else
        """)
    c.save({"conandata.yml": conandata_yml2})
    c.run("export . --version=1.0")
    layout = c.exported_layout()
    data2 = load(os.path.join(layout.export(), "conandata.yml"))
    assert "1.1" not in data2
    assert data1 == data2
    assert "pkg/1.0: Exported: pkg/1.0#70612e15e4fc9af1123fe11731ac214f" in c.out
    # If I now try to create version 1.2 which has no patches, and then change a patch
    # its revision should not change either
    conandata_yml3 = textwrap.dedent("""\
    sources:
      "1.0":
        url: "url1"
        sha256: "sha1"
      "1.1":
        url: "url2"
        sha256: "sha2"
      "1.3":
        url: "url3"
        sha256: "sha3"
    patches:
      "1.1":
        - patch_file: "patches/some_patch2"
          base_path: "source_subfolder"
      "1.0":
        - patch_file: "patches/some_patch"
          base_path: "source_subfolder"
    something: else""")
    c.save({"conandata.yml": conandata_yml3})
    c.run("export . --version=1.3")
    initial_v13_rev = c.exported_recipe_revision()
    conandata_yml4 = textwrap.dedent("""\
        sources:
          "1.0":
            url: "url1"
            sha256: "sha1"
          "1.1":
            url: "url2"
            sha256: "sha2"
          "1.3":
            url: "url3"
            sha256: "sha3"
        patches:
          "1.1":
            - patch_file: "patches/some_patch2-v2"
              base_path: "source_subfolder"
          "1.0":
            - patch_file: "patches/some_patch"
              base_path: "source_subfolder"
        something: else""")
    c.save({"conandata.yml": conandata_yml4})
    c.run("export . --version=1.3")
    second_v13_rev = c.exported_recipe_revision()
    assert initial_v13_rev == second_v13_rev


def test_trim_conandata_as_hook():
    c = TestClient()
    c.save_home({"extensions/hooks/hook_trim.py": textwrap.dedent("""
    from conan.tools.files import trim_conandata

    def post_export(conanfile):
        trim_conandata(conanfile)
    """)})

    conandata_yml = textwrap.dedent("""\
            sources:
              "1.0":
                url: "url1"
                sha256: "sha1"
            patches:
              "1.0":
                - patch_file: "patches/some_patch"
                  base_path: "source_subfolder"
            something: else
              """)
    c.save({"conanfile.py": GenConanfile("pkg"),
            "conandata.yml": conandata_yml})
    c.run("export . --version=1.0")
    layout = c.exported_layout()
    data1 = load(os.path.join(layout.export(), "conandata.yml"))
    assert "pkg/1.0: Exported: pkg/1.0#03af39add1c7c9d68dcdb10b6968a14d" in c.out
    conandata_yml2 = textwrap.dedent("""\
            sources:
             "1.0":
               url: "url1"
               sha256: "sha1"
             "1.1":
               url: "url2"
               sha256: "sha2"
            patches:
             "1.1":
               - patch_file: "patches/some_patch2"
                 base_path: "source_subfolder"
             "1.0":
               - patch_file: "patches/some_patch"
                 base_path: "source_subfolder"
            something: else
            """)
    c.save({"conandata.yml": conandata_yml2})
    c.run("export . --version=1.0")
    layout = c.exported_layout()
    data2 = load(os.path.join(layout.export(), "conandata.yml"))
    assert "1.1" not in data2
    assert data1 == data2
    assert "pkg/1.0: Exported: pkg/1.0#03af39add1c7c9d68dcdb10b6968a14d" in c.out


@pytest.mark.parametrize("raise_if_missing", [True, False])
def test_trim_conandata_as_hook_without_conandata(raise_if_missing):
    c = TestClient()
    c.save_home({"extensions/hooks/hook_trim.py": textwrap.dedent(f"""
    from conan.tools.files import trim_conandata

    def post_export(conanfile):
        trim_conandata(conanfile, raise_if_missing={raise_if_missing})
    """)})

    c.save({"conanfile.py": GenConanfile("pkg")})
    if raise_if_missing:
        with pytest.raises(Exception, match="conandata.yml file doesn't exist") as exception:
            c.run("export . --version=1.0")
    else:
        c.run("export . --version=1.0")
        assert c.exported_recipe_revision() == "a9ec2e5fbb166568d4670a9cd1ef4b26"


def test_trim_conandata_anchors():
    """Anchors load correctly, because trim_conandata loads the yaml instead of replacing in place"""
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent("""
     from conan import ConanFile
     from conan.tools.files import trim_conandata

     class Pkg(ConanFile):
        name = "pkg"
        def export(self):
            trim_conandata(self)

        def generate(self):
            self.output.info("x: {}".format(self.conan_data["mapping"][self.version]["x"]))
    """),
             "conandata.yml": textwrap.dedent("""
             mapping:
                "1.0": &anchor
                    "x": "foo"
                "2.0": *anchor
             """)})
    tc.run("create . --version=2.0")
    assert "x: foo" in tc.out
    pkg_layout = tc.exported_layout()
    conandata = tc.load(pkg_layout.conandata())
    assert conandata == textwrap.dedent("""\
        mapping:
          '2.0':
            x: foo
        """)
