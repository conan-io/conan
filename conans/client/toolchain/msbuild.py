import os
import textwrap
from xml.dom import minidom

from conans.client.tools import msvs_toolset
from conans.util.files import save, load


class MSBuildToolchain(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.definitions = {}

    @ staticmethod
    def _name_condition(settings):
        toolset = msvs_toolset(settings)

        props = [("Configuration", settings.build_type),
                 # FIXME: This probably requires mapping ARM architectures
                 ("Platform", {'x86': 'Win32',
                               'x86_64': 'x64'}.get(settings.get_safe("arch"))),
                 ("PlatformToolset", toolset)]

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
        toolset = self._conanfile.settings.get_safe("compiler.toolset")
        print("RUNTIME ", self._conanfile.settings.values.dumps(), runtime)
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
                </ClCompile>
              </ItemDefinitionGroup>
              <PropertyGroup>
                <PlatformToolset>{}</PlatformToolset>
              </PropertyGroup>
            </Project>
            """)
        definitions = ";".join([format_macro(k, v) for k, v in self.definitions.items()])
        platform_toolset = toolset or ""
        config_props = content.format(definitions, runtime_library, platform_toolset)
        config_filepath = os.path.abspath(config_filename)
        save(config_filepath, config_props)

    @staticmethod
    def _write_main_toolchain(config_filename, condition):
        main_toolchain_path = os.path.abspath("conan_toolchain.props")
        if os.path.isfile(main_toolchain_path):
            content = load(main_toolchain_path)
        else:
            content = textwrap.dedent("""\
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                    <ImportGroup Label="PropertySheets" >
                    </ImportGroup>
                </Project>
                """)

        dom = minidom.parseString(content)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
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
        save(main_toolchain_path, conan_toolchain)

    def _get_props_file_contents(self, definitions=None):
        # how to specify runtime in command line:
        # https://stackoverflow.com/questions/38840332/msbuild-overrides-properties-while-building-vc-project

        if self.build_env:
            # Take the flags from the build env, the user was able to alter them if needed
            flags = copy.copy(self.build_env.flags)
            flags.append(self.build_env.std)
        else:  # To be removed when build_sln_command is deprecated
            flags = vs_build_type_flags(self._settings, with_flags=False)
            flags.append(vs_std_cpp(self._settings))

        flags_str = " ".join(list(filter(None, flags)))  # Removes empty and None elements
        additional_node = "<AdditionalOptions>" \
                          "{} %(AdditionalOptions)" \
                          "</AdditionalOptions>".format(flags_str) if flags_str else ""

        template = """<?xml version="1.0" encoding="utf-8"?>
<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemDefinitionGroup>
    <ClCompile>
      {additional_node}
    </ClCompile>
  </ItemDefinitionGroup>
</Project>""".format(**{"additional_node": additional_node})
        return template
