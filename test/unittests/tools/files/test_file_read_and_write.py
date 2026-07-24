# -*- coding: utf-8 -*-


import os

import pytest

from conan.errors import ConanException
from conan.tools.files import replace_in_file, save, load
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder


def test_save_and_load_encoding():
    conanfile = ConanFileMock({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")

    # By default utf-8 is used
    save(conanfile, file_path, "你很重，伙計")
    contents = load(conanfile, file_path)
    assert isinstance(contents, str)
    assert contents == "你很重，伙計"

    # And you can specify different encoding
    save(conanfile, file_path, "你很重，伙計", encoding="utf-16")
    contents = load(conanfile, file_path, encoding="utf-16")
    assert contents == "你很重，伙計"

    save(conanfile, file_path, "regular contents")
    contents = load(conanfile, file_path)
    assert contents == "regular contents"


def test_replace_in_file():
    conanfile = ConanFileMock({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")

    # By default utf-8 is used
    save(conanfile, file_path, "你很重，伙計")
    assert replace_in_file(conanfile, file_path, "重", "0")
    contents = load(conanfile, file_path)
    assert contents == "你很0，伙計"

    # Replacing with other encodings is also possible
    save(conanfile, file_path, "Ö¼", encoding="cp1252")
    assert replace_in_file(conanfile, file_path, "¼", "0", encoding="cp1252")
    contents = load(conanfile, file_path, encoding="cp1252")
    assert contents == "Ö0"

    save(conanfile, file_path, "Ö¼", encoding="ISO-8859-1")
    assert replace_in_file(conanfile, file_path, "¼", "0", encoding="ISO-8859-1")
    contents = load(conanfile, file_path, encoding="ISO-8859-1")
    assert contents == "Ö0"

    # Replacing utf-16 is also possible but using "utf-16LE" (without BOM) to search and replace
    # otherwise the "search" string is not found because it contains also a BOM (header)
    save(conanfile, file_path, "你很重，伙計", encoding="utf-16")
    replace_in_file(conanfile, file_path, "重", "0", encoding="utf-16")
    contents = load(conanfile, file_path, encoding="utf-16")
    assert contents == "你很0，伙計"

    with pytest.raises(ConanException, match="didn't find pattern"):
        replace_in_file(conanfile, file_path, "not existing", "0", encoding="utf-16")

    assert not replace_in_file(conanfile, file_path, "not existing", "0",
                               encoding="utf-16", strict=False)


def test_replace_in_file_regex():
    conanfile = ConanFileMock({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")
    save(conanfile, file_path, "foo\nbar=123\nbaz\n")

    # Search with regex
    assert replace_in_file(conanfile, file_path, r"^bar=.*", "bar=", regex=True)
    assert load(conanfile, file_path) == "foo\nbar=\nbaz\n"

    # Search and replace with regex
    save(conanfile, file_path, "foo=hello\nbar\n")
    assert replace_in_file(conanfile, file_path, r"^foo=(.*)", r"foo=pre_\1", regex=True)
    assert load(conanfile, file_path) == "foo=pre_hello\nbar\n"

    # Not found replace with strict=False
    assert not replace_in_file(conanfile, file_path, r"^missing=.*", "x",
                               regex=True, strict=False)

    # Not found with strict=True
    with pytest.raises(ConanException, match="didn't find pattern"):
        replace_in_file(conanfile, file_path, r"^missing=.*", "x", regex=True)

    # Not valid regex
    with pytest.raises(ConanException, match="invalid regex"):
        replace_in_file(conanfile, file_path, r"[unclosed", "x", regex=True)

    # regex=False keeps literal match even if search looks like a regex
    save(conanfile, file_path, "foo.*bar")
    assert replace_in_file(conanfile, file_path, "foo.*", "baz", regex=False)
    assert load(conanfile, file_path) == "bazbar"


def test_replace_in_file_noop_replace():
    """ Regression test for a replace that matches but produces identical content, e.g.
    replace_in_file(conanfile, path, search, replace) when search == replace, or when replace
    reconstructs the exact same text. This must not be reported as "pattern not found"
    (https://github.com/conan-io/conan/pull/20194 regression).
    """
    conanfile = ConanFileMock({})
    tmp = temp_folder()
    file_path = os.path.join(tmp, "file.txt")
    save(conanfile, file_path, "foo bar baz\n")

    # search is present, but replace happens to produce the same text back
    assert replace_in_file(conanfile, file_path, "bar", "bar")
    assert load(conanfile, file_path) == "foo bar baz\n"

    # same, but for regex mode
    save(conanfile, file_path, "foo bar baz\n")
    assert replace_in_file(conanfile, file_path, r"ba(r)", r"ba\1", regex=True)
    assert load(conanfile, file_path) == "foo bar baz\n"
