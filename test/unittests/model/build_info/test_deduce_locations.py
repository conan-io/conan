import os
from unittest.mock import MagicMock

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.tools.files import save
from conan.tools.google.bazeldeps import _get_libs
from conans.model.build_info import CppInfo
from conans.util.files import save


# @pytest.fixture(scope="module")
# def cpp_info():
#     folder = temp_folder(path_with_spaces=False)
#     bindirs = os.path.join(folder, "bin")
#     libdirs = os.path.join(folder, "lib")
#     save(ConanFileMock(), os.path.join(bindirs, "mylibwin.dll"), "")
#     save(ConanFileMock(), os.path.join(bindirs, "mylibwin2.dll"), "")
#     save(ConanFileMock(), os.path.join(bindirs, "myliblin.so"), "")
#     save(ConanFileMock(), os.path.join(bindirs, "mylibmac.dylib"), "")
#     save(ConanFileMock(), os.path.join(bindirs, "protoc"), "")  # binary
#     save(ConanFileMock(), os.path.join(libdirs, "myliblin.a"), "")
#     save(ConanFileMock(), os.path.join(libdirs, "mylibmac.a"), "")
#     save(ConanFileMock(), os.path.join(libdirs, "mylibwin.lib"), "")
#     save(ConanFileMock(), os.path.join(libdirs, "mylibwin2.if.lib"), "")
#     save(ConanFileMock(), os.path.join(libdirs, "libmylib.so"), "")
#     save(ConanFileMock(), os.path.join(libdirs, "subfolder", "libmylib.a"), "")  # recursive
#     cpp_info_mock = MagicMock(_base_folder=None, libdirs=[], bindirs=[], libs=[],
#                               aggregated_components=MagicMock())
#     cpp_info_mock._base_folder = folder.replace("\\", "/")
#     cpp_info_mock.libdirs = [libdirs]
#     cpp_info_mock.bindirs = [bindirs]
#     cpp_info_mock.aggregated_components.return_value = cpp_info_mock
#     return cpp_info_mock
#
#
# @pytest.mark.parametrize("libs, is_shared, expected", [
#     # expected == (lib_name, is_shared, library_path, interface_library_path)
#     (["mylibwin"], False, [('mylibwin', False, '{base_folder}/lib/mylibwin.lib', None)]),
#     # Win + shared
#     (["mylibwin"], True, [('mylibwin', True, '{base_folder}/bin/mylibwin.dll', '{base_folder}/lib/mylibwin.lib')]),
#     # Win + shared (interface with another ext)
#     (["mylibwin2"], True, [('mylibwin2', True, '{base_folder}/bin/mylibwin2.dll', '{base_folder}/lib/mylibwin2.if.lib')]),
#     # Mac + shared
#     (["mylibmac"], True, [('mylibmac', True, '{base_folder}/bin/mylibmac.dylib', None)]),
#     # Mac + static
#     (["mylibmac"], False, [('mylibmac', False, '{base_folder}/lib/mylibmac.a', None)]),
#     # mylib + shared (saved as libmylib.so) -> removing the leading "lib" if it matches
#     (["mylib"], True, [('mylib', True, '{base_folder}/lib/libmylib.so', None)]),
#     # mylib + static (saved in a subfolder subfolder/libmylib.a) -> non-recursive at this moment
#     (["mylib"], False, []),
#     # no lib matching
#     (["noexist"], False, []),
#     # no lib matching + Win + static
#     (["noexist", "mylibwin"], False, [('mylibwin', False, '{base_folder}/lib/mylibwin.lib', None)]),
#     # protobuf (Issue related https://github.com/conan-io/conan/issues/15390)
#     (["protoc"], True, []),
#     # non-conventional library name (Issue related https://github.com/conan-io/conan/pull/11343)
#     (["libmylib.so"], True, [('libmylib.so', True, '{base_folder}/lib/libmylib.so', None)]),
# ])
# def test_bazeldeps_get_libs(cpp_info, libs, is_shared, expected):
#     cpp_info.libs = libs
#     ret = []
#     for (lib, is_shared, lib_path, interface_lib_path) in expected:
#         if lib_path:
#             lib_path = lib_path.format(base_folder=cpp_info._base_folder)
#         if interface_lib_path:
#             interface_lib_path = interface_lib_path.format(base_folder=cpp_info._base_folder)
#         ret.append((lib, is_shared, lib_path, interface_lib_path))
#     dep = MagicMock()
#     dep.options.get_safe.return_value = is_shared
#     dep.ref.name = "my_pkg"
#     found_libs = _get_libs(dep, cpp_info)
#     found_libs.sort()
#     ret.sort()
#     assert found_libs == ret



@pytest.mark.parametrize("lib_name, libs", [
    ("myliblin.a", ["myliblin"]),
    ("libmyliblin.a", ["myliblin"]),
    ("mylibmac.a", ["mylibmac"]),
    ("mylibwin.lib", ["mylibwin"]),
    ("libmylibwin.lib", ["libmylibwin"]),
    ("mylibwin2.if.lib", ["mylibwin2.if.lib"]),
    ("mylibwin2.if.lib", ["mylibwin2"])
])
def test_simple_deduce_locations(lib_name, libs):
    folder = temp_folder()
    location = os.path.join(folder, "libdir", lib_name)
    save(location, "")

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.libs = libs
    cppinfo.set_relative_base_folder(folder)

    result = cppinfo.deduce_full_cpp_info(ConanFileMock())
    assert result.location == location.replace("\\", "/")
    assert result.link_location is None
    assert result.type == "static-library"


def test_deduce_shared_link_locations():
    folder = temp_folder()
    imp_location = os.path.join(folder, "libdir", "mylib.lib")
    save(imp_location, "")
    location = os.path.join(folder, "bindir", "mylib.dll")
    save(location, "")

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.bindirs = ["bindir"]
    cppinfo.libs = ["mylib"]
    cppinfo.set_relative_base_folder(folder)

    result = cppinfo.deduce_full_cpp_info(ConanFileMock())
    assert result.location == location.replace("\\", "/")
    assert result.link_location == imp_location.replace("\\", "/")
    assert result.type == "shared-library"


@pytest.mark.parametrize("lib_name, dll_name, libs", [
    ("libcurl_imp.lib", "libcurl.dll", ["libcurl_imp"]),
    ("libcrypto.lib", "libcrypto-3-x64.dll", ["libcrypto"]),
    ("libssl.lib", "libssl-3-x64.dll", ["libssl"]),
    ("zdll.lib", "zlib1.dll", ["zdll"]),
    (["iconv.lib", "charset.lib"], ["charset-1.dll", "iconv-2.dll"], ["charset", "iconv"]),
])
def test_windows_shared_link_locations(lib_name, dll_name, libs):
    folder = temp_folder()
    imp_location = os.path.join(folder, "libdir", lib_name)
    save(imp_location, "")
    location = os.path.join(folder, "bindir", dll_name)
    save(location, "")

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.bindirs = ["bindir"]
    cppinfo.libs = libs
    cppinfo.set_relative_base_folder(folder)

    result = cppinfo.deduce_full_cpp_info(ConanFileMock())
    assert result.location == location.replace("\\", "/")
    assert result.link_location == imp_location.replace("\\", "/")
    assert result.type == "shared-library"


@pytest.mark.parametrize("lib_info", [
    {"charset": ("charset.lib", "charset-1.dll"),
     "iconv": ("iconv.lib", "iconv-2.dll")}
])
def test_windows_several_shared_link_locations(lib_info):
    folder = temp_folder()
    locations = {}
    for lib_name, lib_files in lib_info.items():
        imp_location = os.path.join(folder, "libdir", lib_files[0])
        save(imp_location, "")
        location = os.path.join(folder, "bindir", lib_files[1])
        save(location, "")
        locations[lib_name] = (location, imp_location)

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.bindirs = ["bindir"]
    cppinfo.libs = list(lib_info.keys())
    cppinfo.set_relative_base_folder(folder)

    result = cppinfo.deduce_full_cpp_info(ConanFileMock())
    for lib_name in lib_info:
        assert result.components[f"_{lib_name}"].location == locations[lib_name][0].replace("\\", "/")
        assert result.components[f"_{lib_name}"].link_location == locations[lib_name][1].replace("\\", "/")
    assert result.type == "shared-library"
