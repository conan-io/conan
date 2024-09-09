import os
import textwrap
from collections import OrderedDict
from unittest import mock

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID, GenConanfile
from conans.util.files import load


def test_download_with_sources():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports_sources("*"),
                 "file.h": "myfile.h",
                 "otherfile.cpp": "C++code"})
    client.run("export . --user=lasote --channel=stable")

    ref = RecipeReference.loads("pkg/0.1@lasote/stable")
    client.run("upload pkg/0.1@lasote/stable -r default")
    client.run("remove pkg/0.1@lasote/stable -c")

    client.run("download pkg/0.1@lasote/stable -r default")
    assert "Downloading 'pkg/0.1@lasote/stable' sources" in client.out
    source = client.get_latest_ref_layout(ref).export_sources()
    assert "myfile.h" == load(os.path.join(source, "file.h"))
    assert "C++code" == load(os.path.join(source, "otherfile.cpp"))


def test_no_user_channel():
    # https://github.com/conan-io/conan/issues/6009
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=pkg --version=1.0")
    client.run("upload * --confirm -r default")
    client.run("remove * -c")

    client.run("download pkg/1.0:{} -r default".format(NO_SETTINGS_PACKAGE_ID))
    assert f"Downloading package 'pkg/1.0#4d670581ccb765839f2239cc8dff8fbd:{NO_SETTINGS_PACKAGE_ID}" in client.out

    # All
    client.run("remove * -c")
    client.run("download pkg/1.0#*:* -r default")
    assert f"Downloading package 'pkg/1.0#4d670581ccb765839f2239cc8dff8fbd:{NO_SETTINGS_PACKAGE_ID}" in client.out


def test_download_with_python_requires():
    """ In the past,
    when having a python_require in a different repo, it cannot be ``conan download``
    as the download runs from a single repo.

    Now, from https://github.com/conan-io/conan/issues/14260, "conan download" doesn't
    really need to load conanfile, so it doesn't fail because of this.
    """
    # https://github.com/conan-io/conan/issues/9548
    servers = OrderedDict([("tools", TestServer()),
                           ("pkgs", TestServer())])
    c = TestClient(servers=servers, inputs=["admin", "password", "admin", "password"])

    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("tool/0.1")})
    c.run("export tool")
    c.run("create pkg")
    c.run("upload tool* -r tools -c")
    c.run("upload pkg* -r pkgs -c")
    c.run("remove * -c")

    c.run("install --requires=pkg/0.1 -r pkgs -r tools")
    assert "Downloading" in c.out
    c.run("remove * -c")

    c.run("download pkg/0.1 -r pkgs")
    assert "pkg/0.1: Downloaded package revision" in c.out


def test_download_verify_ssl_conf():
    client = TestClient()

    client.save({"conanfile.py": textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import download

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"

            def source(self):
                download(self, "http://verify.true", "", verify=True)
                download(self, "http://verify.false", "", verify=False)
        """)})

    did_verify = {}

    def custom_download(this, url, filepath, *args, **kwargs):
        did_verify[url] = args[2]

    with mock.patch("conans.client.downloaders.file_downloader.FileDownloader.download",
                    custom_download):
        client.run("create . -c tools.files.download:verify=True")
        assert did_verify["http://verify.true"]
        assert did_verify["http://verify.false"]

        did_verify.clear()
        client.run("remove pkg/1.0 -c")

        client.run("create . -c tools.files.download:verify=False")
        assert not did_verify["http://verify.true"]
        assert not did_verify["http://verify.false"]

        did_verify.clear()
        client.run("remove pkg/1.0 -c")

        client.run("create .")
        assert did_verify["http://verify.true"]
        assert not did_verify["http://verify.false"]


def test_download_list_only_recipe():
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("liba", "0.1")})
    c.run("create .")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("list *:* -r=default --format=json", redirect_stdout="pkgs.json")
    c.run("download --list=pkgs.json --only-recipe -r=default")
    assert "packages" not in c.out
