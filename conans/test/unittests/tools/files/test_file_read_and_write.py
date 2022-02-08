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
    assert isinstance(contents, str)
    assert contents == "你很重，伙計"

    # But you can save bytes directly with an encoding
    save(conanfile, file_path, bytes("你很重，伙計", "utf-16"))
    contents = load(conanfile, file_path, encoding="utf-16")
    assert contents == "你很重，伙計"

    # And you can specify different encoding
    save(conanfile, file_path, "你很重，伙計", encoding="utf-16")
    contents = load(conanfile, file_path, encoding="utf-16")
    assert contents == "你很重，伙計"

    save(conanfile, file_path, "regular contents")
    contents = load(conanfile, file_path)
    assert contents == "regular contents"


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_replace_in_file():
    conanfile = MockConanfile({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")

    # By default utf-8 is used
    save(conanfile, file_path, "你很重，伙計")
    replace_in_file(conanfile, file_path, "重", "0")
    contents = load(conanfile, file_path)
    assert contents == "你很0，伙計"

    # Replacing with other encodings is also possible
    save(conanfile, file_path, "Ö¼", encoding="cp1252")
    replace_in_file(conanfile, file_path, "¼", "0", encoding="cp1252")
    contents = load(conanfile, file_path, encoding="cp1252")
    assert contents == "Ö0"

    save(conanfile, file_path, bytes("Ö¼", "ISO-8859-1"))
    replace_in_file(conanfile, file_path, "¼", "0", encoding="ISO-8859-1")
    contents = load(conanfile, file_path, encoding="ISO-8859-1")
    assert contents == "Ö0"

    # Replacing utf-16 is also possible but using "utf-16LE" (without BOM) to search and replace
    # otherwise the "search" string is not found because it contains also a BOM (header)
    save(conanfile, file_path, bytes("你很重，伙計", "utf-16"))
    replace_in_file(conanfile, file_path, "重", "0", encoding="utf-16")
    contents = load(conanfile, file_path, encoding="utf-16")
    assert contents == "你很0，伙計"
