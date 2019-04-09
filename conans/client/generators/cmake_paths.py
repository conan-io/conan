from conans.client.generators.cmake import DepsCppCmake
from conans.model import Generator


class CMakePathsGenerator(Generator):

    @property
    def filename(self):
        return "conan_paths.cmake"

    @property
    def content(self):
        lines = []
        # The CONAN_XXX_ROOT variables are needed because the FindXXX.cmake or XXXConfig.cmake
        # in a package could have been "patched" with the `cmake.patch_config_paths()`
        # replacing absolute paths with CONAN_XXX_ROOT variables.
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            var_name = "CONAN_{}_ROOT".format(dep_name.upper())
            lines.append('set({} {})'.format(var_name, DepsCppCmake(dep_cpp_info).rootpath))

        # We want to prioritize the FindXXX.cmake files:
        # 1. First the files found in the packages
        # 2. The previously set (by default CMAKE_MODULE_PATH is empty)
        # 3. The "install_folder" ones, in case there is no FindXXX.cmake, try with the install dir
        #    if the user used the "cmake_find_package" will find the auto-generated
        # 4. The CMake installation dir/Modules ones.
        deps = DepsCppCmake(self.deps_build_info)
        lines.append("set(CMAKE_MODULE_PATH {deps.build_paths} ${{CMAKE_MODULE_PATH}} "
                     "${{CMAKE_CURRENT_LIST_DIR}})".format(deps=deps))
        lines.append("set(CMAKE_PREFIX_PATH {deps.build_paths} ${{CMAKE_PREFIX_PATH}} "
                     "${{CMAKE_CURRENT_LIST_DIR}})".format(deps=deps))

        return "\n".join(lines)
