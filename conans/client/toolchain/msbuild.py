import os
import textwrap
from xml.dom import minidom

from conans.client.toolchain.visual import vcvars_arch, vcvars_command
from conans.client.tools import msvs_toolset
from conans.errors import ConanException
from conans.util.files import save, load


class MSBuildCmd(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.version = conanfile.settings.get_safe("compiler.version")
        self.vcvars_arch = vcvars_arch(conanfile)
        self.build_type = conanfile.settings.get_safe("build_type")
        msvc_arch = {'x86': 'x86',
                     'x86_64': 'x64',
                     'armv7': 'ARM',
                     'armv8': 'ARM64'}
        # if platforms:
        #    msvc_arch.update(platforms)
        arch = conanfile.settings.get_safe("arch")
        msvc_arch = msvc_arch.get(str(arch))
        if conanfile.settings.get_safe("os") == "WindowsCE":
            msvc_arch = conanfile.settings.get_safe("os.platform")
        self.platform = msvc_arch

    def command(self, sln):
        vcvars = vcvars_command(self.version, architecture=self.vcvars_arch,
                                platform_type=None, winsdk_version=None,
                                vcvars_ver=None)
        cmd = ('%s && msbuild "%s" /p:Configuration=%s /p:Platform=%s '
               % (vcvars, sln, self.build_type, self.platform))
        return cmd

    def build(self, sln):
        cmd = self.command(sln)
        self._conanfile.run(cmd)

    @staticmethod
    def get_version(settings):
        return NotImplementedError("get_version() method is not supported in MSBuild "
                                   "toolchain helper")


class MSBuildToolchain(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.preprocessor_definitions = {}

    @staticmethod
    def _name_condition(settings):
        props = [("Configuration", settings.build_type),
                 # FIXME: This probably requires mapping ARM architectures
                 ("Platform", {'x86': 'Win32',
                               'x86_64': 'x64'}.get(settings.get_safe("arch")))]

        name = "".join("_%s" % v for _, v in props if v is not None)
        condition = " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in props if v is not None)
        return name.lower(), condition

    def write_toolchain_files(self):
        name, condition = self._name_condition(self._conanfile.settings)
        config_filename = "conan_toolchain{}.props".format(name)
        self._write_config_toolchain(config_filename)
        self._write_main_toolchain(config_filename, condition)

    def _write_config_toolchain(self, config_filename):

        def format_macro(k, value):
            return '%s="%s"' % (k, value) if value is not None else k

        runtime = self._conanfile.settings.get_safe("compiler.runtime")
        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        toolset = msvs_toolset(self._conanfile.settings)
        runtime_library = {"MT": "MultiThreaded",
                           "MTd": "MultiThreadedDebug",
                           "MD": "MultiThreadedDLL",
                           "MDd": "MultiThreadedDebugDLL"}.get(runtime, "")

        content = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ItemDefinitionGroup>
                <ClCompile>
                  <PreprocessorDefinitions>
                     {};%(PreprocessorDefinitions)
                  </PreprocessorDefinitions>
                  <RuntimeLibrary>{}</RuntimeLibrary>
                  <LanguageStandard>{}</LanguageStandard>
                </ClCompile>
              </ItemDefinitionGroup>
              <PropertyGroup Label="Configuration">
                <PlatformToolset>{}</PlatformToolset>
              </PropertyGroup>
            </Project>
            """)
        preprocessor_definitions = ";".join([format_macro(k, v)
                                             for k, v in self.preprocessor_definitions.items()])
        # It is useless to set PlatformToolset in the config file, because the conditional checks it
        cppstd = "stdcpp%s" % cppstd if cppstd else ""
        toolset = toolset or ""
        config_props = content.format(preprocessor_definitions, runtime_library, cppstd, toolset)
        config_filepath = os.path.abspath(config_filename)
        self._conanfile.output.info("MSBuildToolchain created %s" % config_filename)
        save(config_filepath, config_props)

    def _write_main_toolchain(self, config_filename, condition):
        main_toolchain_path = os.path.abspath("conan_toolchain.props")
        if os.path.isfile(main_toolchain_path):
            content = load(main_toolchain_path)
        else:
            content = textwrap.dedent("""\
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0"
                        xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                    <ImportGroup Label="PropertySheets" >
                    </ImportGroup>
                </Project>
                """)

        dom = minidom.parseString(content)
        try:
            import_group = dom.getElementsByTagName('ImportGroup')[0]
        except Exception:
            raise ConanException("Broken conan_toolchain.props. Remove the file and try again")
        children = import_group.getElementsByTagName("Import")
        for node in children:
            if (config_filename == node.getAttribute("Project") and
                    condition == node.getAttribute("Condition")):
                break  # the import statement already exists
        else:  # create a new import statement
            import_node = dom.createElement('Import')
            import_node.setAttribute('Condition', condition)
            import_node.setAttribute('Project', config_filename)
            import_group.appendChild(import_node)

        conan_toolchain = dom.toprettyxml()
        conan_toolchain = "\n".join(line for line in conan_toolchain.splitlines() if line.strip())
        self._conanfile.output.info("MSBuildToolchain writing %s" % "conan_toolchain.props")
        save(main_toolchain_path, conan_toolchain)
