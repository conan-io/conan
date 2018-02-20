from conans.model import Generator
from conans.paths import BUILD_INFO_VISUAL_STUDIO


class VisualStudioGenerator(Generator):

    template = '''<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ImportGroup Label="PropertySheets" />
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup Label="Conan-RootDirs">{item_properties}
  </PropertyGroup>
  <PropertyGroup Label="ConanVariables">
    <ConanBinaryDirectories>{bin_dirs}</ConanBinaryDirectories>
    <ConanResourceDirectories>{res_dirs}</ConanResourceDirectories>
  </PropertyGroup>
  <PropertyGroup>
    <LocalDebuggerEnvironment>PATH=%PATH%;{bin_dirs}</LocalDebuggerEnvironment>
    <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>
  </PropertyGroup>
  <ItemDefinitionGroup>
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
  </ItemDefinitionGroup>
  <ItemGroup />
</Project>'''

    item_template = '''
    <Conan-{name}-Root>{root_dir}</Conan-{name}-Root>'''

    def _format_items(self):
        sections = []
        for dep_name, cpp_info in self.deps_build_info.dependencies:
            fields = {
                'root_dir': cpp_info.rootpath,
                'name': dep_name.replace(".", "-")
            }
            section = self.item_template.format(**fields)
            sections.append(section)
        return "".join(sections)

    @property
    def filename(self):
        return BUILD_INFO_VISUAL_STUDIO

    @property
    def content(self):
        per_item_props = self._format_items()
        fields = {
            'item_properties': per_item_props,
            'bin_dirs': "".join("%s;" % p for p in self._deps_build_info.bin_paths).replace("\\", "/"),
            'res_dirs': "".join("%s;" % p for p in self._deps_build_info.res_paths).replace("\\", "/"),
            'include_dirs': "".join("%s;" % p for p in self._deps_build_info.include_paths).replace("\\", "/"),
            'lib_dirs': "".join("%s;" % p for p in self._deps_build_info.lib_paths).replace("\\", "/"),
            'libs': "".join(['%s.lib;' % lib if not lib.endswith(".lib")
                             else '%s;' % lib for lib in self._deps_build_info.libs]),
            'definitions': "".join("%s;" % d for d in self._deps_build_info.defines),
            'compiler_flags': " ".join(self._deps_build_info.cppflags + self._deps_build_info.cflags),
            'linker_flags': " ".join(self._deps_build_info.sharedlinkflags),
            'exe_flags': " ".join(self._deps_build_info.exelinkflags)
        }
        return self.template.format(**fields)
