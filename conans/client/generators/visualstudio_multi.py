import os
from xml.dom import minidom

from conans.client.generators import VisualStudioGenerator
from conans.errors import ConanException
from conans.model import Generator
from conans.util.files import load
from conans.client.tools import msvs_toolset


class _VSSettings(object):
    def __init__(self, settings):
        toolset = msvs_toolset(settings)
        if toolset is None:
            raise ConanException("Undefined Visual Studio version %s" %
                                 settings.get_safe("compiler.version"))

        self._props = [("Configuration", settings.get_safe("build_type")),
                       ("Platform", {'x86': 'Win32',
                                     'x86_64': 'x64'}.get(settings.get_safe("arch"))),
                       ("PlatformToolset", toolset)]

    @property
    def filename(self):
        name = "conanbuildinfo%s.props" % "".join("_%s" % v for _, v in self._props if v)
        return name.lower()

    @property
    def condition(self):
        return " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in self._props if v)


class VisualStudioMultiGenerator(Generator):

    multi_content_template = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
    <ImportGroup Label="PropertySheets" >
    </ImportGroup>
    <PropertyGroup Label="UserMacros" />
    <PropertyGroup />
    <ItemDefinitionGroup />
    <ItemGroup />
</Project>
"""

    @property
    def filename(self):
        pass

    @property
    def content(self):
        vs_settings = _VSSettings(self.conanfile.settings)
        condition = vs_settings.condition
        name_current = vs_settings.filename
        name_multi = "conanbuildinfo_multi.props"

        # read the exising mult_filename or use the template if it doesn't exist
        multi_path = os.path.join(self.output_path, name_multi)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self.multi_content_template

        # parse the multi_file and add a new import statement if needed
        dom = minidom.parseString(content_multi)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for node in children:
            if name_current == node.getAttribute("Project") and condition == node.getAttribute("Condition"):
                # the import statement already exists
                break
        else:
            # create a new import statement
            import_node = dom.createElement('Import')
            import_node.setAttribute('Condition', condition)
            import_node.setAttribute('Project', name_current)
            # add it to the import group
            import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())

        return {name_multi: content_multi,
                vs_settings.filename: VisualStudioGenerator(self.conanfile).content}
