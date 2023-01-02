import os
import re
import xml.etree.ElementTree as ET

from conan.tools.microsoft.msbuilddeps import MSBuildDeps
from conan.tools.microsoft.toolchain import MSBuildToolchain
from conan.tools.microsoft.visual import msbuild_arch
from conans.errors import ConanException


def msbuild_verbosity_cmd_line_arg(conanfile):
    verbosity = conanfile.conf.get("tools.microsoft.msbuild:verbosity")
    if verbosity:
        if verbosity not in ("Quiet", "Minimal", "Normal", "Detailed", "Diagnostic"):
            raise ConanException("Unknown msbuild verbosity: {}".format(verbosity))
        return '/verbosity:{}'.format(verbosity)


class MSBuild(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.build_type = conanfile.settings.get_safe("build_type")
        self.configuration = conanfile.settings.get_safe("build_type")
        # if platforms:
        #    msvc_arch.update(platforms)
        msvc_arch = msbuild_arch(conanfile)
        if conanfile.settings.get_safe("os") == "WindowsCE":
            msvc_arch = conanfile.settings.get_safe("os.platform")
        self.platform = msvc_arch

    def command(self, sln, targets=None, force_import_generated_files=False):
        cmd = ('msbuild "%s" /p:Configuration=%s /p:Platform=%s'
               % (sln, self.build_type, self.platform))

        if force_import_generated_files:
            cmd += f" {self._force_import_generated_files_cmd_line_arg()}"

        verbosity = msbuild_verbosity_cmd_line_arg(self._conanfile)
        if verbosity:
            cmd += " {}".format(verbosity)

        maxcpucount = self._conanfile.conf.get("tools.microsoft.msbuild:max_cpu_count",
                                               check_type=int)
        if maxcpucount:
            cmd += " /m:{}".format(maxcpucount)

        if targets:
            if not isinstance(targets, list):
                raise ConanException("targets argument should be a list")
            cmd += " /target:{}".format(";".join(targets))

        return cmd

    def build(self, sln, targets=None, force_import_generated_files=False):
        cmd = self.command(sln, targets=targets, force_import_generated_files=force_import_generated_files)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(_):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")

    def _get_concrete_props_file(self, root_props_file):
        concrete_props_file = ""

        root = ET.parse(root_props_file).getroot()
        namespace = re.match('\{.*\}', root.tag)
        namespace = namespace.group(0) if namespace else ""
        importgroup_element = root.find(f"{namespace}ImportGroup")
        if importgroup_element:
            expected_condition = f"'$(Configuration)' == '{self.configuration}' And '$(Platform)' == '{self.platform}'"
            for import_element in importgroup_element.iter(f"{namespace}Import"):
                condition = import_element.attrib.get("Condition")
                if expected_condition == condition:
                    concrete_props_file = import_element.attrib.get("Project")
                    break

        if concrete_props_file:
            concrete_props_file = os.path.join(self._conanfile.generators_folder, concrete_props_file)

        if not concrete_props_file or not os.path.exists(concrete_props_file):
            raise ConanException(
                f"MSBuildToolchain props file is missing for configuration={self.configuration} and "
                f"platform={self.platform}. 'configuration' and 'platform' attributes must be the same "
                "respectively in MSBuildToolchain and MSBuild."
            )

        return concrete_props_file

    def _get_msbuildtoolchain_properties(self, root_props_file):
        properties = {}

        # Get properties from props file of configuration and platform
        concrete_props_file = self._get_concrete_props_file(root_props_file)
        root = ET.parse(concrete_props_file).getroot()
        namespace = re.match('\{.*\}', root.tag)
        namespace = namespace.group(0) if namespace else ""
        for propertygroup in root.iter(f"{namespace}PropertyGroup"):
            if propertygroup.attrib.get("Label") == "Configuration":
                for child in propertygroup:
                    propert_name = child.tag.replace(namespace, "")
                    properties[propert_name] = child.text
        return properties

    def _force_import_generated_files_cmd_line_arg(self):
        cmd_args = []
        props_paths = []

        # MSBuildToolchan must be in generators for this MSBuild mode
        msbuildtoolchain_file = os.path.join(self._conanfile.generators_folder, MSBuildToolchain.filename)
        if not os.path.exists(msbuildtoolchain_file):
            raise ConanException("Missing MSBuildToolchain, it should be added to generators")
        props_paths.append(msbuildtoolchain_file)

        # Properties of MSBuildToolchain must be extracted and passed manually through command line
        # because they don't have precedence when props file is injected with /p:ForceImportBeforeCppTargets
        properties = self._get_msbuildtoolchain_properties(msbuildtoolchain_file)
        for k, v in properties.items():
            cmd_args.append(f"/p:{k}=\"{v}\"")

        # MSBuildDeps generator is optional
        msbuilddeps_file = os.path.join(self._conanfile.generators_folder, MSBuildDeps.filename)
        if os.path.exists(msbuilddeps_file):
            props_paths.append(msbuilddeps_file)

        # Inject root props generated by MSBuildToolchain & MSBuildDeps
        if props_paths:
            cmd_args.append(f"/p:ForceImportBeforeCppTargets=\"{';'.join(props_paths)}\"")

        return " ".join(cmd_args)
