""" Conan parses settings.yml and conandata.yml with the libyaml loader when it is available, it
must load exactly the same data as the pure-Python yaml.safe_load() used before, with the same types
and order: settings.yml defines the settings and their values in the package_ids, and conandata.yml
is written again in the exported files by trim_conandata() and export_conandata_patches(), a
difference would change the package_ids or the recipe revisions
"""
import os
import textwrap
from unittest import mock

import pytest
import yaml

from conan.errors import ConanException
from conan.internal.default_settings import default_settings_yml
from conan.internal.loader import ConanFileLoader
from conan.internal.model.settings import Settings
from conan.internal.util.files import YamlSafeLoader, load, save
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.tools.files import trim_conandata

pytestmark = pytest.mark.skipif(YamlSafeLoader is yaml.SafeLoader,
                                reason="PyYAML without libyaml, Conan uses the pure-Python loader")


def _typed(data):
    """ The data with the type of every value, in order: 1 == 1.0 == True, and "1.10" is not 1.1 """
    if isinstance(data, dict):
        return "dict", [(_typed(k), _typed(v)) for k, v in data.items()]
    if isinstance(data, list):
        return "list", [_typed(v) for v in data]
    return type(data).__name__, repr(data)


_SETTINGS_USER_YML = textwrap.dedent("""\
    os:
      MyOS:
        version: [1.10, "1.10", 2, 0755, 2023-01-01, yes, "yes", null, ~]
    compiler:
      gcc:
        version: [15.1, "15.2", 16]
        libcxx: &libcxx [libstdc++, "libstdc++11"]
      mycompiler:
        libcxx: *libcxx
    build_type: [null, Debug, Release, ANY]  # comment
    """)


@pytest.mark.parametrize("text", [default_settings_yml, _SETTINGS_USER_YML],
                         ids=["settings.yml", "settings_user.yml"])
def test_settings_yml(text):
    expected = yaml.safe_load(text)
    data = yaml.load(text, Loader=YamlSafeLoader)
    assert _typed(data) == _typed(expected)
    assert Settings(data).possible_values() == Settings(expected).possible_values()


# The usual contents of conan-center-index, and what YAML gives a type: unquoted versions are
# floats, ints or dates, digits-only checksums are ints, yes/no are booleans
_CONANDATA_YML = textwrap.dedent("""\
    sources:
      "1.10.0":
        url:
          - "https://github.com/org/lib/archive/v1.10.0.tar.gz"
          - "https://mirror.example.com/lib-1.10.0.tar.gz"
        sha256: "1b6c8c0b9ec9a0e9e9f8d1e7c1cb1b7a4e3d3c3a3c0e8b8d5e9a1f9e7a5c6d4b"
      "1.9":
        url: https://github.com/org/lib/archive/v1.9.tar.gz
        sha256: 2234567890123456789012345678901234567890123456789012345678901234
      1.10:
        url: "https://example.com/float.tar.gz"
        sha256: 0e12345
      2:
        url: 'https://example.com/int.tar.gz'
        sha256: 0755
      2023-01-01:
        url: https://example.com/date.tar.gz
        sha256: 1_000
      cci.20230101:
        url: "https://example.com/cci.tar.gz"
        sha256: abc
    patches:
      "1.10.0":
        - patch_file: "patches/0001-fix.patch"
          patch_description: "fix MSVC: don't use \\"__attribute__\\"\\t(tab)"
          patch_type: "portability"
          patch_source: https://github.com/org/lib/pull/123
        - patch_file: patches/0002-cmake.patch
          patch_description: >-
            folded description
            in two lines, with ümlauts and 日本語

            and a paragraph
          patch_type: conan
          base_path: src
        - patch_file: "patches/0003-literal.patch"
          patch_description: |
            literal description:
              indented line
            \tline starting with a tab
          patch_type: bugfix
      "1.9": &old_patches
        - patch_file: "patches/0001-old.patch"
          patch_description: 'single quoted, it''s
            in two lines'
          patch_type: official
      1.10: *old_patches
    common: &common {flag: yes, other: off, nothing: null, tilde: ~}
    extra:
      <<: *common
      flow: [a, "b", 1.5, .inf, 0x1F, 1e3, true]
      when: 2023-01-01T10:00:00Z
    scm:
      url: "git@github.com:org/lib.git"
      commit: "4ae3e5d"
    license: MIT  # Not dicts, trim_conandata() keeps them
    topics: [yes, 1.10, 0755, 2023-01-01, null]
    """)


@pytest.mark.parametrize("newline, bom", [("\n", ""), ("\r\n", ""), ("\n", "﻿")],
                         ids=["lf", "crlf", "bom"])
def test_conandata_yml(newline, bom):
    folder = temp_folder()
    conandata_path = os.path.join(folder, "conandata.yml")
    save(conandata_path, bom + _CONANDATA_YML.replace("\n", newline))
    # The self.conan_data of the recipes
    data = ConanFileLoader._load_data(os.path.join(folder, "conanfile.py"))  # noqa
    expected = yaml.safe_load(load(conandata_path))
    assert _typed(data) == _typed(expected)
    # export_conandata_patches() writes it in the exported conandata.yml
    dumped = yaml.safe_dump(data, default_flow_style=False)
    assert dumped == yaml.safe_dump(expected, default_flow_style=False)


@pytest.mark.parametrize("version", ["1.10.0", "1.9", "cci.20230101", "1.10", "3.0"])
def test_trim_conandata(version):
    """ trim_conandata() loads the exported conandata.yml again with yaml.safe_load(), and writes
    the data of its version: the same file with both loaders
    """
    def trim(loader):
        conanfile = ConanFileMock()
        conanfile.folders.set_base_export(temp_folder())
        conanfile.version = version
        conandata_path = os.path.join(conanfile.export_folder, "conandata.yml")
        save(conandata_path, _CONANDATA_YML)
        with mock.patch.object(yaml, "safe_load", lambda text: yaml.load(text, Loader=loader)):
            trim_conandata(conanfile)
        return load(conandata_path), conanfile.conan_data

    trimmed, data = trim(YamlSafeLoader)
    expected_trimmed, expected_data = trim(yaml.SafeLoader)
    assert trimmed == expected_trimmed
    assert _typed(data) == _typed(expected_data)


@pytest.mark.parametrize("text", [
    # A block scalar whose first line starts with a tab after the indentation ("|2" loads it)
    "description: |\n  \tfirst line\n  second\n",
    # The escapes of the two halves of a UTF-16 surrogate pair
    'description: "\\ud83d\\ude00"\n',
])
def test_only_pure_python_loads(text):
    """ The pure-Python loader loads it, libyaml doesn't. None in conan-center-index. Conan reports
    it as any other invalid conandata.yml
    """
    yaml.safe_load(text)
    folder = temp_folder()
    save(os.path.join(folder, "conandata.yml"), text)
    with pytest.raises(ConanException, match="Invalid yml format at conandata.yml"):
        ConanFileLoader._load_data(os.path.join(folder, "conanfile.py"))  # noqa


@pytest.mark.parametrize("text", [
    "url:\thttps://example.com\n",  # A tab after the ":"
    "description: a\tb\n",  # A tab in a plain scalar
    "urls: [https://example.com/a?b=c]\n",  # A "?" in a plain scalar of a flow sequence
])
def test_only_libyaml_loads(text):
    """ libyaml loads it, the pure-Python loader doesn't, so trim_conandata() and
    update_conandata(), that still use yaml.safe_load(), raise an error with it
    """
    yaml.load(text, Loader=YamlSafeLoader)
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(text)
