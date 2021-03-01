from conan.tools.cmake import CMakeDeps
from conans import ConanFile, Settings
from conans.model.build_info import CppInfo
from conans.model.env_info import EnvValues
from conans.test.utils.mocks import TestBufferConanOutput


def test_cpp_info_name_cmakedeps():

    conanfile = ConanFile(TestBufferConanOutput(), None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.names["cmake_find_package_multi"] = "MySuperPkg1"
    cpp_info.filenames["cmake_find_package_multi"] = "ComplexFileName1"
    conanfile.deps_cpp_info.add("mypkg", cpp_info)

    cmakedeps = CMakeDeps(conanfile)
    files = cmakedeps.content
    assert "TARGET MySuperPkg1::MySuperPkg1" in files["ComplexFileName1Config.cmake"]
