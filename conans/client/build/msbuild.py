import copy
import os
import re

from conans.client import tools
from conans.client.build.visual_environment import (VisualStudioBuildEnvironment,
                                                    vs_build_type_flags, vs_std_cpp)
from conans.client.toolchain.msbuild import MSBuildCmd
from conans.client.tools.env import environment_append, no_op
from conans.client.tools.intel import intel_compilervars
from conans.client.tools.oss import cpu_count
from conans.client.tools.win import vcvars_command
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.version import Version
from conans.tools import vcvars_command as tools_vcvars_command
from conans.util.env_reader import get_env
from conans.util.files import decode_text, save
from conans.util.runners import version_runner


class MSBuild(object):
    def __new__(cls, conanfile, *args, **kwargs):
        """ Inject the proper MSBuild base class in the hierarchy """

        # If already injected, create and return
        if MSBuildHelper in cls.__bases__ or MSBuildCmd in cls.__bases__:
            return super(MSBuild, cls).__new__(cls)

        # If not, add the proper CMake implementation
        if hasattr(conanfile, "toolchain"):
            msbuild_class = type("CustomMSBuildClass", (cls, MSBuildCmd), {})
        else:
            msbuild_class = type("CustomMSBuildClass", (cls, MSBuildHelper), {})

        return msbuild_class.__new__(msbuild_class, conanfile, *args, **kwargs)

    @staticmethod
    def get_version(settings):
        return MSBuildHelper.get_version(settings)


class MSBuildHelper(object):

    def __init__(self, conanfile):
        if isinstance(conanfile, ConanFile):
            self._conanfile = conanfile
            self._settings = self._conanfile.settings
            self._output = self._conanfile.output
            self.build_env = VisualStudioBuildEnvironment(self._conanfile,
                                                          with_build_type_flags=False)
        else:  # backwards compatible with build_sln_command
            self._settings = conanfile
            self.build_env = None

    def build(self, project_file, targets=None, upgrade_project=True, build_type=None, arch=None,
              parallel=True, force_vcvars=False, toolset=None, platforms=None, use_env=True,
              vcvars_ver=None, winsdk_version=None, properties=None, output_binary_log=None,
              property_file_name=None, verbosity=None, definitions=None,
              user_property_file_name=None):
        """
        :param project_file: Path to the .sln file.
        :param targets: List of targets to build.
        :param upgrade_project: Will call devenv to upgrade the solution to your
        current Visual Studio.
        :param build_type: Use a custom build type instead of the default settings.build_type one.
        :param arch: Use a custom architecture name instead of the settings.arch one.
        It will be used to build the /p:Configuration= parameter of MSBuild.
        It can be used as the key of the platforms parameter.
        E.g. arch="x86", platforms={"x86": "i386"}
        :param parallel: Will use the configured number of cores in the conan.conf file or
        tools.cpu_count():
        In the solution: Building the solution with the projects in parallel. (/m: parameter).
        CL compiler: Building the sources in parallel. (/MP: compiler flag)
        :param force_vcvars: Will ignore if the environment is already set for a different
        Visual Studio version.
        :param toolset: Specify a toolset. Will append a /p:PlatformToolset option.
        :param platforms: Dictionary with the mapping of archs/platforms from Conan naming to
        another one. It is useful for Visual Studio solutions that have a different naming in
        architectures.
        Example: platforms={"x86":"Win32"} (Visual solution uses "Win32" instead of "x86").
        This dictionary will update the default one:
        msvc_arch = {'x86': 'x86', 'x86_64': 'x64', 'armv7': 'ARM', 'armv8': 'ARM64'}
        :param use_env: Applies the argument /p:UseEnv=true to the MSBuild call.
        :param vcvars_ver: Specifies the Visual Studio compiler toolset to use.
        :param winsdk_version: Specifies the version of the Windows SDK to use.
        :param properties: Dictionary with new properties, for each element in the dictionary
        {name: value} it will append a /p:name="value" option.
        :param output_binary_log: If set to True then MSBuild will output a binary log file
        called msbuild.binlog in the working directory. It can also be used to set the name of
        log file like this output_binary_log="my_log.binlog".
        This parameter is only supported starting from MSBuild version 15.3 and onwards.
        :param property_file_name: When None it will generate a file named conan_build.props.
        You can specify a different name for the generated properties file.
        :param verbosity: Specifies verbosity level (/verbosity: parameter)
        :param definitions: Dictionary with additional compiler definitions to be applied during
        the build. Use value of None to set compiler definition with no value.
        :param user_property_file_name: Specify a user provided .props file with custom definitions
        :return: status code of the MSBuild command invocation
        """
        property_file_name = property_file_name or "conan_build.props"
        self.build_env.parallel = parallel

        with environment_append(self.build_env.vars):
            # Path for custom properties file
            props_file_contents = self._get_props_file_contents(definitions)
            property_file_name = os.path.abspath(property_file_name)
            save(property_file_name, props_file_contents)
            vcvars = vcvars_command(self._conanfile.settings, arch=arch, force=force_vcvars,
                                    vcvars_ver=vcvars_ver, winsdk_version=winsdk_version,
                                    output=self._output)
            command = self.get_command(project_file, property_file_name,
                                       targets=targets, upgrade_project=upgrade_project,
                                       build_type=build_type, arch=arch, parallel=parallel,
                                       toolset=toolset, platforms=platforms,
                                       use_env=use_env, properties=properties,
                                       output_binary_log=output_binary_log,
                                       verbosity=verbosity,
                                       user_property_file_name=user_property_file_name)
            command = "%s && %s" % (vcvars, command)
            context = no_op()
            if self._conanfile.settings.get_safe("compiler") == "Intel" and \
                self._conanfile.settings.get_safe("compiler.base") == "Visual Studio":
                context = intel_compilervars(self._conanfile.settings, arch)
            with context:
                return self._conanfile.run(command)

    def get_command(self, project_file, props_file_path=None, targets=None, upgrade_project=True,
                    build_type=None, arch=None, parallel=True, toolset=None, platforms=None,
                    use_env=False, properties=None, output_binary_log=None, verbosity=None,
                    user_property_file_name=None):

        targets = targets or []
        if not isinstance(targets, (list, tuple)):
            raise TypeError("targets argument should be a list")
        properties = properties or {}
        command = []

        if upgrade_project and not get_env("CONAN_SKIP_VS_PROJECTS_UPGRADE", False):
            command.append('devenv "%s" /upgrade &&' % project_file)
        else:
            self._output.info("Skipped sln project upgrade")

        build_type = build_type or self._settings.get_safe("build_type")
        arch = arch or self._settings.get_safe("arch")
        if toolset is None:  # False value to skip adjusting
            toolset = tools.msvs_toolset(self._settings)
        verbosity = os.getenv("CONAN_MSBUILD_VERBOSITY") or verbosity or "minimal"
        if not build_type:
            raise ConanException("Cannot build_sln_command, build_type not defined")
        if not arch:
            raise ConanException("Cannot build_sln_command, arch not defined")

        command.append('msbuild "%s" /p:Configuration="%s"' % (project_file, build_type))
        msvc_arch = {'x86': 'x86',
                     'x86_64': 'x64',
                     'armv7': 'ARM',
                     'armv8': 'ARM64'}
        if platforms:
            msvc_arch.update(platforms)
        msvc_arch = msvc_arch.get(str(arch))
        if self._settings.get_safe("os") == "WindowsCE":
            msvc_arch = self._settings.get_safe("os.platform")
        try:
            sln = tools.load(project_file)
            pattern = re.compile(r"GlobalSection\(SolutionConfigurationPlatforms\)"
                                 r"(.*?)EndGlobalSection", re.DOTALL)
            solution_global = pattern.search(sln).group(1)
            lines = solution_global.splitlines()
            lines = [s.split("=")[0].strip() for s in lines]
        except Exception:
            pass  # TODO: !!! what are we catching here? tools.load? .group(1)? .splitlines?
        else:
            config = "%s|%s" % (build_type, msvc_arch)
            if config not in "".join(lines):
                self._output.warn("***** The configuration %s does not exist in this solution *****"
                                  % config)
                self._output.warn("Use 'platforms' argument to define your architectures")

        if output_binary_log:
            msbuild_version = MSBuildHelper.get_version(self._settings)
            if msbuild_version >= "15.3":  # http://msbuildlog.com/
                command.append('/bl' if isinstance(output_binary_log, bool)
                               else '/bl:"%s"' % output_binary_log)
            else:
                raise ConanException("MSBuild version detected (%s) does not support "
                                     "'output_binary_log' ('/bl')" % msbuild_version)

        if use_env:
            command.append('/p:UseEnv=true')
        else:
            command.append('/p:UseEnv=false')

        if msvc_arch:
            command.append('/p:Platform="%s"' % msvc_arch)

        if parallel:
            command.append('/m:%s' % cpu_count(output=self._output))

        if targets:
            command.append("/target:%s" % ";".join(targets))

        if toolset:
            command.append('/p:PlatformToolset="%s"' % toolset)

        if verbosity:
            command.append('/verbosity:%s' % verbosity)

        if props_file_path or user_property_file_name:
            paths = [os.path.abspath(props_file_path)] if props_file_path else []
            if isinstance(user_property_file_name, list):
                paths.extend([os.path.abspath(p) for p in user_property_file_name])
            elif user_property_file_name:
                paths.append(os.path.abspath(user_property_file_name))
            paths = ";".join(paths)
            command.append('/p:ForceImportBeforeCppTargets="%s"' % paths)

        for name, value in properties.items():
            command.append('/p:%s="%s"' % (name, value))

        return " ".join(command)

    def _get_props_file_contents(self, definitions=None):
        def format_macro(name, value):
            return "%s=%s" % (name, value) if value is not None else name
        # how to specify runtime in command line:
        # https://stackoverflow.com/questions/38840332/msbuild-overrides-properties-while-building-vc-project
        runtime_library = {"MT": "MultiThreaded",
                           "MTd": "MultiThreadedDebug",
                           "MD": "MultiThreadedDLL",
                           "MDd": "MultiThreadedDebugDLL"}.get(
                               self._settings.get_safe("compiler.runtime"), "")

        if self.build_env:
            # Take the flags from the build env, the user was able to alter them if needed
            flags = copy.copy(self.build_env.flags)
            flags.append(self.build_env.std)
        else:  # To be removed when build_sln_command is deprecated
            flags = vs_build_type_flags(self._settings, with_flags=False)
            flags.append(vs_std_cpp(self._settings))

        if definitions:
            definitions = ";".join([format_macro(name, definitions[name]) for name in definitions])

        flags_str = " ".join(list(filter(None, flags)))  # Removes empty and None elements
        additional_node = "<AdditionalOptions>" \
                          "{} %(AdditionalOptions)" \
                          "</AdditionalOptions>".format(flags_str) if flags_str else ""
        runtime_node = "<RuntimeLibrary>" \
                       "{}" \
                       "</RuntimeLibrary>".format(runtime_library) if runtime_library else ""
        definitions_node = "<PreprocessorDefinitions>" \
                           "{};%(PreprocessorDefinitions)" \
                           "</PreprocessorDefinitions>".format(definitions) if definitions else ""
        template = """<?xml version="1.0" encoding="utf-8"?>
<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemDefinitionGroup>
    <ClCompile>
      {runtime_node}
      {additional_node}
      {definitions_node}
    </ClCompile>
  </ItemDefinitionGroup>
</Project>""".format(**{"runtime_node": runtime_node,
                        "additional_node": additional_node,
                        "definitions_node": definitions_node})
        return template

    @staticmethod
    def get_version(settings):
        msbuild_cmd = "msbuild -version"
        vcvars = tools_vcvars_command(settings)
        command = "%s && %s" % (vcvars, msbuild_cmd)
        try:
            out = version_runner(command, shell=True)
            version_line = decode_text(out).split("\n")[-1]
            prog = re.compile("(\d+\.){2,3}\d+")
            result = prog.match(version_line).group()
            return Version(result)
        except Exception as e:
            raise ConanException("Error retrieving MSBuild version: '{}'".format(e))
