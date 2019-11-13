
import platform

from conans.client import tools
from conans.client.build.base_cmake import BaseCMake, _compute_build_flags
from conans.client.build.cmake_flags import is_multi_configuration, get_generator
from conans.client.toolchain.cmake import CMakeToolchain
from conans.errors import ConanException


def _validate_recipe(conanfile):
    # Toolchain is required
    toolchain_method = getattr(conanfile, "toolchain", None)
    if not toolchain_method or not callable(toolchain_method):
        raise ConanException("Using 'CMakeToolchainBuildHelper' helper, requires 'toolchain()' method"
                             " to be defined.")

    return  # TODO: I do want to check this, but then I'd need to rewrite some tests :S
    forbidden_generators = ["cmake", "cmake_multi", "cmake_paths"]
    if any(it in conanfile.generators for it in forbidden_generators):
        raise ConanException("Usage of toolchain is only supported with 'cmake_find_package'"
                             " or 'cmake_find_package_multi' generators")


class CMakeToolchainBuildHelper(BaseCMake):
    """ CMake helper to use together with the toolchain feature, it has the same interface
        as the original 'conans.client.build.cmake.CMake' helper, but it will warn the
        user about arguments forbidden, not used,... and how to achieve the same behavior
        with the toolchain.
    """

    def __init__(self, conanfile, generator=None, cmake_system_name=None,
                 parallel=True, build_type=None, toolset=None, make_program=None,
                 set_cmake_flags=None, msbuild_verbosity="minimal", cmake_program=None,
                 generator_platform=None):
        _validate_recipe(conanfile)

        #assert generator is None, "'generator' is handled by the toolchain"
        generator = generator or get_generator(conanfile.settings)
        self._is_multiconfiguration = is_multi_configuration(generator)
        self._build_flags = _compute_build_flags(conanfile, generator, parallel, msbuild_verbosity)
        self.generator = generator  # TODO: I don't want to store the generator here !!!

        assert cmake_system_name is None, "'cmake_system_name' is handled by the toolchain"
        assert toolset is None, "'toolset' is handled by the toolchain"
        assert make_program is None, "'make_program' is handled by the toolchain"
        assert set_cmake_flags is None, "'set_cmake_flags' is handled by the toolchain"
        assert cmake_program is None, "'cmake_program' is handled by the environment"  # FIXME: Not yet
        assert generator_platform is None, "'generator_platform' is handled by the toolchain"

        super(CMakeToolchainBuildHelper, self).__init__(conanfile, parallel, build_type, msbuild_verbosity)
        self._cmake_program = "cmake"  # Path to CMake should be handled by environment

    @property
    def definitions(self):
        raise ConanException("Cannot add 'definitions' to CMake build helper when using a"
                             " toolchain. All the definitions should be added to the toolchain")

    @property
    def runtime(self):
        raise ConanException("Runtime is assigned by the toolchain and it is not known in the"
                             " CMakeToolchainBuildHelper helper")

    @property
    def is_multi_configuration(self):
        return self._is_multiconfiguration

    @property
    def verbose(self):
        raise ConanException("Verbosity is assigned by the toolchain and it is not known in the"
                             " CMakeToolchainBuildHelper helper")

    def _get_install_prefix(self):
        if self._conanfile.package_folder:
            return self._conanfile.package_folder.replace("\\", "/")
        return None

    def configure(self, args=None, defs=None, source_dir=None, build_dir=None,
                  source_folder=None, build_folder=None, cache_build_folder=None,
                  pkg_config_paths=None):
        assert args is None, "All the 'args' should be provided in the toolchain"
        assert defs is None, "All the 'defs' should be provided in the toolchain"
        assert pkg_config_paths is None, "'pkg_config_paths' should be provided in the toolchain"  # TODO: environment?

        # TODO: Deprecate source_dir and build_dir in favor of xxx_folder
        if not self._conanfile.should_configure:
            return

        defs = {"CMAKE_TOOLCHAIN_FILE": CMakeToolchain.filename}
        configure_command = self._configure_command(self._cmake_program, None, defs, source_dir,
                                                    build_dir, source_folder, build_folder,
                                                    cache_build_folder)

        if platform.system() == "Windows" and self.generator == "MinGW Makefiles":  # TODO: Don't know about generator, why this remove?
            with tools.remove_from_path("sh"):
                self._run(configure_command)
        else:
            self._run(configure_command)

    def _build(self, args=None, build_dir=None, target=None):
        assert args is None, "Do not use 'args' here, they won't be handled by the toolchain"

        build_command = self._build_command(self._cmake_program, forward_args=self._build_flags,
                                            args=None, build_dir=build_dir, target=target)
        self._run(build_command)