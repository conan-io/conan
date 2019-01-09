from conans.model import Generator


class VisualStudioLegacyGenerator(Generator):
    template = '''<?xml version="1.0" encoding="Windows-1252"?>
<VisualStudioPropertySheet
    ProjectType="Visual C++"
    Version="8.00"
    Name="conanbuildinfo"
    >
    <Tool
        Name="VCCLCompilerTool"
        AdditionalOptions="{compiler_flags}"
        AdditionalIncludeDirectories="{include_dirs}"
        PreprocessorDefinitions="{definitions}"
    />
    <Tool
        Name="VCLinkerTool"
        AdditionalOptions="{linker_flags}"
        AdditionalDependencies="{libs}"
        AdditionalLibraryDirectories="{lib_dirs}"
    />
</VisualStudioPropertySheet>'''

    @property
    def filename(self):
        return 'conanbuildinfo.vsprops'

    @property
    def content(self):
        fields = {
            'include_dirs': "".join("&quot;%s&quot;;" % p for p in self._deps_build_info.include_paths).replace("\\", "/"),
            'lib_dirs': "".join("&quot;%s&quot;;" % p for p in self._deps_build_info.lib_paths).replace("\\", "/"),
            'libs': "".join(['%s.lib ' % lib if not lib.endswith(".lib")
                             else '%s ' % lib for lib in self._deps_build_info.libs]),
            'definitions': "".join("%s;" % d for d in self._deps_build_info.defines),
            'compiler_flags': " ".join(self._deps_build_info.cppflags + self._deps_build_info.cflags),
            'linker_flags': " ".join(self._deps_build_info.sharedlinkflags),
        }
        return self.template.format(**fields)
