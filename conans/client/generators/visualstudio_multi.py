#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from conans.model import Generator
from conans.client.generators import VisualStudioGenerator
from xml.dom import minidom


class VisualStudioMultiGenerator(Generator):
    template = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
<ImportGroup Label="PropertySheets" ></ImportGroup>
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
        configuration = str(self.conanfile.settings.build_type)
        platform = {'x86': 'Win32', 'x86_64': 'x64'}.get(str(self.conanfile.settings.arch))
        vsversion = str(self.settings.compiler.version)

        # there is also ClCompile.RuntimeLibrary, but it's handling is a bit complicated, so skipping for now
        condition = " '$(Configuration)' == '%s' And '$(Platform)' == '%s' And '$(VisualStudioVersion)' == '%s' "\
                    % (configuration, platform, vsversion + '.0')

        name_multi = 'conanbuildinfo_multi.props'
        name_current = ('conanbuildinfo_%s_%s_%s.props' % (configuration, platform, vsversion)).lower()

        content_multi = self.template
        if os.path.isfile(name_multi):
            content_multi = open(name_multi, 'r').read()

        dom = minidom.parseString(content_multi)
        import_node = dom.createElement('Import')
        import_node.setAttribute('Condition', condition)
        import_node.setAttribute('Project', name_current)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()

        vs_generator = VisualStudioGenerator(self.conanfile)
        content_current = vs_generator.content

        return {name_multi: content_multi, name_current: content_current}
