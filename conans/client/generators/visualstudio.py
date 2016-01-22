from conans.model import Generator
from conans.paths import BUILD_INFO_VISUAL_STUDIO


class VisualStudioGenerator(Generator):

    template = '''<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ImportGroup Label="PropertySheets" />
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup />
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
  </ItemDefinitionGroup>
  <ItemGroup />
</Project>'''

    def __init__(self, deps_cpp_info, cpp_info):
        super(VisualStudioGenerator, self).__init__(deps_cpp_info, cpp_info)
        self.include_dirs = "".join('%s;' % p.replace("\\", "/")
                                    for p in deps_cpp_info.include_paths)
        self.lib_dirs = "".join('%s;' % p.replace("\\", "/")
                                for p in deps_cpp_info.lib_paths)
        self.libs = "".join(['%s.lib;' % lib if not lib.endswith(".lib")
                             else '%s;' % lib for lib in deps_cpp_info.libs])
        self.definitions = "".join("%s;" % d for d in deps_cpp_info.defines)
        self.compiler_flags = " ".join(deps_cpp_info.cppflags + deps_cpp_info.cflags)
        self.linker_flags = " ".join(deps_cpp_info.sharedlinkflags)

    @property
    def filename(self):
        return BUILD_INFO_VISUAL_STUDIO

    @property
    def content(self):
        return self.template.format(**self.__dict__)
