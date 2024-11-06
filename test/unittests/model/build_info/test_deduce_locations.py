import os

from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conans.model.build_info import CppInfo
from conans.util.files import save


def test_deduce_locations():
    folder = temp_folder()
    location = os.path.join(folder, "libdir", "mylib.lib")
    save(location, "")

    cppinfo = CppInfo()
    cppinfo.libdirs = ["libdir"]
    cppinfo.libs = ["mylib"]
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
