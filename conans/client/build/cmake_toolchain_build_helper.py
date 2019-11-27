import os
import platform

from conans.client import tools
from conans.client.build import defs_to_string, join_arguments
from conans.client.build.cmake import BaseCMakeHelper
from conans.client.build.cmake_flags import cmake_in_local_cache_var_name
from conans.client.build.cmake_flags import in_local_cache_definition
from conans.client.build.cmake_flags import is_multi_configuration, get_generator, \
    verbose_definition, verbose_definition_name
from conans.client.toolchain.cmake import CMakeToolchain
from conans.client.tools.oss import cpu_count, args_to_string
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.version import Version
from conans.util.config_parser import get_bool_from_text
from conans.util.files import mkdir


def _validate_recipe(conanfile):
    # Toolchain is required to use the CMakeToolchainBuildHelper
    toolchain_method = getattr(conanfile, "toolchain", None)
    if not toolchain_method or not callable(toolchain_method):
        raise ConanException("Using 'CMakeToolchainBuildHelper' helper, requires 'toolchain()'"
                             " method to be defined.")

    return  # TODO: I do want to check this, but then I'd need to rewrite some tests :S
    forbidden_generators = ["cmake", "cmake_multi", "cmake_paths"]
    if any(it in conanfile.generators for it in forbidden_generators):
        raise ConanException("Usage of toolchain is only supported with 'cmake_find_package'"
                             " or 'cmake_find_package_multi' generators")


def _compute_build_flags(conanfile, generator, parallel, msbuild_verbosity):
    args = []
    compiler_version = conanfile.settings.get_safe("compiler.version")
    if generator and parallel:
        if ("Makefiles" in generator or "Ninja" in generator) and "NMake" not in generator:
            args.append("-j%i" % cpu_count(conanfile.output))
        elif "Visual Studio" in generator and compiler_version and Version(compiler_version) >= "10":
            # Parallel for building projects in the solution
            args.append("/m:%i" % cpu_count(output=conanfile.output))

    if generator and msbuild_verbosity:
        if "Visual Studio" in generator and compiler_version and Version(compiler_version) >= "10":
            args.append("/verbosity:%s" % msbuild_verbosity)

    return args


class CMakeToolchainBuildHelper(BaseCMakeHelper):
    """ CMake helper to use together with the toolchain feature, it has the same interface
        as the original 'conans.client.build.cmake.CMake' helper, but it will warn the
        user about arguments forbidden, not used,... and how to achieve the same behavior
        with the toolchain.
    """

    def __init__(self, conanfile, generator=None, cmake_system_name=None,
                 parallel=True, build_type=None, toolset=None, make_program=None,
                 set_cmake_flags=None, msbuild_verbosity="minimal", cmake_program=None,
                 generator_platform=None):
        if not isinstance(conanfile, ConanFile):
            raise ConanException("First argument of CMake() has to be ConanFile. Use CMake(self)")
        _validate_recipe(conanfile)

        # assert generator is None, "'generator' is handled by the toolchain"
        generator = generator or get_generator(conanfile.settings)
        self._is_multiconfiguration = is_multi_configuration(generator)
        self._build_flags = _compute_build_flags(conanfile, generator, parallel, msbuild_verbosity)
        self._is_windows_mingw = platform.system() == "Windows" and generator == "MinGW Makefiles"

        assert cmake_system_name is None, "'cmake_system_name' is handled by the toolchain"
        assert toolset is None, "'toolset' is handled by the toolchain"
        assert make_program is None, "'make_program' is handled by the toolchain"
        assert set_cmake_flags is None, "'set_cmake_flags' is handled by the toolchain"
        assert cmake_program is None, "'cmake_program' handled by the environment"  # FIXME: Not yet
        assert generator_platform is None, "'generator_platform' is handled by the toolchain"
        if not self._is_multiconfiguration:
            assert build_type is None, "'build_type' is handled by the toolchain" \
                                       " in not-multi_config generators"

        # Store a reference to useful data
        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._build_type = build_type or conanfile.settings.get_safe("build_type")
        self.parallel = parallel
        self.msbuild_verbosity = os.getenv("CONAN_MSBUILD_VERBOSITY") or msbuild_verbosity
        self.build_dir = None

        self._definitions = {"CONAN_EXPORTED": "1"}
        self._definitions.update(in_local_cache_definition(self._conanfile.in_local_cache))

        self._cmake_program = "cmake"  # Path to CMake should be handled by environment

    @property
    def build_folder(self):
        return self.build_dir

    @build_folder.setter
    def build_folder(self, value):
        self.build_dir = value

    @property
    def build_type(self):
        return self._build_type

    @build_type.setter
    def build_type(self, build_type):
        raise ConanException("Cannot change 'build_type' to CMake build helper when using a"
                             " toolchain. Assign it in the constructor or let Conan use the"
                             " one declared in the settings")

    @property
    def in_local_cache(self):
        try:
            in_local_cache = self._definitions[cmake_in_local_cache_var_name]
            return get_bool_from_text(str(in_local_cache))
        except KeyError:
            return False

    @property
    def flags(self):
        return defs_to_string(self._definitions)

    @property
    def command_line(self):
        return self.flags

    @property
    def build_config(self):
        """ cmake --build tool have a --config option for Multi-configuration IDEs
        """
        if self._build_type and self.is_multi_configuration:
            return "--config %s" % self._build_type
        return ""

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
        try:
            verbose = self._definitions[verbose_definition_name]
            return get_bool_from_text(str(verbose))
        except KeyError:
            return False

    @verbose.setter
    def verbose(self, value):
        self._definitions.update(verbose_definition(value))

    def _get_dirs(self, source_folder, build_folder, cache_build_folder):

        def get_dir(folder, origin):
            if folder:
                return os.path.join(origin, folder)
            return origin

        build_ret = get_dir(build_folder, self._conanfile.build_folder)
        source_ret = get_dir(source_folder, self._conanfile.source_folder)

        if self._conanfile.in_local_cache and cache_build_folder:
            build_ret = get_dir(cache_build_folder, self._conanfile.build_folder)

        return source_ret, build_ret

    def configure(self, args=None, defs=None, source_dir=None, build_dir=None,
                  source_folder=None, build_folder=None, cache_build_folder=None,
                  pkg_config_paths=None):
        assert args is None, "All the 'args' should be provided in the toolchain"
        assert defs is None, "All the 'defs' should be provided in the toolchain"
        assert source_dir is None, "'source_dir' is deprecated. Use 'source_folder'"
        assert build_dir is None, "'build_dir' is deprecated. Use 'source_folder'"
        assert pkg_config_paths is None, "'pkg_config_paths' should be provided in the toolchain"  # TODO: environment?

        if not self._conanfile.should_configure:
            return

        defs = {"CMAKE_TOOLCHAIN_FILE": CMakeToolchain.filename}
        configure_command = self._configure_command(defs, source_folder, build_folder,
                                                    cache_build_folder)

        if self._is_windows_mingw:
            with tools.remove_from_path("sh"):
                self._conanfile.run(configure_command)
        else:
            self._conanfile.run(configure_command)

    def _configure_command(self, defs, source_folder=None, build_folder=None,
                           cache_build_folder=None):
        source_dir, self.build_dir = self._get_dirs(source_folder, build_folder, cache_build_folder)
        mkdir(self.build_dir)
        arg_list = join_arguments([
            self.command_line,
            defs_to_string(defs),
            args_to_string([source_dir])
        ])

        command = "cd %s && %s %s" % (args_to_string([self.build_dir]),
                                      self._cmake_program, arg_list)
        return command

    def _build(self, args=None, build_dir=None, target=None):
        assert args is None, "Do not use 'args' here, they won't be handled by the toolchain"

        build_dir = build_dir or self.build_dir or self._conanfile.build_folder

        args = []
        if target is not None:
            args = ["--target", target]

        if self._build_flags:
            args += ['--'] + self._build_flags

        arg_list = [args_to_string([build_dir]), self.build_config, args_to_string(args)]
        command = "%s --build %s" % (self._cmake_program, join_arguments(arg_list))
        self._conanfile.run(command)

    def build(self, args=None, build_dir=None, target=None):
        if not self._conanfile.should_build:
            return
        self._build(args, build_dir, target)

    def install(self, args=None, build_dir=None):
        if not self._conanfile.should_install:
            return
        mkdir(self._conanfile.package_folder)
        self._build(args=args, build_dir=build_dir, target="install")

    def test(self, args=None, build_dir=None, target=None, output_on_failure=False):
        if not self._conanfile.should_test:
            return
        if not target:
            target = "RUN_TESTS" if self.is_multi_configuration else "test"

        env = {'CTEST_OUTPUT_ON_FAILURE': '1' if output_on_failure else '0'}
        if self.parallel:
            env['CTEST_PARALLEL_LEVEL'] = str(cpu_count(self._conanfile.output))
        with tools.environment_append(env):
            self._build(args=args, build_dir=build_dir, target=target)

    def _get_install_prefix(self):
        if self._conanfile.package_folder:
            return self._conanfile.package_folder.replace("\\", "/")
        return None

    def patch_config_paths(self):
        pf = None
        if self._conanfile.package_folder:
            pf = self._conanfile.package_folder.replace("\\", "/")

        return super(CMakeToolchainBuildHelper, self)._patch_config_paths(package_folder=pf)
