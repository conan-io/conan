import os
import platform
import subprocess
from itertools import chain

from six import StringIO  # Python 2 and 3 compatible

from conans.client import tools
from conans.client.build import defs_to_string, join_arguments
from conans.client.build.cmake_flags import cmake_in_local_cache_var_name
from conans.client.build.cmake_flags import in_local_cache_definition
from conans.client.build.cmake_flags import is_multi_configuration, get_generator
from conans.client.output import ConanOutput
from conans.client.toolchain.cmake import CMakeToolchain
from conans.client.tools.oss import cpu_count, args_to_string
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.version import Version
from conans.util.config_parser import get_bool_from_text
from conans.util.files import mkdir, walk, decode_text


def _validate_recipe(conanfile):
    # Toolchain is required to use the CMakeToolchainBuildHelper
    toolchain_method = getattr(conanfile, "toolchain", None)
    if not toolchain_method or not callable(toolchain_method):
        raise ConanException("Using 'CMakeToolchainBuildHelper' helper, requires 'toolchain()' method"
                             " to be defined.")

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


class CMakeToolchainBuildHelper(object):
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

        # Store a reference to useful data
        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._build_type = build_type or conanfile.settings.get_safe("build_type")
        self.parallel = parallel
        self.msbuild_verbosity = os.getenv("CONAN_MSBUILD_VERBOSITY") or msbuild_verbosity
        self.build_dir = None

        self._definitions = {"CONAN_EXPORTED": "1"}
        self._definitions.update(in_local_cache_definition(self._conanfile.in_local_cache))

        self.build_type = self._build_type

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
        settings_build_type = self._settings.get_safe("build_type")
        if build_type != settings_build_type:
            self._conanfile.output.warn("Forced CMake build type ('%s') different from the settings"
                                        " build type ('%s')" % (build_type, settings_build_type))
        self._build_type = build_type

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
        raise ConanException("Verbosity is assigned by the toolchain and it is not known in the"
                             " CMakeToolchainBuildHelper helper")

    def _get_dirs(self, source_folder, build_folder, source_dir, build_dir, cache_build_folder):
        if (source_folder or build_folder) and (source_dir or build_dir):
            raise ConanException("Use 'build_folder'/'source_folder' arguments")

        def get_dir(folder, origin):
            if folder:
                if os.path.isabs(folder):
                    return folder
                return os.path.join(origin, folder)
            return origin

        if source_dir or build_dir:  # OLD MODE
            build_ret = build_dir or self.build_dir or self._conanfile.build_folder
            source_ret = source_dir or self._conanfile.source_folder
        else:
            build_ret = get_dir(build_folder, self._conanfile.build_folder)
            source_ret = get_dir(source_folder, self._conanfile.source_folder)

        if self._conanfile.in_local_cache and cache_build_folder:
            build_ret = get_dir(cache_build_folder, self._conanfile.build_folder)

        return source_ret, build_ret

    def _run(self, command):
        self._conanfile.run(command)

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

    def _configure_command(self, cmake_program, args=None, defs=None, source_dir=None,
                           build_dir=None, source_folder=None, build_folder=None,
                           cache_build_folder=None):
        args = args or []
        defs = defs or {}
        source_dir, self.build_dir = self._get_dirs(source_folder, build_folder,
                                                    source_dir, build_dir,
                                                    cache_build_folder)
        mkdir(self.build_dir)
        arg_list = join_arguments([
            self.command_line,
            args_to_string(args),
            defs_to_string(defs),
            args_to_string([source_dir])
        ])

        command = "cd %s && %s %s" % (args_to_string([self.build_dir]), cmake_program, arg_list)
        return command

    def _build_command(self, cmake_program, forward_args, args=None, build_dir=None, target=None):
        args = args or []
        build_dir = build_dir or self.build_dir or self._conanfile.build_folder
        if target is not None:
            args = ["--target", target] + args

        if forward_args:
            if '--' not in args:
                args.append('--')
            args += forward_args

        arg_list = [args_to_string([build_dir]), self.build_config, args_to_string(args)]
        command = "%s --build %s" % (cmake_program, join_arguments(arg_list))
        return command

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

    def patch_config_paths(self):
        """
        changes references to the absolute path of the installed package and its dependencies in
        exported cmake config files to the appropriate conan variable. This makes
        most (sensible) cmake config files portable.
        For example, if a package foo installs a file called "fooConfig.cmake" to
        be used by cmake's find_package method, normally this file will contain
        absolute paths to the installed package folder, for example it will contain
        a line such as:
            SET(Foo_INSTALL_DIR /home/developer/.conan/data/Foo/1.0.0/...)
        This will cause cmake find_package() method to fail when someone else
        installs the package via conan.
        This function will replace such mentions to
            SET(Foo_INSTALL_DIR ${CONAN_FOO_ROOT})
        which is a variable that is set by conanbuildinfo.cmake, so that find_package()
        now correctly works on this conan package.
        For dependent packages, if a package foo installs a file called "fooConfig.cmake" to
        be used by cmake's find_package method and if it depends to a package bar,
        normally this file will contain absolute paths to the bar package folder,
        for example it will contain a line such as:
            SET_TARGET_PROPERTIES(foo PROPERTIES
                  INTERFACE_INCLUDE_DIRECTORIES
                  "/home/developer/.conan/data/Bar/1.0.0/user/channel/id/include")
        This function will replace such mentions to
            SET_TARGET_PROPERTIES(foo PROPERTIES
                  INTERFACE_INCLUDE_DIRECTORIES
                  "${CONAN_BAR_ROOT}/include")
        If the install() method of the CMake object in the conan file is used, this
        function should be called _after_ that invocation. For example:
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                cmake.install()
                cmake.patch_config_paths()
        """

        if not self._conanfile.should_install:
            return
        if not self._conanfile.name:
            raise ConanException("cmake.patch_config_paths() can't work without package name. "
                                 "Define name in your recipe")
        pf = self._get_install_prefix()
        replstr = "${CONAN_%s_ROOT}" % self._conanfile.name.upper()
        allwalk = chain(walk(self._conanfile.build_folder), walk(self._conanfile.package_folder))

        # We don't want warnings printed because there is no replacement of the abs path.
        # there could be MANY cmake files in the package and the normal thing is to not find
        # the abs paths
        _null_out = ConanOutput(StringIO())
        for root, _, files in allwalk:
            for f in files:
                if f.endswith(".cmake") and not f.startswith("conan"):
                    path = os.path.join(root, f)

                    tools.replace_path_in_file(path, pf, replstr, strict=False,
                                               output=_null_out)

                    # patch paths of dependent packages that are found in any cmake files of the
                    # current package
                    for dep in self._conanfile.deps_cpp_info.deps:
                        from_str = self._conanfile.deps_cpp_info[dep].rootpath
                        dep_str = "${CONAN_%s_ROOT}" % dep.upper()
                        ret = tools.replace_path_in_file(path, from_str, dep_str, strict=False,
                                                         output=_null_out)
                        if ret:
                            self._conanfile.output.info("Patched paths for %s: %s to %s"
                                                        % (dep, from_str, dep_str))

    @staticmethod
    def get_version():
        try:
            out, _ = subprocess.Popen(["cmake", "--version"], stdout=subprocess.PIPE).communicate()
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.rsplit(' ', 1)[-1]
            return Version(version_str)
        except Exception as e:
            raise ConanException("Error retrieving CMake version: '{}'".format(e))