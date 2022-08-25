import os

from conan.tools.build import build_jobs
from conan.tools.cmake.presets import load_cmake_presets, get_configure_preset
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.files import chdir, mkdir
from conan.tools.microsoft.msbuild import msbuild_verbosity_cmd_line_arg
from conans.client.tools.oss import args_to_string
from conans.errors import ConanException


def _validate_recipe(conanfile):
    forbidden_generators = ["cmake", "cmake_multi"]
    if any(it in conanfile.generators for it in forbidden_generators):
        raise ConanException("Usage of toolchain is only supported with 'cmake_find_package'"
                             " or 'cmake_find_package_multi' generators")


def _cmake_cmd_line_args(conanfile, generator):
    args = []
    if not generator:
        return args

    # Arguments related to parallel
    njobs = build_jobs(conanfile)
    if njobs and ("Makefiles" in generator or "Ninja" in generator) and "NMake" not in generator:
        args.append("-j{}".format(njobs))

    maxcpucount = conanfile.conf.get("tools.microsoft.msbuild:max_cpu_count", check_type=int)
    if maxcpucount and "Visual Studio" in generator:
        args.append("/m:{}".format(njobs))

    # Arguments for verbosity
    if "Visual Studio" in generator:
        verbosity = msbuild_verbosity_cmd_line_arg(conanfile)
        if verbosity:
            args.append(verbosity)

    return args


class CMake(object):
    """ CMake helper to use together with the toolchain feature. It implements a very simple
    wrapper to call the cmake executable, but without passing compile flags, preprocessor
    definitions... all that is set by the toolchain. Only the generator and the CMAKE_TOOLCHAIN_FILE
    are passed to the command line, plus the ``--config Release`` for builds in multi-config
    """

    def __init__(self, conanfile):
        _validate_recipe(conanfile)

        # Store a reference to useful data
        self._conanfile = conanfile

        cmake_presets = load_cmake_presets(conanfile.generators_folder)
        configure_preset = get_configure_preset(cmake_presets, conanfile)

        self._generator = configure_preset["generator"]
        self._toolchain_file = configure_preset.get("toolchainFile")
        self._cache_variables = configure_preset["cacheVariables"]

        self._cmake_program = "cmake"  # Path to CMake should be handled by environment

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

    def _build(self, build_type=None, target=None, cli_args=None, build_tool_args=None):
        bf = self._conanfile.build_folder
        is_multi = is_multi_configuration(self._generator)
        if build_type and not is_multi:
            self._conanfile.output.error("Don't specify 'build_type' at build time for "
                                         "single-config build systems")

        bt = build_type or self._conanfile.settings.get_safe("build_type")
        if not bt:
            raise ConanException("build_type setting should be defined.")
        build_config = "--config {}".format(bt) if bt and is_multi else ""

        args = []
        if target is not None:
            args = ["--target", target]
        if cli_args:
            args.extend(cli_args)

        cmd_line_args = _cmake_cmd_line_args(self._conanfile, self._generator)
        if build_tool_args:
            cmd_line_args.extend(build_tool_args)
        if cmd_line_args:
            args += ['--'] + cmd_line_args

        arg_list = ['"{}"'.format(bf), build_config, args_to_string(args)]
        arg_list = " ".join(filter(None, arg_list))
        command = "%s --build %s" % (self._cmake_program, arg_list)
        self._conanfile.output.info("CMake command: %s" % command)
        self._conanfile.run(command)

    def build(self, build_type=None, target=None, cli_args=None, build_tool_args=None):
        self._build(build_type, target, cli_args, build_tool_args)

    def install(self, build_type=None):
        mkdir(self._conanfile, self._conanfile.package_folder)

        bt = build_type or self._conanfile.settings.get_safe("build_type")
        if not bt:
            raise ConanException("build_type setting should be defined.")
        is_multi = is_multi_configuration(self._generator)
        build_config = "--config {}".format(bt) if bt and is_multi else ""

        pkg_folder = '"{}"'.format(self._conanfile.package_folder.replace("\\", "/"))
        build_folder = '"{}"'.format(self._conanfile.build_folder)
        arg_list = ["--install", build_folder, build_config, "--prefix", pkg_folder]
        arg_list = " ".join(filter(None, arg_list))
        command = "%s %s" % (self._cmake_program, arg_list)
        self._conanfile.output.info("CMake command: %s" % command)
        self._conanfile.run(command)

    def test(self, build_type=None, target=None, cli_args=None, build_tool_args=None):
        if self._conanfile.conf.get("tools.build:skip_test", check_type=bool):
            return
        if not target:
            is_multi = is_multi_configuration(self._generator)
            is_ninja = "Ninja" in self._generator
            target = "RUN_TESTS" if is_multi and not is_ninja else "test"

        self._build(build_type=build_type, target=target, cli_args=cli_args,
                    build_tool_args=build_tool_args)
