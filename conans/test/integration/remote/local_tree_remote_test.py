import os
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir, save


@pytest.fixture()
def c3i_folder():
    folder = temp_folder()
    recipes_folder = os.path.join(folder, "recipes")
    mkdir(os.path.join(recipes_folder, "zlib", "all"))
    save(os.path.join(recipes_folder, "zlib", "config.yml"), textwrap.dedent("""
        versions:
          "1.2.8":
            folder: all
          "1.2.11":
            folder: all
        """))
    save(os.path.join(recipes_folder, "zlib", "all", "conanfile.py"), str(GenConanfile()))
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


def test_basic(c3i_folder):
    client = TestClient()
    client.run("remote add repo-sources 'file://{}'".format(c3i_folder))

    client.run("search '*'")
    assert 'repo-sources:\n  ' \
           'libcurl\n    libcurl/1.0\n  ' \
           'zlib\n    zlib/1.2.8\n    zlib/1.2.11\n  ' \
           'openssl\n    openssl/1.0\n    openssl/1.1\n    ' \
           'openssl/2.0\n' in client.out

    client.run("install --reference libcurl/1.0 --build missing")
    client.run("list recipes '*'")
    assert 'Local Cache:\n  zlib\n    zlib/1.2.11\n  openssl\n    ' \
           'openssl/2.0\n  libcurl\n    libcurl/1.0\n' in client.out

    client.run("install --reference libcurl/1.0")
    assert "zlib/1.2.11: Already installed!\n" \
           "openssl/2.0: Already installed!\n" \
           "libcurl/1.0: Already installed!" in client.out

    client.run("install --reference libcurl/1.0 --update")
    assert "libcurl/1.0#eafe68ecc8462f6d6ff3642f01509a4a - Cache (Updated date)" in client.out
    assert "zlib/1.2.11#f3367e0e7d170aa12abccb175fee5f97 - Cache (Updated date)" in client.out
    assert "zlib/1.2.11: Already installed!\n" \
           "openssl/2.0: Already installed!\n" \
           "libcurl/1.0: Already installed!" in client.out

    # New recipe revision for the zlib library
    save(os.path.join(c3i_folder, "recipes", "zlib", "all", "conanfile.py"),
         str(GenConanfile()) + "\n")
    client.run("install --reference libcurl/1.0 --build missing --update")
    assert "zlib/1.2.11#9bdcc7e7b70bf5b92dd8a947cefb878a - Updated (repo-sources)" in client.out
