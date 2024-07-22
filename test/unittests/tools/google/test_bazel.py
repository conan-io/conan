import os
import platform
from unittest.mock import MagicMock

import pytest

from conan.tools.files import save
from conan.tools.google import Bazel
from conan.tools.google.bazeldeps import _relativize_path, _get_libs
from conans.model.options import Options
from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder


@pytest.fixture(scope="module")
def cpp_info():
    folder = temp_folder(path_with_spaces=False)
    bindirs = os.path.join(folder, "bin")
    libdirs = os.path.join(folder, "lib")
    save(ConanFileMock(), os.path.join(bindirs, "mylibwin.dll"), "")
    save(ConanFileMock(), os.path.join(bindirs, "mylibwin2.dll"), "")
    save(ConanFileMock(), os.path.join(bindirs, "myliblin.so"), "")
    save(ConanFileMock(), os.path.join(bindirs, "mylibmac.dylib"), "")
    save(ConanFileMock(), os.path.join(bindirs, "protoc"), "")  # binary
    save(ConanFileMock(), os.path.join(libdirs, "myliblin.a"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibmac.a"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibwin.lib"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibwin2.if.lib"), "")
    save(ConanFileMock(), os.path.join(libdirs, "libmylib.so"), "")
    save(ConanFileMock(), os.path.join(libdirs, "subfolder", "libmylib.a"), "")  # recursive
    cpp_info_mock = MagicMock(_base_folder=None, libdirs=None, bindirs=None, libs=None)
    cpp_info_mock._base_folder = folder.replace("\\", "/")
    cpp_info_mock.libdirs = [libdirs]
    cpp_info_mock.bindirs = [bindirs]
    return cpp_info_mock


@pytest.mark.skipif(platform.system() == "Windows", reason="Remove this skip for Conan 2.x"
                                                           "Needs conanfile.commands")
def test_bazel_command_with_empty_config():
    conanfile = ConanFileMock()
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    # Uncomment Conan 2.x
    assert 'bazel build //test:label' in conanfile.commands


@pytest.mark.skipif(platform.system() == "Windows", reason="Remove this skip for Conan 2.x."
                                                           "Needs conanfile.commands")
def test_bazel_command_with_config_values():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.google.bazel:configs", ["config", "config2"])
    conanfile.conf.define("tools.google.bazel:bazelrc_path", ["/path/to/bazelrc"])
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    assert "bazel --bazelrc=/path/to/bazelrc build " \
           "--config=config --config=config2 //test:label" in conanfile.commands


@pytest.mark.parametrize("path, pattern, expected", [
    ("", "./", ""),
    ("./", "", "./"),
    ("/my/path/", "", "/my/path/"),
    ("\\my\\path\\", "", "\\my\\path\\"),
    ("/my/path/absolute", ".*/path", "absolute"),
    ("/my/path/absolute", "/my/path", "absolute"),
    ("\\my\\path\\absolute", "/my/path", "absolute"),
    ("/my/./path/absolute/", "/my/./path", "absolute"),
    ("/my/./path/absolute/", "/my/./path/absolute/", "./"),
    ("././my/path/absolute/././", "./", "my/path/absolute"),
    ("C:\\my\\path\\absolute\\with\\folder", "C:\\", "my/path/absolute/with/folder"),
    ("C:\\my\\path\\absolute\\with\\folder", ".*/absolute", "with/folder"),
    ("C:\\my\\path\\myabsolute\\with\\folder", ".*/absolute", "C:\\my\\path\\myabsolute\\with\\folder"),
])
def test_bazeldeps_relativize_path(path, pattern, expected):
    assert _relativize_path(path, pattern) == expected


@pytest.mark.parametrize("libs, is_shared, expected", [
    # expected == (lib_name, is_shared, library_path, interface_library_path)
    (["mylibwin"], False, [('mylibwin', False, '{base_folder}/lib/mylibwin.lib', None)]),
    # Win + shared
    (["mylibwin"], True, [('mylibwin', True, '{base_folder}/bin/mylibwin.dll', '{base_folder}/lib/mylibwin.lib')]),
    # Win + shared (interface with another ext)
    (["mylibwin2"], True,
     [('mylibwin2', True, '{base_folder}/bin/mylibwin2.dll', '{base_folder}/lib/mylibwin2.if.lib')]),
    # Win + Mac + shared
    (["mylibwin", "mylibmac"], True, [('mylibmac', True, '{base_folder}/bin/mylibmac.dylib', None),
                                      ('mylibwin', True, '{base_folder}/bin/mylibwin.dll',
                                       '{base_folder}/lib/mylibwin.lib')]),
    # Linux + Mac + static
    (["myliblin", "mylibmac"], False, [('mylibmac', False, '{base_folder}/lib/mylibmac.a', None),
                                       ('myliblin', False, '{base_folder}/lib/myliblin.a', None)]),
    # mylib + shared (saved as libmylib.so) -> removing the leading "lib" if it matches
    (["mylib"], True, [('mylib', True, '{base_folder}/lib/libmylib.so', None)]),
    # mylib + static (saved in a subfolder subfolder/libmylib.a) -> non-recursive at this moment
    (["mylib"], False, []),
    # no lib matching
    (["noexist"], False, []),
    # no lib matching + Win + static
    (["noexist", "mylibwin"], False, [('mylibwin', False, '{base_folder}/lib/mylibwin.lib', None)]),
    # protobuf (Issue related https://github.com/conan-io/conan/issues/15390)
    (["protoc"], True, []),
    # non-conventional library name (Issue related https://github.com/conan-io/conan/pull/11343)
    (["libmylib.so"], True, [('libmylib.so', True, '{base_folder}/lib/libmylib.so', None)]),
])
def test_bazeldeps_get_libs(cpp_info, libs, is_shared, expected):
    cpp_info.libs = libs
    ret = []
    for (lib, is_shared, lib_path, interface_lib_path) in expected:
        if lib_path:
            lib_path = lib_path.format(base_folder=cpp_info._base_folder)
        if interface_lib_path:
            interface_lib_path = interface_lib_path.format(base_folder=cpp_info._base_folder)
        ret.append((lib, is_shared, lib_path, interface_lib_path))
    found_libs = _get_libs(ConanFileMock(options=Options(options_values={"shared": is_shared})),
                           cpp_info)
    found_libs.sort()
    ret.sort()
    assert found_libs == ret
