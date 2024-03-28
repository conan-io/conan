import os
import platform
from unittest.mock import MagicMock

import pytest

from conan.tools.files import save, fetch_libraries
from conans.model.build_info import CppInfo
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder


@pytest.fixture(scope="module")
def cpp_info():
    folder = temp_folder(path_with_spaces=False)
    bindirs = os.path.join(folder, "bin")
    libdirs = os.path.join(folder, "lib")
    # Shared Windows with interface ending with .if.lib
    save(ConanFileMock(), os.path.join(bindirs, "mylibwin2.dll"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibwin2.if.lib"), "")
    # Shared Windows
    save(ConanFileMock(), os.path.join(bindirs, "mylibwinsh.dll"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibwinsh.lib"), "")
    # Static Windows
    save(ConanFileMock(), os.path.join(libdirs, "mylibwinst.lib"), "")
    # Shared macOS
    save(ConanFileMock(), os.path.join(bindirs, "mylibmacsh.dylib"), "")
    # Binary
    save(ConanFileMock(), os.path.join(bindirs, "protoc"), "")
    # Static Linux and macOS
    save(ConanFileMock(), os.path.join(libdirs, "myliblin.a"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibmacst.a"), "")
    # Shared Linux and shared name starting with "lib"
    save(ConanFileMock(), os.path.join(bindirs, "myliblinsh.so"), "")
    save(ConanFileMock(), os.path.join(libdirs, "libmylibsh.so"), "")
    # Recursive folder
    save(ConanFileMock(), os.path.join(libdirs, "subfolder", "libmylib.a"), "")
    cpp_info_mock = MagicMock(_base_folder=None, libdirs=None, bindirs=None, libs=None)
    cpp_info_mock._base_folder = folder.replace("\\", "/")
    cpp_info_mock.libdirs = [libdirs]
    cpp_info_mock.bindirs = [bindirs]
    return cpp_info_mock


@pytest.mark.parametrize("libs, expected", [
    # expected == (lib_name, is_shared, library_path, interface_library_path)
    (["mylibwinst"], [('mylibwinst', '{base_folder}/lib/mylibwinst.lib', "", "")]),
    # Win + shared
    (["mylibwinsh"], [('mylibwinsh', '{base_folder}/bin/mylibwinsh.dll', '{base_folder}/lib/mylibwinsh.lib', "")]),
    # Win + shared (interface with another ext)
    (["mylibwin2"],
     [('mylibwin2', '{base_folder}/bin/mylibwin2.dll', '{base_folder}/lib/mylibwin2.if.lib', "")]),
    # Win + Mac + shared
    (["mylibwinsh", "mylibmacsh"], [('mylibmacsh', '{base_folder}/bin/mylibmacsh.dylib', "", ""),
                                  ('mylibwinsh', '{base_folder}/bin/mylibwinsh.dll', '{base_folder}/lib/mylibwinsh.lib', "")]),
    # Linux + Mac + static
    (["myliblin", "mylibmacst"], [('mylibmacst', '{base_folder}/lib/mylibmacst.a', "", ""),
                                  ('myliblin', '{base_folder}/lib/myliblin.a', "", "")]),
    # mylib + shared (saved as libmylib.so) -> removing the leading "lib" if it matches
    (["mylibsh"], [('mylibsh', '{base_folder}/lib/libmylibsh.so', "", "")]),
    # mylib + static (saved in a subfolder subfolder/libmylib.a) -> non-recursive at this moment
    (["mylib"], []),
    # no lib matching
    (["noexist"], []),
    # no lib matching + Win + static
    (["noexist", "mylibwinst"], [('mylibwinst', '{base_folder}/lib/mylibwinst.lib', "", "")]),
    # protobuf (Issue related https://github.com/conan-io/conan/issues/15390)
    (["protoc"], []),
    # non-conventional library name (Issue related https://github.com/conan-io/conan/pull/11343)
    (["libmylibsh.so"], [('libmylibsh.so', '{base_folder}/lib/libmylibsh.so', "", "")]),
])
def test_fetch_libraries(libs, expected, cpp_info):
    cpp_info.libs = libs
    ret = []
    for (lib, lib_path, interface_lib_path, symlink_path) in expected:
        if lib_path:
            lib_path = lib_path.format(base_folder=cpp_info._base_folder)
        if interface_lib_path:
            interface_lib_path = interface_lib_path.format(base_folder=cpp_info._base_folder)
        ret.append((lib, lib_path, interface_lib_path, symlink_path))

    found_libs = fetch_libraries(ConanFileMock(), cpp_info)
    ret.sort()
    assert found_libs == ret

@pytest.mark.parametrize("cpp_info_libs, expected", [
    # Only mylib associated
    (["mylib"], [('mylib', '{base_folder}/lib/libmylib.dylib', '', '{base_folder}/lib/libmylib.1.dylib')]),
    # All the existing ones
    ([], [
        ('mylib', '{base_folder}/lib/libmylib.dylib', '', '{base_folder}/lib/libmylib.1.dylib'),
        ('mylib.1', '{base_folder}/lib/libmylib.1.dylib', '', '{base_folder}/lib/libmylib.1.0.0.dylib'),
        ('mylib.1.0.0', '{base_folder}/lib/libmylib.1.0.0.dylib', '', ''),
        ('mylib.2', '{base_folder}/lib/libmylib.2.dylib', '', ''),
        ('mylib.3', '{base_folder}/custom_folder/libmylib.3.dylib', '', '')]),
])
@pytest.mark.skipif(platform.system() == "Windows", reason="Needs symlinks support")
def test_fetch_libraries_symlinks(cpp_info_libs, expected):
    """
    Tests how fetch_libraries function saves the shortest path (symlink) defined

    Folder tree structure:

        .
        ├── custom_folder
        │   └── libmylib.3.dylib
        └── lib
            ├── libmylib.1.0.0.dylib
            ├── libmylib.1.dylib -> lib/libmylib.1.0.0.dylib
            ├── libmylib.2.dylib
            └── libmylib.dylib -> lib/libmylib.1.dylib
    """
    # Keep only the shortest lib name per group of symlinks
    base_folder = temp_folder()
    conanfile = ConanFileMock(options_values={"shared": True})
    conanfile.folders.set_base_package(base_folder)
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    # Lib dirs and libraries
    lib_folder = os.path.join(conanfile.package_folder, "lib")
    custom_folder = os.path.join(conanfile.package_folder, "custom_folder")
    version_mylib_path = os.path.join(lib_folder, "libmylib.1.0.0.dylib")
    soversion_mylib_path = os.path.join(lib_folder, "libmylib.1.dylib")
    lib_mylib_path = os.path.join(lib_folder, "libmylib.dylib")
    lib_mylib2_path = os.path.join(lib_folder, "libmylib.2.dylib")
    lib_mylib3_path = os.path.join(custom_folder, "libmylib.3.dylib")
    save(conanfile, version_mylib_path, "")
    os.symlink(version_mylib_path, soversion_mylib_path)  # libmylib.1.dylib -> lib/libmylib.1.0.0.dylib
    os.symlink(soversion_mylib_path, lib_mylib_path)  # libmylib.dylib -> lib/libmylib.1.dylib
    save(conanfile, lib_mylib2_path, "")
    save(conanfile, lib_mylib3_path, "")
    conanfile.cpp_info.libdirs = [lib_folder, custom_folder]
    ret = []
    for (lib, lib_path, _, symlink_path) in expected:
        if lib_path:
            lib_path = lib_path.format(base_folder=base_folder)
        if symlink_path:
            symlink_path = symlink_path.format(base_folder=base_folder)
        ret.append((lib, lib_path, _, symlink_path))
    result = fetch_libraries(conanfile, cpp_info_libs=cpp_info_libs)
    assert ret == result


def test_basic_fetch_libraries():
    conanfile = ConanFileMock()
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    # Without package_folder
    result = fetch_libraries(conanfile)
    assert [] == result

    # Default behavior
    conanfile.folders.set_base_package(temp_folder())
    mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
    save(conanfile, mylib_path, "")

    result = fetch_libraries(conanfile, cpp_info_libs=[])
    assert ["mylib"] == result

    # Custom folder
    customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
    save(conanfile, customlib_path, "")
    result = fetch_libraries(conanfile, extra_folders=["custom_folder"])
    assert ["customlib"] == result

    # Custom folder doesn't exist
    result = fetch_libraries(conanfile, extra_folders=["fake_folder"])
    assert [] == result
    assert "Lib folder doesn't exist, can't collect libraries:" in conanfile.output

    # Use cpp_info.libdirs
    conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
    result = fetch_libraries(conanfile)
    assert ["customlib", "mylib"] == result

    # Custom folder with multiple libdirs should only collect from custom folder
    assert ["lib", "custom_folder"] == conanfile.cpp_info.libdirs
    result = fetch_libraries(conanfile, extra_folders=["custom_folder"])
    assert ["customlib"] == result

    # Unicity of lib names
    conanfile = ConanFileMock()
    conanfile.folders.set_base_package(temp_folder())
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
    lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
    save(conanfile, custom_mylib_path, "")
    save(conanfile, lib_mylib_path, "")
    conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
    result = fetch_libraries(conanfile)
    assert ["mylib"] == result

    # Warn lib folder does not exist with correct result
    conanfile = ConanFileMock()
    conanfile.folders.set_base_package(temp_folder())
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
    save(conanfile, lib_mylib_path, "")
    no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
    conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
    result = fetch_libraries(conanfile)
    assert ["mylib"] == result
    assert "WARN: Lib folder doesn't exist, can't collect libraries: %s" % no_folder_path \
           in conanfile.output
