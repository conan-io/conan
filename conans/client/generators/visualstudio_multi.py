#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from conans.model import Generator
from conans.client.generators import VisualStudioGenerator
from xml.dom import minidom
from conans.util.files import load



class VsSetting(object):
    """ map Conan settings on their respective Visual Studio Settings.
    """

    def __init__(self, conanfile_settings):
        self.settings = conanfile_settings
    
    @property
    def name(self):
        raise NotImplementedError

    @property
    def value(self):
        return NotImplementedError

    def condition_expression(self):
        return "'$({name})' == '{value}'".format(
                name=self.VsSettingName,
                value=self.VsSettingValue)

class VSBuildType(VsSetting):
    """ mapConan settings.build_type on the Visual Studio 'Configuration'
    """

    @property
    def name(self):
        return "Configuration"

    @property
    def value(self):
        """the Conan.settings.build_type matches perfectly with the visual studio configuration"""
        return str(self.settings.build_type)

class VSArch(VsSetting):
    """ map Conan settings.arch on the Visual Studio 'Platform'
    """

    platformMapping = {
        'x86': 'Win32',
        'x86_64': 'x64'}
    

    @property
    def name(self):
        return "Platform"

    @property
    def value(self):
        """return the appropriate platform value for a given Conan.settings.arch"""
        return VSArch.platformMapping.get(self.setttings.arch)

class VSVersion(VsSetting):
    """ map Conan settings.compiler.version on the Visual Studio 'VisualStudioVersion'
    """

    @property
    def name(self):
        return "VisualStudioVersion"

    @property
    def valkue(self):
        """return the appropriate 'VisualStudioVersion' value for a given Conan.settings.compiler.version"""
        return str(self.settings.compiler.version) + ".0"

class VSToolset(VsSetting):
    """ map Conan settings.compiler.toolset on the Visual Studio 'PlatformToolset'
    """
    
    def __init__(self, conan_toolset):
        self.conan_toolset = conan_toolset

    @property
    def name(self):
        return "PlatformToolset"

    @property
    def value(self):
        """return the appropriate 'PlatformToolset' value for a given Conan.settings.compiler.toolset"""
        return str(self.settings.compiler.toolset)


    


class VisualStudioMultiGenerator(Generator):
    template = """<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
    <ImportGroup Label="PropertySheets" >
    </ImportGroup>
    <PropertyGroup Label="UserMacros" />
    <PropertyGroup />
    <ItemDefinitionGroup />
    <ItemGroup />
</Project>
"""

    def __init__(self, includeVersionCondition):
        self.includeVersionCondition = includeVersionCondition

    @property
    def filename(self):
        pass

    def _condition_expression(self, settings):
        conditions = []
        if(settings.build_type):
            conditions.append(VSBuildType(settings).condition_expression())

        if(settings.arch):
            conditions.append(VSArch(settings).condition_expression())
        
        if(self.includeVersionCondition):
            # only include the IDE version if requested
            if(settings.compiler.version):
                conditions.append(VSVersion(settings).condition_expression())

        if(settings.compiler.toolset):
            conditions.append(VSToolset(settings).condition_expression())

        return " AND ".join(conditions)

    def _property_filename(self, settings):
        name = "conanbuildinfo"
        if(settings.build_type):
            name += "_" + VSBuildType(settings).value

        if(settings.arch):
            name += "_" + VSArch(settings).value      
        
        if(self.includeVersionCondition):
            # only include the IDE version if requested
            if(settings.compiler.version):
                name += "_" + VSArch(VSVersion).value
                
        if(settings.compiler.toolset):
            name += "_" + VSToolset(VSVersion).value

        name + ".props"
        return name.lower()

    @property
    def content(self):
        # there is also ClCompile.RuntimeLibrary, but it's handling is a bit complicated, so skipping for now
        condition = self._condition_expression(self.conanfile.settings)

        name_multi = 'conanbuildinfo_multi.props'
        name_current = self._property_filename(self.conanfile.settings)

        multi_path = os.path.join(self.output_path, name_multi)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self.template

        dom = minidom.parseString(content_multi)
        import_node = dom.createElement('Import')
        import_node.setAttribute('Condition', condition)
        import_node.setAttribute('Project', name_current)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for node in children:
            if name_current == node.getAttribute("Project") and condition == node.getAttribute("Condition"):
                break
        else:
            import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())

        vs_generator = VisualStudioGenerator(self.conanfile)
        content_current = vs_generator.content

        return {name_multi: content_multi, name_current: content_current}
