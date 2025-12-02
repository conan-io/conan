import json
import os
import sys
import textwrap

import pytest

from conan.api.model import RecipeReference, PkgReference
from conan.internal.util import load
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("compress", ["gz", "xz", "zst"])
def test_xz(compress):
    if compress == "zst" and sys.version_info.minor < 14:
        pytest.skip("Skipping zst compression tests")

    c = TestClient(default_server_user=True)
    c.save_home({"global.conf": f"core.upload:compression_format={compress}"})
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            exports_sources = "*.h"
            exports = "*.yml"
            def package(self):
                copy(self, "*.h", self.source_folder, self.package_folder)
        """)

    c.save({"conanfile.py": conanfile,
            "header.h": "myheader",
            "myfile.yml": "myyml"})
    c.run("create -tf=")
    c.run("upload * -r=default -c --format=json")

    # Verify the uploaded files are all txz
    upload_json = json.loads(c.stdout)
    rrev = upload_json["default"]["pkg/0.1"]["revisions"]["4e81a0b14da7ae918cf3dba3a07578d6"]
    rfiles = rrev["files"]
    assert f"conan_export.t{compress}" in rfiles
    assert f"conan_sources.t{compress}" in rfiles
    prevs = rrev["packages"]["da39a3ee5e6b4b0d3255bfef95601890afd80709"]["revisions"]
    prev = prevs["13eb72928af98144fa7bf104b69663bc"]
    pfiles = prev["files"]
    assert f"conan_package.t{compress}" in pfiles

    # decompress should work anyway
    c.save_home({"global.conf": ""})
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")

    # checking the recipe
    ref = RecipeReference.loads("pkg/0.1")
    rlayout = c.get_latest_ref_layout(ref)
    downloaded_files = os.listdir(rlayout.download_export())
    assert f"conan_export.t{compress}" in downloaded_files
    assert f"conan_sources.t{compress}" not in downloaded_files
    assert "myyml" == load(os.path.join(rlayout.export(), "myfile.yml"))

    # checking the package
    pref = PkgReference(rlayout.reference, "da39a3ee5e6b4b0d3255bfef95601890afd80709")
    playout = c.get_latest_pkg_layout(pref)
    downloaded_files = os.listdir(playout.download_package())
    assert f"conan_package.t{compress}" in downloaded_files
    assert "myheader" == load(os.path.join(playout.package(), "header.h"))

    # Force the build from source
    c.run("install --requires=pkg/0.1 --build=*")
    downloaded_files = os.listdir(rlayout.download_export())
    assert f"conan_export.t{compress}" in downloaded_files
    assert f"conan_sources.t{compress}" in downloaded_files
