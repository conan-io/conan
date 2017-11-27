import os
from conans.model import Generator
from conans.client.generators import VisualStudioGenerator
from xml.dom import minidom
from conans.util.files import load


class VSSettings(object):
    def __init__(self, settings, use_version=True):
        self._props = [("Configuration", settings.get_safe("build_type")),
                       ("Platform", {'x86': 'Win32', 'x86_64': 'x64'}.get(settings.get_safe("arch"))),
                       ("PlatformToolset", settings.get_safe("compiler.toolset"))]

        if use_version:
            self._props.append(("VisualStudioVersion", settings.get_safe("compiler.version")))

    @property
    def filename(self):
        name = "conanbuildinfo%s.props" % "".join("_%s" % v for _, v in self._props if v)
        return name.lower()

    @property
    def condition(self):
        result = []
        for k, v in self._props:
            if v:
                if k == "VisualStudioVersion":
                    v += ".0"
                result.append("'$(%s)' == '%s'" % (k, v))
        return " And ".join(result)


class _VisualStudioMultiBase(Generator):

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
        vs_settings = VSSettings(self.conanfile.settings, self.use_version)
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


class VisualStudioMultiGenerator(_VisualStudioMultiBase):
    use_version = True


class VisualStudioMultiToolsetGenerator(_VisualStudioMultiBase):
    use_version = False
