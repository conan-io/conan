import os
import textwrap
from xml.dom import minidom

from conans.client.tools import msvs_toolset
from conans.util.files import save


class MSBuildToolchain(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.definitions = {}

    @staticmethod
    def _name_condition(settings):
        toolset = msvs_toolset(settings)

        props = [("Configuration", settings.build_type),
                 # FIXME: This probably requires mapping ARM architectures
                 ("Platform", {'x86': 'Win32',
                               'x86_64': 'x64'}.get(settings.get_safe("arch"))),
                 ("PlatformToolset", toolset)]

        name = "".join("_%s" % v for _, v in props)
        condition = " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in props)
        return name.lower(), condition

    def dump(self, install_folder):
        def format_macro(k, value):
            return '%s="%s"' % (k, value) if value is not None else k

        name, condition = self._name_condition(self._conanfile.settings)
        runtime = self._conanfile.settings.get_safe("compiler.runtime")
        runtime_library = {"MT": "MultiThreaded",
                           "MTd": "MultiThreadedDebug",
                           "MD": "MultiThreadedDLL",
                           "MDd": "MultiThreadedDebugDLL"}.get(runtime, "")

        config_filename = "conan_toolchain{}.props".format(name)
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
            </Project>
            """)
        definitions = ";".join([format_macro(k, v) for k, v in self.definitions.items()])
        config_props = content.format(definitions, runtime_library)
        config_filepath = os.path.join(install_folder, config_filename)
        save(config_filepath, config_props)

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
        save(os.path.join(install_folder, "conan_toolchain.props"), conan_toolchain)
