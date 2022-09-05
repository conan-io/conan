import os

from conan.tools.cmake.presets import load_cmake_presets, get_configure_preset
from conans.util.files import save, load


class CMakeInitialCache:
    """CMakeToolchain sub-generator"""
    """
    # Build the vtkHybrid kit.
    set(VTK_USE_HYBRID ON CACHE BOOL "doc string")
    """

    def __init__(self, conanfile, cmaketoolchain):
        self._conanfile = conanfile

        cmake_presets = load_cmake_presets(conanfile.generators_folder)
        configure_preset = get_configure_preset(cmake_presets, conanfile)
        self._cache_variables = configure_preset["cacheVariables"]

    def _content(self):
        return {}

    def generate(self):
        cache_cmake_path = os.path.join(self._conanfile.generators_folder, "CMakeInitialCache.cmake")
        if not os.path.exists(cache_cmake_path):
            content = self._content()
            save(cache_cmake_path, content)

    def configure(self, variables=None, build_script_folder=None):
        cmakelist_folder = self._conanfile.source_folder
        if build_script_folder:
            cmakelist_folder = os.path.join(self._conanfile.source_folder, build_script_folder)

        build_folder = self._conanfile.build_folder
        generator_folder = self._conanfile.generators_folder

        mkdir(self._conanfile, build_folder)

        arg_list = [self._cmake_program]
        if self._generator:
            arg_list.append('-G "{}"'.format(self._generator))
        if self._toolchain_file:
            if os.path.isabs(self._toolchain_file):
                toolpath = self._toolchain_file
            else:
                toolpath = os.path.join(generator_folder, self._toolchain_file)
            arg_list.append('-DCMAKE_TOOLCHAIN_FILE="{}"'.format(toolpath.replace("\\", "/")))
        if self._conanfile.package_folder:
            pkg_folder = self._conanfile.package_folder.replace("\\", "/")
            arg_list.append('-DCMAKE_INSTALL_PREFIX="{}"'.format(pkg_folder))

        if not variables:
            variables = {}
        self._cache_variables.update(variables)

        arg_list.extend(['-D{}="{}"'.format(k, v) for k, v in self._cache_variables.items()])
        arg_list.append('"{}"'.format(cmakelist_folder))

        command = " ".join(arg_list)
        self._conanfile.output.info("CMake command: %s" % command)
        with chdir(self, build_folder):
            self._conanfile.run(command)
