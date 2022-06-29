import os
import platform

import pytest

from conan.tools.files import check_md5, check_sha1, check_sha256, collect_libs
from conans.model.build_info import CppInfo
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_collect_libs():
    conanfile = ConanFileMock()
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    # Without package_folder
    result = collect_libs(conanfile)
    assert [] == result

    # Default behavior
    conanfile.folders.set_base_package(temp_folder())
    mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
    save(mylib_path, "")

    result = collect_libs(conanfile)
    assert ["mylib"] == result

    # Custom folder
    customlib_path = os.path.join(conanfile.package_folder, "custom_folder", "customlib.lib")
    save(customlib_path, "")
    result = collect_libs(conanfile, folder="custom_folder")
    assert ["customlib"] == result

    # Custom folder doesn't exist
    result = collect_libs(conanfile, folder="fake_folder")
    assert [] == result
    assert "Lib folder doesn't exist, can't collect libraries:" in conanfile.output

    # Use cpp_info.libdirs
    conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
    result = collect_libs(conanfile)
    assert ["customlib", "mylib"] == result

    # Custom folder with multiple libdirs should only collect from custom folder
    assert ["lib", "custom_folder"] == conanfile.cpp_info.libdirs
    result = collect_libs(conanfile, folder="custom_folder")
    assert ["customlib"] == result

    # Unicity of lib names
    conanfile = ConanFileMock()
    conanfile.folders.set_base_package(temp_folder())
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    custom_mylib_path = os.path.join(conanfile.package_folder, "custom_folder", "mylib.lib")
    lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
    save(custom_mylib_path, "")
    save(lib_mylib_path, "")
    conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
    result = collect_libs(conanfile)
    assert ["mylib"] == result

    # Warn lib folder does not exist with correct result
    conanfile = ConanFileMock()
    conanfile.folders.set_base_package(temp_folder())
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "mylib.lib")
    save(lib_mylib_path, "")
    no_folder_path = os.path.join(conanfile.package_folder, "no_folder")
    conanfile.cpp_info.libdirs = ["no_folder", "lib"]  # 'no_folder' does NOT exist
    result = collect_libs(conanfile)
    assert ["mylib"] == result
    assert "WARN: Lib folder doesn't exist, can't collect libraries: %s" % no_folder_path \
           in conanfile.output

@pytest.mark.skipif(platform.system() == "Windows", reason="Needs symlinks support")
def test_collect_libs_symlinks():
    # Keep only the shortest lib name per group of symlinks
    conanfile = ConanFileMock()
    conanfile.folders.set_base_package(temp_folder())
    conanfile.cpp_info = CppInfo(conanfile.name, "")
    version_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.1.0.0.dylib")
    soversion_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.1.dylib")
    lib_mylib_path = os.path.join(conanfile.package_folder, "lib", "libmylib.dylib")
    lib_mylib2_path = os.path.join(conanfile.package_folder, "lib", "libmylib.2.dylib")
    lib_mylib3_path = os.path.join(conanfile.package_folder, "custom_folder", "libmylib.3.dylib")
    save(version_mylib_path, "")
    os.symlink(version_mylib_path, soversion_mylib_path)
    os.symlink(soversion_mylib_path, lib_mylib_path)
    save(lib_mylib2_path, "")
    save(lib_mylib3_path, "")
    conanfile.cpp_info.libdirs = ["lib", "custom_folder"]
    result = collect_libs(conanfile)
    assert ["mylib", "mylib.2", "mylib.3"] == result
