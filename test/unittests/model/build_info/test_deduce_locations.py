import os
import platform

import pytest

from conan.errors import ConanException
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
def test_simple_deduce_locations_static(lib_name, libs):
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


@pytest.mark.parametrize("lib_name, libs", [
    ("liblog4cxx.so.15.2.0", ["log4cxx"]),
    ("libapr-1.0.dylib", ["apr-1"]),
    ("libapr-1.so.0.7.4", ["apr-1"])
])
def test_complex_deduce_locations_shared(lib_name, libs):
    """
    Tests real examples of shared library names in Linux/MacOS,
    e.g., log4cxx, apr-1, etc.

    Related issue: https://github.com/conan-io/conan/issues/16990
    """
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
    assert result.type == "shared-library"


@pytest.mark.parametrize("lib_name, dll_name, libs", [
    ("libcurl_imp.lib", "libcurl.dll", ["libcurl_imp"]),
    ("libcrypto.lib", "libcrypto-3-x64.dll", ["libcrypto"]),
    ("libssl.lib", "libssl-3-x64.dll", ["libssl"]),
    ("zdll.lib", "zlib1.dll", ["zdll"])
])
def test_windows_shared_link_locations(lib_name, dll_name, libs):
    """
    Tests real examples of shared library names in Windows,
    e.g., openssl, zlib, libcurlb, etc.
    """
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
    {"charset": ["charset.lib", "charset-1.dll"],
     "iconv": ["iconv.lib", "iconv-2.dll"]},
    {"charset": ["libcharset.so.1.0.0"],
     "iconv": ["libiconv.so.2.6.1"]},
])
def test_windows_several_shared_link_locations(lib_info):
    """
    Tests a real model as LIBICONV with several libs defined in the root component
    """
    folder = temp_folder()
    locations = {}
    is_windows = False
    for lib_name, lib_files in lib_info.items():
        imp_location = os.path.join(folder, "libdir", lib_files[0])
        save(imp_location, "")
        if len(lib_files) > 1:
            is_windows = True
            location = os.path.join(folder, "bindir", lib_files[1])
            save(location, "")
        else:
            location = imp_location  # Linux
        locations[lib_name] = (location, imp_location)

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.bindirs = ["bindir"]
    cppinfo.libs = list(lib_info.keys())
    cppinfo.set_relative_base_folder(folder)

    result = cppinfo.deduce_full_cpp_info(ConanFileMock())
    for lib_name in lib_info:
        assert result.components[f"_{lib_name}"].location == locations[lib_name][0].replace("\\", "/")
        if is_windows:
            assert result.components[f"_{lib_name}"].link_location == locations[lib_name][1].replace("\\", "/")
        assert result.components[f"_{lib_name}"].type == "shared-library"


@pytest.mark.skipif(platform.system() == "Windows", reason="Can't apply symlink on Windows")
def test_shared_link_locations_symlinks():
    """
    Tests auto deduce location is able to find the real path of
    any symlink created in the libs folder
    """
    folder = temp_folder()
    # forcing a folder that it's not going to be analysed by the deduce_location() function
    real_location = os.path.join(folder, "other", "mylib.so")
    save(real_location, "")
    # Symlinks
    os.makedirs(os.path.join(folder, "libdir"))
    sym_1 = os.path.join(folder, "libdir", "mylib.1.0.0.so")
    sym_2 = os.path.join(folder, "libdir", "mylib.2.0.0.so")
    os.symlink(real_location, sym_1)
    os.symlink(sym_1, sym_2)

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.libs = ["mylib"]
    cppinfo.set_relative_base_folder(folder)

    result = cppinfo.deduce_full_cpp_info(ConanFileMock())
    assert result.location == real_location
    assert result.type == "shared-library"


def test_error_if_shared_and_static_found():
    folder = temp_folder()
    save(os.path.join(folder, "libdir", "libmylib.a"), "")
    save(os.path.join(folder, "libdir", "libmylib.so"), "")

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.libs = ["mylib"]
    cppinfo.set_relative_base_folder(folder)
    folder = folder.replace("\\", "/")
    with pytest.raises(ConanException) as e:
        cppinfo.deduce_full_cpp_info(ConanFileMock())
    assert (f"obtained for library 'mylib' both static and shared libraries at the same time:\n"
            f"- STATIC: {folder}/libdir/libmylib.a\n"
            f"- SHARED: {folder}/libdir/libmylib.so") in str(e.value)
