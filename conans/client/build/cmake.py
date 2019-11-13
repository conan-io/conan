import os
import platform

from conans.client import tools
from conans.client.build import defs_to_string, join_arguments
from conans.client.build.base_cmake import BaseCMake, _compute_build_flags
from conans.client.build.cmake_flags import CMakeDefinitionsBuilder, \
    get_generator, is_multi_configuration, verbose_definition, verbose_definition_name, \
    cmake_install_prefix_var_name, get_toolset, build_type_definition, \
    runtime_definition_var_name, get_generator_platform, \
    is_generator_platform_supported, is_toolset_supported
from conans.errors import ConanException
from conans.util.config_parser import get_bool_from_text
from conans.util.files import get_abs_path


class CMake(BaseCMake):

    def __init__(self, conanfile, generator=None, cmake_system_name=True,
                 parallel=True, build_type=None, toolset=None, make_program=None,
                 set_cmake_flags=False, msbuild_verbosity="minimal", cmake_program=None,
                 generator_platform=None):
        """
        :param conanfile: Conanfile instance
        :param generator: Generator name to use or none to autodetect
        :param cmake_system_name: False to not use CMAKE_SYSTEM_NAME variable,
               True for auto-detect or directly a string with the system name
        :param parallel: Try to build with multiple cores if available
        :param build_type: Overrides default build type coming from settings
        :param toolset: Toolset name to use (such as llvm-vs2014) or none for default one,
                applies only to certain generators (e.g. Visual Studio)
        :param set_cmake_flags: whether or not to set CMake flags like CMAKE_CXX_FLAGS,
                CMAKE_C_FLAGS, etc. it's vital to set for certain projects
                (e.g. using CMAKE_SIZEOF_VOID_P or CMAKE_LIBRARY_ARCHITECTURE)
        :param msbuild_verbosity: verbosity level for MSBuild (in case of Visual Studio generator)
        :param cmake_program: Path to the custom cmake executable
        :param generator_platform: Generator platform name or none to autodetect (-A cmake option)
        """
        self.generator = generator or get_generator(conanfile.settings)
        super(CMake, self).__init__(conanfile, parallel, build_type, msbuild_verbosity)

        if not self.generator:
            self._conanfile.output.warn("CMake generator could not be deduced from settings")

        self._cmake_program = os.getenv("CONAN_CMAKE_PROGRAM") or cmake_program or "cmake"
        self.generator_platform = generator_platform or get_generator_platform(conanfile.settings,
                                                                               self.generator)
        # Initialize definitions (won't be updated if conanfile or any of these variables change)
        builder = CMakeDefinitionsBuilder(self._conanfile,
                                          cmake_system_name=cmake_system_name,
                                          make_program=make_program, parallel=parallel,
                                          generator=self.generator,
                                          set_cmake_flags=set_cmake_flags,
                                          output=self._conanfile.output)
        # FIXME CONAN 2.0: CMake() interface should be always the constructor and self.definitions.
        # FIXME CONAN 2.0: Avoid properties and attributes to make the user interface more clear

        self._definitions.update(builder.get_definitions())
        self.toolset = toolset or get_toolset(self._settings)

    @property
    def definitions(self):
        return self._definitions

    @BaseCMake.build_type.setter
    def build_type(self, build_type):
        BaseCMake.build_type.fset(self, build_type)
        self._definitions.pop("CMAKE_BUILD_TYPE", None)
        self._definitions.update(build_type_definition(self._build_type, self.generator))

    @property
    def runtime(self):
        return defs_to_string(self._definitions.get(runtime_definition_var_name))

    @property
    def is_multi_configuration(self):
        return is_multi_configuration(self.generator)

    def _get_install_prefix(self):
        return self._definitions.get(cmake_install_prefix_var_name)

    @property
    def command_line(self):
        args = []
        if self.generator:
            args.append('-G "%s"' % self.generator)

        if self.generator_platform:
            if is_generator_platform_supported(self.generator):
                args.append('-A "%s"' % self.generator_platform)
            else:
                raise ConanException('CMake does not support generator platform with generator '
                                     '"%s:. Please check your conan profile to either remove the '
                                     'generator platform, or change the CMake generator.'
                                     % self.generator)

        cmd_line = super(CMake, self).command_line
        args += [cmd_line, '-Wno-dev']

        if self.toolset:
            if is_toolset_supported(self.generator):
                args.append('-T "%s"' % self.toolset)
            else:
                raise ConanException('CMake does not support toolsets with generator "%s:.'
                                     'Please check your conan profile to either remove the toolset,'
                                     ' or change the CMake generator.' % self.generator)
        return join_arguments(args)

    def _run(self, command):
        compiler = self._settings.get_safe("compiler")
        the_os = self._settings.get_safe("os")
        is_clangcl = the_os == "Windows" and compiler == "clang"
        is_msvc = compiler == "Visual Studio"
        if (is_msvc or is_clangcl) and self.generator in ["Ninja", "NMake Makefiles",
                                                          "NMake Makefiles JOM"]:
            with tools.vcvars(self._settings, force=True, filter_known_paths=False,
                              output=self._conanfile.output):
                super(CMake, self)._run(command)
        else:
            super(CMake, self)._run(command)

    def configure(self, args=None, defs=None, source_dir=None, build_dir=None,
                  source_folder=None, build_folder=None, cache_build_folder=None,
                  pkg_config_paths=None):
        # TODO: Deprecate source_dir and build_dir in favor of xxx_folder
        if not self._conanfile.should_configure:
            return

        configure_command = self._configure_command(self._cmake_program, args, defs, source_dir,
                                                    build_dir, source_folder, build_folder,
                                                    cache_build_folder)

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
            if platform.system() == "Windows" and self.generator == "MinGW Makefiles":
                with tools.remove_from_path("sh"):
                    self._run(configure_command)
            else:
                self._run(configure_command)

    def _build(self, args=None, build_dir=None, target=None):
        # Compute forward_args each time, user can change attributes
        forward_args = _compute_build_flags(self._conanfile, self.generator,
                                            self.parallel, self.msbuild_verbosity)
        build_command = self._build_command(self._cmake_program, forward_args=forward_args,
                                            args=args, build_dir=build_dir, target=target)
        self._run(build_command)

    def install(self, args=None, build_dir=None):
        if not self._conanfile.should_install:
            return

        if not self._get_install_prefix():
            raise ConanException("%s not defined for 'cmake.install()'\n"
                                 "Make sure 'package_folder' is "
                                 "defined" % self._get_install_prefix())
        super(CMake, self).install(args=args, build_dir=build_dir)

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
