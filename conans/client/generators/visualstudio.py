from conans.model import Generator
from conans.paths import BUILD_INFO_VISUAL_STUDIO


class VisualStudioGenerator(Generator):

    template = '''<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ImportGroup Label="PropertySheets" />
  <PropertyGroup Label="UserMacros" />
  {item_properties}
  <PropertyGroup>
    <ExecutablePath>{bin_dirs}$(ExecutablePath)</ExecutablePath>
  </PropertyGroup>
  <PropertyGroup>
    <LocalDebuggerEnvironment>PATH=%PATH%;{bin_dirs}</LocalDebuggerEnvironment>
    <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>
  </PropertyGroup>
  {item_properties}
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

  #   item_template = '''  <PropertyGroup Label="{name}">
  #   <Conan.{name}.root>{root_dir}</Conan.{name}.root>
  #   <Conan.IncludeDirs.{name}>{include_dirs}</Conan.IncludeDirs.{name}>
  #   <Conan.LibDirs.{name}>{lib_dirs}</Conan.LibDirs.{name}>
  #   <Conan.BinDirs.{name}>{bin_dirs}</Conan.BinDirs.{name}>
  #   <Conan.Libs.{name}>{libs}</Conan.Libs.{name}>
  #   <Conan.Defines.{name}>{defines}</Conan.Defines.{name}>
  #   <Conan.CompileDefinitions.{name}>{definitions}</Conan.CompileDefinitions.{name}>
  #   <Conan.CxxFlags.{name}>{cxx_flags}</Conan.CxxFlags.{name}>
  #   <Conan.SharedLinkerFlags.{shared_linker_flags}>{include_dirs}</Conan.SharedLinkerFlags.{name}>
  #   <Conan.ExeLinkerFlags.{name}>{shared_exe_flags}</Conan.ExeLinkerFlags.{name}>
  #   <Conan.CFlags.{name}>{c_flags}</Conan.CFlags.{name}>
  # </PropertyGroup>'''

    item_template = '''  <PropertyGroup Label="{name}">
     <Conan.{name}.Root>{root_dir}</Conan.{name}.Root>
     <Conan.IncludeDirs.{name}>{include_dirs}</Conan.IncludeDirs.{name}>
     <Conan.LibDirs.{name}>{lib_dirs}</Conan.LibDirs.{name}>
     <Conan.BinDirs.{name}>{bin_dirs}</Conan.BinDirs.{name}>
     <Conan.Libs.{name}>{libs}</Conan.Libs.{name}>
     <Conan.Defines.{name}>{definitions}</Conan.Defines.{name}>
     <Conan.CompilerFlags.{name}>{compiler_flags}</Conan.CxxFlags.{name}>
     <Conan.SharedLinkerFlags.{linker_flags}>{include_dirs}</Conan.SharedLinkerFlags.{name}>
     <Conan.ExeLinkerFlags.{name}>{exe_flags}</Conan.ExeLinkerFlags.{name}>
   </PropertyGroup>'''

    def _format_template(self, template, dep_cpp_info, user_items=dict()):
        items = user_items.copy()
        items['bin_dirs'] = ";".join(dep_cpp_info.bin_paths)
        items['include_dirs'] = "".join(dep_cpp_info.include_paths)
        items['lib_dirs'] = "".join(dep_cpp_info.lib_paths)
        items['libs'] = "".join(['%s.lib;' % lib if not lib.endswith(".lib")
                             else '%s;' % lib for lib in dep_cpp_info.libs])
        items['definitions'] = "".join("%s;" % d for d in dep_cpp_info.defines)
        items['compiler_flags'] = " ".join(dep_cpp_info.cppflags + dep_cpp_info.cflags)
        items['linker_flags'] = " ".join(dep_cpp_info.sharedlinkflags)
        items['exe_flags'] = " ".join(dep_cpp_info.exelinkflags)

        print(items)
        line = template.format(**items)
        print(line)
        return line

    def _format_items(self, deps_cpp_info):
        sections = []
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            items = {
                'root_dir': dep_cpp_info.rootpath,
                'name': dep_name
            }
            sections.append(self._format_template(self.item_template, dep_cpp_info, items))
        return "\n".join(sections)

    @property
    def filename(self):
        return BUILD_INFO_VISUAL_STUDIO

    @property
    def content(self):
        per_item_props = self._format_items(self._deps_build_info)
        return self._format_template(self.template, self._deps_build_info, {'item_properties': per_item_props})

