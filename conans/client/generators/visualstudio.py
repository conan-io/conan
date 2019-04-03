import os
import re

from conans.model import Generator
from conans.paths import BUILD_INFO_VISUAL_STUDIO


class VisualStudioGenerator(Generator):

    template = '''<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ImportGroup Label="PropertySheets" />
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup Label="Conan-RootDirs">{item_properties}
  </PropertyGroup>
  {properties}
  <ItemGroup />
</Project>'''

    properties_template = '''  <PropertyGroup Label="ConanVariables"{condition}>
    <ConanBinaryDirectories>{bin_dirs};%(ConanBinaryDirectories)</ConanBinaryDirectories>
    <ConanResourceDirectories>{res_dirs};%(ConanResourceDirectories)$(</ConanResourceDirectories>
  </PropertyGroup>
  <PropertyGroup{condition}>
    <LocalDebuggerEnvironment>PATH=%PATH%;{bin_dirs}</LocalDebuggerEnvironment>
    <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>
  </PropertyGroup>
  <ItemDefinitionGroup{condition}>
    <ClCompile>
      <AdditionalIncludeDirectories>{include_dirs}%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <PreprocessorDefinitions>{definitions}%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <AdditionalOptions>{compiler_flags} %(AdditionalOptions)</AdditionalOptions>
    </ClCompile>
    <Link>
      <AdditionalLibraryDirectories>{lib_dirs}%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
      <AdditionalDependencies>{libs}%(AdditionalDependencies)</AdditionalDependencies>
      <AdditionalOptions>{linker_flags} %(AdditionalOptions)</AdditionalOptions>
    </Link>
    <Midl>
      <AdditionalIncludeDirectories>{include_dirs}%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
    </Midl>
    <ResourceCompile>
      <AdditionalIncludeDirectories>{include_dirs}%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <PreprocessorDefinitions>{definitions}%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <AdditionalOptions>{compiler_flags} %(AdditionalOptions)</AdditionalOptions>
    </ResourceCompile>
  </ItemDefinitionGroup>'''

    item_template = '''
    <Conan-{name}-Root>{root_dir}</Conan-{name}-Root>'''

    def _format_items(self):
        sections = []
        for dep_name, cpp_info in self._deps_build_info.dependencies:
            fields = {
                'root_dir': cpp_info.rootpath.replace("\\", "/"),
                'name': dep_name.replace(".", "-")
            }
            section = self.item_template.format(**fields)
            sections.append(section)
        return "".join(sections)

    @property
    def filename(self):
        return BUILD_INFO_VISUAL_STUDIO

    def _format_properties(self, build_info, condition):
        fields = {
            'condition': condition,
            'bin_dirs': "".join("%s;" % p for p in build_info.bin_paths).replace("\\", "/"),
            'res_dirs': "".join("%s;" % p for p in build_info.res_paths).replace("\\", "/"),
            'include_dirs': "".join("%s;" % p for p in build_info.include_paths).replace("\\", "/"),
            'lib_dirs': "".join("%s;" % p for p in build_info.lib_paths).replace("\\", "/"),
            'libs': "".join(['%s.lib;' % lib if not lib.endswith(".lib")
                             else '%s;' % lib for lib in build_info.libs]),
            'definitions': "".join("%s;" % d for d in build_info.defines),
            'compiler_flags': " ".join(build_info.cxxflags + build_info.cflags),
            'linker_flags': " ".join(build_info.sharedlinkflags),
            'exe_flags': " ".join(build_info.exelinkflags)
        }
        formatted_template = self.properties_template.format(**fields)
        return formatted_template

    @property
    def content(self):
        per_item_props = self._format_items()

        properties = [self._format_properties(self._deps_build_info, condition='')]
        for config, cpp_info in self._deps_build_info.configs.items():
            condition = " Condition=\"'$(Configuration)' == '%s'\"" % config
            properties.append(self._format_properties(cpp_info, condition=condition))

        fields = {
            'item_properties': per_item_props,
            'properties': '\n'.join(properties)
        }
        formatted_template = self.template.format(**fields)

        userprofile = os.getenv("USERPROFILE")
        if userprofile:
            userprofile = userprofile.replace("\\", "/")
            formatted_template = re.sub(userprofile, "$(USERPROFILE)", formatted_template,
                                        flags=re.I)
        return formatted_template
