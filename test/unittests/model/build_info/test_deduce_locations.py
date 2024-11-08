import os

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.tools.files import save
from conans.model.build_info import CppInfo
from conans.util.files import save


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


def test_shared_link_locations_symlinks():
    pass
