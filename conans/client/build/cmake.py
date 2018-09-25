import os
import platform
from itertools import chain
import subprocess

from conans import tools
from conans.client import defs_to_string, join_arguments
from conans.client.build.cmake_flags import CMakeDefinitionsBuilder, \
    get_generator, is_multi_configuration, verbose_definition, verbose_definition_name, \
    cmake_install_prefix_var_name, get_toolset, build_type_definition, runtime_definition_var_name, \
    cmake_in_local_cache_var_name, in_local_cache_definition
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.version import Version
from conans.tools import cpu_count, args_to_string
from conans.util.config_parser import get_bool_from_text
from conans.util.files import mkdir, get_abs_path, decode_text


class CMake(object):

    def __init__(self, conanfile, generator=None, cmake_system_name=True,
                 parallel=True, build_type=None, toolset=None, make_program=None,
                 set_cmake_flags=False):
        """
        :param settings_or_conanfile: Conanfile instance (or settings for retro compatibility)
        :param generator: Generator name to use or none to autodetect
        :param cmake_system_name: False to not use CMAKE_SYSTEM_NAME variable,
               True for auto-detect or directly a string with the system name
        :param parallel: Try to build with multiple cores if available
        :param build_type: Overrides default build type comming from settings
        :param toolset: Toolset name to use (such as llvm-vs2014) or none for default one,
                applies only to certain generators (e.g. Visual Studio)
        :param set_cmake_flags: whether or not to set CMake flags like CMAKE_CXX_FLAGS, CMAKE_C_FLAGS, etc.
               it's vital to set for certain projects (e.g. using CMAKE_SIZEOF_VOID_P or CMAKE_LIBRARY_ARCHITECTURE)
        """
        if not isinstance(conanfile, ConanFile):
            raise ConanException("First argument of CMake() has to be ConanFile. Use CMake(self)")

        self._settings = conanfile.settings
        self._conanfile = conanfile

        self.generator = generator or get_generator(self._settings)
        self.toolset = toolset or get_toolset(self._settings)
        self.build_dir = None
        self.parallel = parallel

        self._set_cmake_flags = set_cmake_flags
        self._cmake_system_name = cmake_system_name
        self._make_program = make_program

        # Initialize definitions (won't be updated if conanfile or any of these variables change)
        builder = CMakeDefinitionsBuilder(self._conanfile, cmake_system_name=self._cmake_system_name,
                                          make_program=self._make_program, parallel=self.parallel,
                                          generator=self.generator,
                                          set_cmake_flags=self._set_cmake_flags)
        self.definitions = builder.get_definitions()

        if build_type is None:
            self.build_type = self._settings.get_safe("build_type")
        else:
            self.build_type = build_type

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
            self._conanfile.output.warn(
                'Set CMake build type "%s" is different than the settings build_type "%s"'
                % (build_type, settings_build_type))
        self._build_type = build_type
        self.definitions.update(build_type_definition(self._build_type, self.generator))

    @property
    def flags(self):
        return defs_to_string(self.definitions)

    @property
    def is_multi_configuration(self):
        return is_multi_configuration(self.generator)

    @property
    def command_line(self):
        args = ['-G "%s"' % self.generator] if self.generator else []
        args.append(self.flags)
        args.append('-Wno-dev')

        if self.toolset:
            args.append('-T "%s"' % self.toolset)
        return join_arguments(args)

    @property
    def runtime(self):
        return defs_to_string(self.definitions.get(runtime_definition_var_name))

    @property
    def build_config(self):
        """ cmake --build tool have a --config option for Multi-configuration IDEs
        """
        if self._build_type and self.is_multi_configuration:
            return "--config %s" % self._build_type
        return ""

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
        compiler = self._settings.get_safe("compiler")
        if compiler == 'Visual Studio' and self.generator in ['Ninja', 'NMake Makefiles',
                                                              'NMake Makefiles JOM']:
            with tools.vcvars(self._settings, force=True, filter_known_paths=False):
                self._conanfile.run(command)
        else:
            self._conanfile.run(command)

    def configure(self, args=None, defs=None, source_dir=None, build_dir=None,
                  source_folder=None, build_folder=None, cache_build_folder=None,
                  pkg_config_paths=None):

        # TODO: Deprecate source_dir and build_dir in favor of xxx_folder
        if not self._conanfile.should_configure:
            return
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

        if pkg_config_paths:
            pkg_env = {"PKG_CONFIG_PATH":
                       os.pathsep.join(get_abs_path(f, self._conanfile.install_folder)
                                       for f in pkg_config_paths)}
        else:
            # If we are using pkg_config generator automate the pcs location, otherwise it could
            # read wrong files
            set_env = "pkg_config" in self._conanfile.generators \
                      and "PKG_CONFIG_PATH" not in os.environ
            pkg_env = {"PKG_CONFIG_PATH": self._conanfile.install_folder} if set_env else {}

        with tools.environment_append(pkg_env):
            command = "cd %s && cmake %s" % (args_to_string([self.build_dir]), arg_list)
            if platform.system() == "Windows" and self.generator == "MinGW Makefiles":
                with tools.remove_from_path("sh"):
                    self._conanfile.run(command)
            else:
                self._conanfile.run(command)

    def build(self, args=None, build_dir=None, target=None):
        if not self._conanfile.should_build:
            return
        self._build(args, build_dir, target)

    def _build(self, args=None, build_dir=None, target=None):
        args = args or []
        build_dir = build_dir or self.build_dir or self._conanfile.build_folder
        if target is not None:
            args = ["--target", target] + args

        if self.generator and self.parallel:
            compiler_version = self._settings.get_safe("compiler.version")
            if "Makefiles" in self.generator and "NMake" not in self.generator:
                if "--" not in args:
                    args.append("--")
                args.append("-j%i" % cpu_count())
            elif "Visual Studio" in self.generator and \
                    compiler_version and Version(compiler_version) >= "10":
                if "--" not in args:
                    args.append("--")
                # Parallel for building projects in the solution
                args.append("/m:%i" % cpu_count())

        arg_list = join_arguments([
            args_to_string([build_dir]),
            self.build_config,
            args_to_string(args)
        ])
        command = "cmake --build %s" % arg_list
        self._run(command)

    def install(self, args=None, build_dir=None):
        if not self._conanfile.should_install:
            return
        mkdir(self._conanfile.package_folder)
        if not self.definitions.get(cmake_install_prefix_var_name):
            raise ConanException("%s not defined for 'cmake.install()'\n"
                                 "Make sure 'package_folder' is "
                                 "defined" % cmake_install_prefix_var_name)
        self._build(args=args, build_dir=build_dir, target="install")

    def test(self, args=None, build_dir=None, target=None):
        if not self._conanfile.should_test:
            return
        if not target:
            target = "RUN_TESTS" if self.is_multi_configuration else "test"
        self._build(args=args, build_dir=build_dir, target=target)

    @property
    def verbose(self):
        try:
            verbose = self.definitions[verbose_definition_name]
            return get_bool_from_text(str(verbose))
        except KeyError:
            return False

    @verbose.setter
    def verbose(self, value):
        self.definitions.update(verbose_definition(value))

    @property
    def in_local_cache(self):
        try:
            in_local_cache = self.definitions[cmake_in_local_cache_var_name]
            return get_bool_from_text(str(in_local_cache))
        except KeyError:
            return False

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
        pf = self.definitions.get(cmake_install_prefix_var_name)
        replstr = "${CONAN_%s_ROOT}" % self._conanfile.name.upper()
        allwalk = chain(os.walk(self._conanfile.build_folder), os.walk(self._conanfile.package_folder))
        for root, _, files in allwalk:
            for f in files:
                if f.endswith(".cmake"):
                    path = os.path.join(root, f)
                    tools.replace_in_file(path, pf, replstr, strict=False)

                    # patch paths of dependent packages that are found in any cmake files of the
                    # current package
                    path_content = tools.load(path)
                    for dep in self._conanfile.deps_cpp_info.deps:
                        from_str = self._conanfile.deps_cpp_info[dep].rootpath
                        # try to replace only if from str is found
                        if path_content.find(from_str) != -1:
                            dep_str = "${CONAN_%s_ROOT}" % dep.upper()
                            self._conanfile.output.info("Patching paths for %s: %s to %s" % (dep, from_str, dep_str))
                            tools.replace_in_file(path, from_str, dep_str, strict=False)

    @staticmethod
    def get_version():
        try:
            out, err = subprocess.Popen(["cmake", "--version"], stdout=subprocess.PIPE).communicate()
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.rsplit(' ', 1)[-1]
            return Version(version_str)
        except Exception as e:
            raise ConanException("Error retrieving CMake version: '{}'".format(e))
