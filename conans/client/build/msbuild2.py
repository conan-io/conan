import copy
import os
import re

from conans.client import tools
from conans.client.build.visual_environment import (VisualStudioBuildEnvironment,
                                                    vs_build_type_flags, vs_std_cpp)
from conans.client.tools.env import environment_append, no_op
from conans.client.tools.intel import compilervars
from conans.client.tools.oss import cpu_count
from conans.client.tools.win import vcvars_command
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.version import Version
from conans.tools import vcvars_command as tools_vcvars_command
from conans.util.env_reader import get_env
from conans.util.files import decode_text, save
from conans.util.runners import version_runner


class MSBuild2(object):

    def __init__(self, conanfile):
        assert isinstance(conanfile, ConanFile)
        self._conanfile = conanfile
        self._settings = self._conanfile.settings
        self._output = self._conanfile.output
        self.build_env = VisualStudioBuildEnvironment(self._conanfile,
                                                      with_build_type_flags=False)

    def build(self, project_file, targets=None, upgrade_project=True, build_type=None, arch=None,
              parallel=True, force_vcvars=False, toolset=None, platforms=None, use_env=True,
              vcvars_ver=None, winsdk_version=None, properties=None, output_binary_log=None,
              property_file_name=None, verbosity=None,
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
        self.build_env.parallel = parallel

        with environment_append(self.build_env.vars):
            # Path for custom properties file
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
                context = compilervars(self._conanfile.settings, arch)
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
