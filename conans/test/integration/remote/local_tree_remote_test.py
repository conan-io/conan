import json
import os
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir, save, save_files


@pytest.fixture(scope="module")
def c3i_folder():
    folder = temp_folder()
    recipes_folder = os.path.join(folder, "recipes")
    zlib_config = textwrap.dedent("""
        versions:
          "1.2.8":
            folder: all
          "1.2.11":
            folder: all
        """)
    zlib = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import load
        class Zlib(ConanFile):
            name = "zlib"
            exports_sources = "*"
            def build(self):
                self.output.info(f"CONANDATA: {self.conan_data}")
                self.output.info(f"BUILDING: {load(self, 'file.h')}")
            """)
    save_files(recipes_folder,
               {"zlib/config.yml": zlib_config,
                "zlib/all/conanfile.py": zlib,
                "zlib/all/conandata.yml": "",
                "zlib/all/file.h": "//myheader"})
    mkdir(os.path.join(recipes_folder, "openssl", "1.X"))
    mkdir(os.path.join(recipes_folder, "openssl", "2.X"))
    save(os.path.join(recipes_folder, "openssl", "config.yml"), textwrap.dedent("""
        versions:
          "1.0":
            folder: "1.X"
          "1.1":
            folder: "1.X"
          "2.0":
            folder: "2.X"
        """))
    save(os.path.join(recipes_folder, "openssl", "1.X", "conanfile.py"),
         str(GenConanfile().with_require("zlib/1.2.8")))
    save(os.path.join(recipes_folder, "openssl", "2.X", "conanfile.py"),
         str(GenConanfile().with_require("zlib/1.2.11")))
    mkdir(os.path.join(recipes_folder, "libcurl", "all"))
    save(os.path.join(recipes_folder, "libcurl", "config.yml"), textwrap.dedent("""
            versions:
              "1.0":
                folder: "all"
            """))
    save(os.path.join(recipes_folder, "libcurl", "all", "conanfile.py"),
         str(GenConanfile().with_require("openssl/2.0")))
    return folder


class TestSearchList:
    def test_basic_search(self, c3i_folder):
        client = TestClient()
        client.run(f"remote add ccifork '{c3i_folder}' --type=local")
        client.run("search *")
        assert textwrap.dedent("""\
            ccifork
              libcurl
                libcurl/1.0
              openssl
                openssl/1.0
                openssl/1.1
                openssl/2.0
              zlib
                zlib/1.2.8
                zlib/1.2.11
            """) in client.out

    def test_list_refs(self, c3i_folder):
        client = TestClient()
        client.run(f"remote add ccifork '{c3i_folder}' --type=local")
        client.run("list *#* -r=ccifork --format=json")
        listjson = json.loads(client.stdout)
        revs = listjson["ccifork"]["libcurl/1.0"]["revisions"]
        assert len(revs) == 1 and "e468388f0e4e098d5b62ad68979aebd5" in revs
        revs = listjson["ccifork"]["openssl/1.0"]["revisions"]
        assert len(revs) == 1 and "b35ffb31b6d5a9d8af39f5de3cf4fd63" in revs
        revs = listjson["ccifork"]["openssl/1.1"]["revisions"]
        assert len(revs) == 1 and "b35ffb31b6d5a9d8af39f5de3cf4fd63" in revs
        revs = listjson["ccifork"]["openssl/2.0"]["revisions"]
        assert len(revs) == 1 and "e50e871efca149f160fa6354c8534449" in revs
        revs = listjson["ccifork"]["zlib/1.2.8"]["revisions"]
        assert len(revs) == 1 and "6f5c31bb1219e9393743d1fbf2ee1b52" in revs
        revs = listjson["ccifork"]["zlib/1.2.11"]["revisions"]
        assert len(revs) == 1 and "6f5c31bb1219e9393743d1fbf2ee1b52" in revs

    def test_list_rrevs(self, c3i_folder):
        client = TestClient()
        client.run(f"remote add ccifork '{c3i_folder}' --type=local")
        client.run("list libcurl/1.0#* -r=ccifork --format=json")
        listjson = json.loads(client.stdout)
        revs = listjson["ccifork"]["libcurl/1.0"]["revisions"]
        assert len(revs) == 1 and "e468388f0e4e098d5b62ad68979aebd5" in revs

    def test_list_binaries(self, c3i_folder):
        client = TestClient()
        client.run(f"remote add ccifork '{c3i_folder}' --type=local")
        client.run("list libcurl/1.0:* -r=ccifork --format=json")
        listjson = json.loads(client.stdout)
        rev = listjson["ccifork"]["libcurl/1.0"]["revisions"]["e468388f0e4e098d5b62ad68979aebd5"]
        assert rev["packages"] == {}


class TestInstall:
    def test_install(self, c3i_folder):
        c = TestClient()
        c.run(f"remote add ccifork '{c3i_folder}' --type=local")
        c.run("install --requires=libcurl/1.0 --build missing")
        assert "zlib/1.2.11: CONANDATA: {}" in c.out
        assert "zlib/1.2.11: BUILDING: //myheader" in c.out
        bins = {"libcurl/1.0": ("aa69c1e1e39a18fe70001688213dbb7ada95f890", "Build"),
                "openssl/2.0": ("594ed0eb2e9dfcc60607438924c35871514e6c2a", "Build"),
                "zlib/1.2.11": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Build")}
        c.assert_listed_binary(bins)

        # Already installed in the cache
        c.run("install --requires=libcurl/1.0")
        assert "zlib/1.2.11: Already installed!" in c.out
        assert "openssl/2.0: Already installed!" in c.out
        assert "libcurl/1.0: Already installed!" in c.out

        # Update doesn't fail, but doesn't update revision time
        c.run("install --requires libcurl/1.0 --update")
        bins = {"libcurl/1.0": "Cache (Updated date) (ccifork)",
                "openssl/2.0": "Cache (Updated date) (ccifork)",
                "zlib/1.2.11": "Cache (Updated date) (ccifork)"}

        c.assert_listed_require(bins)
        assert "zlib/1.2.11: Already installed!" in c.out
        assert "openssl/2.0: Already installed!" in c.out
        assert "libcurl/1.0: Already installed!" in c.out

        # Doing local changes creates a new revision
        # New recipe revision for the zlib library
        save(os.path.join(c3i_folder, "recipes", "zlib", "all", "conanfile.py"),
             str(GenConanfile()) + "\n")
        c.run("install --requires=libcurl/1.0 --build missing --update")
        # it is updated
        assert "zlib/1.2.11#dd82451a95902c89bb66a2b980c72de5 - Updated (ccifork)" in c.out


class TestRestrictedOperations:
    def test_upload(self):
        folder = temp_folder()
        c3i_folder = os.path.join(folder, "recipes")
        c = TestClient()
        c.run(f"remote add ccifork '{c3i_folder}' --type=local")
        c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        c.run("create .")
        c.run("upload pkg/0.1 -r=ccifork", assert_error=True)
        assert "ERROR: Git remote 'ccifork' doesn't support upload" in c.out


class TestErrorsUx:
    def test_errors(self):
        folder = temp_folder()
        recipes_folder = os.path.join(folder, "recipes")
        zlib_config = textwrap.dedent("""
            versions:
              "1.2.11":
                folder: all
            """)
        zlib = textwrap.dedent("""
            class Zlib(ConanFile):
                name = "zlib"
                """)
        save_files(recipes_folder,
                   {"zlib/config.yml": zlib_config,
                    "zlib/all/conanfile.py": zlib})
        c = TestClient()
        c.run(f"remote add ccifork '{folder}' --type=local")
        c.run("install --requires=zlib/[*] --build missing", assert_error=True)
        assert "NameError: name 'ConanFile' is not defined" in c.out
