import os
import platform

from conans.client import tools
from conans.client.build import join_arguments
from conans.client.build.cmake_flags import is_multi_configuration
from conan.tools.cmake.base import CMakeToolchainBase
from conans.client.tools.files import chdir
from conans.client.tools.oss import cpu_count, args_to_string, get_cross_building_settings
from conans.errors import ConanException
from conans.model.version import Version
from conans.util.conan_v2_mode import conan_v2_behavior
from conans.util.files import mkdir
from conans.util.log import logger


def get_generator(conanfile):
    # Returns the name of the generator to be used by CMake
    # TODO: Provide a way to configure the generator from config
    if "CONAN_CMAKE_GENERATOR" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR"]

    compiler = conanfile.settings.get_safe("compiler")
    if compiler == "msvc":
        toolset = conanfile.settings.get_safe("compiler.toolset")
        _visuals = {'140': '14 2015',
                    '141': '15 2017',
                    '142': '16 2019'}[toolset]
        base = "Visual Studio %s" % _visuals
        return base

    compiler_base = conanfile.settings.get_safe("compiler.base")
    arch = conanfile.settings.get_safe("arch")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    compiler_base_version = conanfile.settings.get_safe("compiler.base.version")
    os_build, _, _, _ = get_cross_building_settings(conanfile)

    if not compiler or not compiler_version or not arch:
        if os_build == "Windows":
            logger.warning("CMake generator could not be deduced from settings")
            return None
        return "Unix Makefiles"

    if compiler == "Visual Studio" or compiler_base == "Visual Studio":
        version = compiler_base_version or compiler_version
        _visuals = {'8': '8 2005',
                    '9': '9 2008',
                    '10': '10 2010',
                    '11': '11 2012',
                    '12': '12 2013',
                    '14': '14 2015',
                    '15': '15 2017',
                    '16': '16 2019'}.get(version, "UnknownVersion %s" % version)
        base = "Visual Studio %s" % _visuals
        return base

    # The generator depends on the build machine, not the target
    if os_build == "Windows" and compiler != "qcc":
        return "MinGW Makefiles"  # it is valid only under Windows

    return "Unix Makefiles"


def _validate_recipe(conanfile):
    forbidden_generators = ["cmake", "cmake_multi", "cmake_paths"]
    if any(it in conanfile.generators for it in forbidden_generators):
        raise ConanException("Usage of toolchain is only supported with 'cmake_find_package'"
                             " or 'cmake_find_package_multi' generators")


def _cmake_cmd_line_args(conanfile, generator, parallel, msbuild_verbosity):
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


class CMake(object):
    """ CMake helper to use together with the toolchain feature. It implements a very simple
    wrapper to call the cmake executable, but without passing compile flags, preprocessor
    definitions... all that is set by the toolchain. Only the generator and the CMAKE_TOOLCHAIN_FILE
    are passed to the command line, plus the ``--config Release`` for builds in multi-config
    """

    def __init__(self, conanfile, generator=None, build_folder=None, parallel=True,
                 msbuild_verbosity="minimal"):

        _validate_recipe(conanfile)

        # assert generator is None, "'generator' is handled by the toolchain"
        self._generator = generator or get_generator(conanfile)
        self._is_multiconfiguration = is_multi_configuration(self._generator)

        # Store a reference to useful data
        self._conanfile = conanfile
        self._parallel = parallel
        self._msbuild_verbosity = msbuild_verbosity

        self._build_folder = build_folder
        self._cmake_program = "cmake"  # Path to CMake should be handled by environment

    def configure(self, source_folder=None):
        # TODO: environment?
        if not self._conanfile.should_configure:
            return

        source = self._conanfile.source_folder
        if source_folder:
            source = os.path.join(self._conanfile.source_folder, source_folder)

        build_folder = self._conanfile.build_folder
        if self._build_folder:
            build_folder = os.path.join(self._conanfile.build_folder, self._build_folder)

        mkdir(build_folder)
        arg_list = '-DCMAKE_TOOLCHAIN_FILE="{}" -DCMAKE_INSTALL_PREFIX="{}" "{}"'.format(
            CMakeToolchainBase.filename,
            self._conanfile.package_folder.replace("\\", "/"),
            source)

        generator = '-G "{}" '.format(self._generator) if self._generator else ""
        command = "%s %s%s" % (self._cmake_program, generator, arg_list)

        is_windows_mingw = platform.system() == "Windows" and self._generator == "MinGW Makefiles"
        self._conanfile.output.info("CMake command: %s" % command)
        with chdir(build_folder):
            if is_windows_mingw:
                with tools.remove_from_path("sh"):
                    self._conanfile.run(command)
            else:
                self._conanfile.run(command)

    def _build(self, build_type=None, target=None):
        bf = self._conanfile.build_folder
        if self._build_folder:
            bf = os.path.join(self._conanfile.build_folder, self._build_folder)

        if build_type and not self._is_multiconfiguration:
            self._conanfile.output.error("Don't specify 'build_type' at build time for "
                                         "single-config build systems")

        bt = build_type or self._conanfile.settings.get_safe("build_type")
        if not bt:
            conan_v2_behavior("build_type setting should be defined.",
                              v1_behavior=self._conanfile.output.warn)

        if bt and self._is_multiconfiguration:
            build_config = "--config %s" % bt
        else:
            build_config = ""

        args = []
        if target is not None:
            args = ["--target", target]

        cmd_line_args = _cmake_cmd_line_args(self._conanfile, self._generator, self._parallel,
                                             self._msbuild_verbosity)
        if cmd_line_args:
            args += ['--'] + cmd_line_args

        arg_list = [args_to_string([bf]), build_config, args_to_string(args)]
        command = "%s --build %s" % (self._cmake_program, join_arguments(arg_list))
        self._conanfile.output.info("CMake command: %s" % command)
        self._conanfile.run(command)

    def build(self, build_type=None, target=None):
        if not self._conanfile.should_build:
            return
        self._build(build_type, target)

    def install(self, build_type=None):
        if not self._conanfile.should_install:
            return
        mkdir(self._conanfile.package_folder)
        self._build(build_type=build_type, target="install")

    def test(self, build_type=None, target=None, output_on_failure=False):
        if not self._conanfile.should_test:
            return
        if not target:
            target = "RUN_TESTS" if self._is_multiconfiguration else "test"

        env = {'CTEST_OUTPUT_ON_FAILURE': '1' if output_on_failure else '0'}
        if self._parallel:
            env['CTEST_PARALLEL_LEVEL'] = str(cpu_count(self._conanfile.output))
        with tools.environment_append(env):
            self._build(build_type=build_type, target=target)
