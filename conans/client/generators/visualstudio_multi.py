#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from conans.model import Generator
from conans.client.generators import VisualStudioGenerator
from xml.dom import minidom
from conans.util.files import load



class VsSetting(object):
    """map Conan a setting on its respective Visual Studio Settings."""

    def __init__(self, conanfile_settings):
        self.settings = conanfile_settings
    
    @property
    def name(self):
        """MsBuild setting name"""
        raise NotImplementedError

    @property
    def value(self):
        """MsBuild setting value equivalent for the given conan setting"""        
        return NotImplementedError

    def condition_expression(self):
        """encode this setting as a suitable <Import> condition"""
        if (self.value is None):
            return None

        return "'$({name})' == '{value}'".format(
            name=self.name,
            value=self.value)

class VSBuildType(VsSetting):
    """ map conan.settings.build_type on the Visual Studio 'Configuration'
    """

    @property
    def name(self):
        return "Configuration"

    @property
    def value(self):
        """the Conan.settings.build_type matches perfectly with the visual studio configuration"""
        if (self.settings.build_type.value is None):
            return None
        return str(self.settings.build_type)

class VSArch(VsSetting):
    """map conan.settings.arch on the Visual Studio 'Platform'"""

    platformMapping = {
        'x86': 'Win32',
        'x86_64': 'x64'} 

    @property
    def name(self):
        return "Platform"

    @property
    def value(self):
        """return the appropriate platform value for a given Conan.settings.arch"""
        if (self.settings.arch.value is None):
            return None
        return VSArch.platformMapping.get(str(self.settings.arch))

class VSVersion(VsSetting):
    """map conan.settings.compiler.version on the Visual Studio 'VisualStudioVersion'"""

    @property
    def name(self):
        return "VisualStudioVersion"

    @property
    def value(self):
        """return the appropriate 'VisualStudioVersion' value for a given Conan.settings.compiler.version"""
        if (self.settings.compiler.version.value is None):
            return None
        
        return str(self.settings.compiler.version) + ".0"

class VSToolset(VsSetting):
    """map conan.settings.compiler.toolset on the Visual Studio 'PlatformToolset'"""

    @property
    def name(self):
        return "PlatformToolset"

    @property
    def value(self):
        """return the appropriate 'PlatformToolset' value for a given Conan.settings.compiler.toolset"""
        if (self.settings.compiler.toolset.value is None):
            return None

        return str(self.settings.compiler.toolset)


    


class VisualStudioMultiGeneratorHelper(object):
    """Helper object to create
    """

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

    def __init__(self, generator, suppressVersionCondition):
        self.generator = generator
        self.suppressVersionCondition = suppressVersionCondition


    def settings_specific_filename(self):
        settings = self.generator.conanfile.settings
        name = "conanbuildinfo"
        if (settings.build_type.value):
            name += "_" + VSBuildType(settings).value

        if (settings.arch.value):
            name += "_" + VSArch(settings).value      
        
        if (not self.suppressVersionCondition):
            # only include the IDE version if requested
            if(settings.compiler.version.value):
                name += "_" + str(settings.compiler.version)
                
        if (settings.compiler.toolset.value):
            name += "_" + VSToolset(settings).value

        name += ".props"
        return name.lower()

    def settings_specific_content(self):
        return VisualStudioGenerator(self.generator.conanfile).content

    def settings_specific_condition(self):
        conditions = []
        settings = self.generator.conanfile.settings
        if (settings.build_type.value):
            conditions.append(VSBuildType(settings).condition_expression())

        if (settings.arch.value):
            conditions.append(VSArch(settings).condition_expression())
        
        if (not self.suppressVersionCondition):
            # only include the IDE version if requested
            if (settings.compiler.version.value):
                conditions.append(VSVersion(settings).condition_expression())

        if (settings.compiler.toolset.value):
            conditions.append(VSToolset(settings).condition_expression())

        return " And ".join(conditions)
    
    def multi_filename(self):
        return 'conanbuildinfo_multi.props'

    def multi_content(self):
        # there is also ClCompile.RuntimeLibrary, but it's handling is a bit complicated, so skipping for now
        condition = self.settings_specific_condition()
        name_current = self.settings_specific_filename()

        # read the exising mult_filename or use the template if it doesn't exist
        name_multi = self.multi_filename()
        multi_path = os.path.join(self.generator.output_path, name_multi)
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

        return content_multi


class VisualStudioMultiGenerator(Generator):

    @property
    def filename(self):
        pass

    @property
    def content(self):
        h = VisualStudioMultiGeneratorHelper(self,
            suppressVersionCondition=False)
        
        return {h.multi_filename(): h.multi_content(),
                h.settings_specific_filename(): h.settings_specific_content()}
        

class VisualStudioMultiToolsetGenerator(Generator):

    @property
    def filename(self):
        pass

    @property
    def content(self):
        h = VisualStudioMultiGeneratorHelper(self,
            suppressVersionCondition=True)
        
        return {h.multi_filename(): h.multi_content(),
                h.settings_specific_filename(): h.settings_specific_content()}

