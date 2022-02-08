# -*- coding: utf-8 -*-


import os

import pytest
import six

from conan.tools.files import replace_in_file, save, load
from conans.test.utils.mocks import MockConanfile
from conans.test.utils.test_files import temp_folder


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_save_and_load_encoding():
    conanfile = MockConanfile({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")

    # By default utf-8 is used
    save(conanfile, file_path, "你很重，伙計")
    contents = load(conanfile, file_path)
    assert isinstance(contents, bytes)
    assert contents == bytes("你很重，伙計", "utf-8")

    # But you can specify a different encoding providing the bytes
    save(conanfile, file_path, bytes("你很重，伙計", "utf-16"))
    contents = load(conanfile, file_path)
    assert isinstance(contents, bytes)
    assert contents == bytes("你很重，伙計", "utf-16")
    assert contents != bytes("你很重，伙計", "utf-8")

    save(conanfile, file_path, "regular contents")
    contents = load(conanfile, file_path)
    assert isinstance(contents, bytes)
    assert contents == b"regular contents"


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_replace_in_file():
    conanfile = MockConanfile({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")

    # By default utf-8 is used
    save(conanfile, file_path, "你很重，伙計")
    replace_in_file(conanfile, file_path, "重", "0")
    contents = load(conanfile, file_path)
    assert contents == bytes("你很0，伙計", "utf-8")

    # Replacing with other encodings is also possible
    save(conanfile, file_path, bytes("Ö¼", "cp1252"))
    replace_in_file(conanfile, file_path, bytes("¼", "cp1252"), "0")
    contents = load(conanfile, file_path)
    assert contents == bytes("Ö0", "cp1252")

    save(conanfile, file_path, bytes("Ö¼", "ISO-8859-1"))
    replace_in_file(conanfile, file_path, bytes("¼", "ISO-8859-1"), "0")
    contents = load(conanfile, file_path)
    assert contents == bytes("Ö0", "ISO-8859-1")

    # Replacing utf-16 is also possible but using "utf-16LE" (without BOM) to search and replace
    # otherwise the "search" string is not found because it contains also a BOM (header)
    save(conanfile, file_path, bytes("你很重，伙計", "utf-16"))
    replace_in_file(conanfile, file_path, bytes("重", "utf-16LE"), bytes("0", "utf-16LE"))
    contents = load(conanfile, file_path)
    assert contents.decode("utf-16") == "你很0，伙計"
