import os
import textwrap
from xml.dom import minidom

from conans.client.tools import msvs_toolset, VALID_LIB_EXTENSIONS
from conans.errors import ConanException
from conans.model import Generator
from conans.util.files import load


class MSVCGenerator(Generator):

    dep_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
            <ImportGroup Label="PropertySheets" >
            </ImportGroup>
            <PropertyGroup Label="UserMacros" />
            <PropertyGroup />
            <ItemDefinitionGroup />
            <ItemGroup />
        </Project>
        """)

    dep_conf_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="PropertySheets">
            {transitive_imports}
          </ImportGroup>
          <PropertyGroup Label="UserMacros" />
          <PropertyGroup>
            <conan_{name}_props_imported>True</conan_{name}_props_imported>
          </PropertyGroup>
          <PropertyGroup Label="ConanVariables">
            <Conan{name}CompilerFlags>{compiler_flags}</Conan{name}CompilerFlags>
            <Conan{name}LinkerFlags>{linker_flags}</Conan{name}LinkerFlags>
            <Conan{name}PreprocessorDefinitions>{definitions}</Conan{name}PreprocessorDefinitions>
            <Conan{name}IncludeDirectories>{include_dirs}</Conan{name}IncludeDirectories>
            <Conan{name}ResourceDirectories>{res_dirs}</Conan{name}ResourceDirectories>
            <Conan{name}LibraryDirectories>{lib_dirs}</Conan{name}LibraryDirectories>
            <Conan{name}BinaryDirectories>{bin_dirs}</Conan{name}BinaryDirectories>
            <Conan{name}Libraries>{libs}</Conan{name}Libraries>
            <Conan{name}SystemDeps>{system_libs}</Conan{name}SystemDeps>
          </PropertyGroup>
          <PropertyGroup>
            <LocalDebuggerEnvironment>PATH=%PATH%;$(Conan{name}BinaryDirectories)
            </LocalDebuggerEnvironment>
            <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>
          </PropertyGroup>
          <ItemDefinitionGroup>
            <ClCompile>
              <AdditionalIncludeDirectories>$(Conan{name}IncludeDirectories)
              %(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
              <PreprocessorDefinitions>$(Conan{name}PreprocessorDefinitions)
              %(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>$(Conan{name}CompilerFlags) %(AdditionalOptions)</AdditionalOptions>
            </ClCompile>
            <Link>
              <AdditionalLibraryDirectories>$(Conan{name}LibraryDirectories)
              %(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
              <AdditionalDependencies>$(Conan{name}Libraries)%(AdditionalDependencies)
              </AdditionalDependencies>
              <AdditionalDependencies>$(Conan{name}SystemDeps)%(AdditionalDependencies)
              </AdditionalDependencies>
              <AdditionalOptions>$(Conan{name}LinkerFlags) %(AdditionalOptions)</AdditionalOptions>
            </Link>
            <Midl>
              <AdditionalIncludeDirectories>$(Conan{name}IncludeDirectories)
              %(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
            </Midl>
            <ResourceCompile>
              <AdditionalIncludeDirectories>$(Conan{name}IncludeDirectories)
              %(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
              <PreprocessorDefinitions>$(Conan{name}PreprocessorDefinitions)
              %(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>$(Conan{name}CompilerFlags) %(AdditionalOptions)</AdditionalOptions>
            </ResourceCompile>
          </ItemDefinitionGroup>
          <ItemGroup />
        </Project>
        """)

    @property
    def filename(self):
        return None

    @ staticmethod
    def _name_condition(settings):
        toolset = msvs_toolset(settings)
        if toolset is None:
            raise ConanException("Undefined Visual Studio version %s" %
                                 settings.get_safe("compiler.version"))

        props = [("Configuration", settings.build_type),
                 ("Platform", {'x86': 'Win32',
                               'x86_64': 'x64'}.get(settings.get_safe("arch"))),
                 ("PlatformToolset", toolset)]

        name = "".join("_%s" % v for _, v in props if v)
        condition = " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in props if v)
        return name.lower(), condition

    def _multi(self, name_multi, name_conf, condition):
        # read the existing mult_filename or use the template if it doesn't exist
        multi_path = os.path.join(self.output_path, name_multi)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self.dep_props

        # parse the multi_file and add a new import statement if needed
        dom = minidom.parseString(content_multi)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for node in children:
            if (name_conf == node.getAttribute("Project") and
                    condition == node.getAttribute("Condition")):
                # the import statement already exists
                break
        else:
            # create a new import statement
            import_node = dom.createElement('Import')
            import_node.setAttribute('Condition', condition)
            import_node.setAttribute('Project', name_conf)
            # add it to the import group
            import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _general(self, name_general, deps, conf_name, condition):
        # read the existing mult_filename or use the template if it doesn't exist
        multi_path = os.path.join(self.output_path, name_general)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self.dep_props

        # parse the multi_file and add a new import statement if needed
        dom = minidom.parseString(content_multi)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for dep in deps:
            conf_props_name = "conan_%s%s.props" % (dep, conf_name)
            for node in children:
                if (conf_props_name == node.getAttribute("Project") and
                        condition == node.getAttribute("Condition")):
                    # the import statement already exists
                    break
            else:
                # create a new import statement
                import_node = dom.createElement('Import')
                import_node.setAttribute('Condition', condition)
                import_node.setAttribute('Project', conf_props_name)
                # add it to the import group
                import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _dep_conf(self, name, cpp_info, conf_name):
        def has_valid_ext(lib):
            ext = os.path.splitext(lib)[1]
            return ext in VALID_LIB_EXTENSIONS

        t = "<Import Project=\"{}\" Condition=\"'$(conan_{}_props_imported)' != 'True'\"/>"
        transitive_imports = []
        for dep_name in cpp_info.public_deps:
            conf_props_name = "conan_%s%s.props" % (dep_name, conf_name)
            transitive_imports.append(t.format(conf_props_name, dep_name))
        transitive_imports = os.linesep.join(transitive_imports)

        fields = {
            'name': name,
            'transitive_imports': transitive_imports,
            'bin_dirs': "".join("%s;" % p for p in cpp_info.bin_paths),
            'res_dirs': "".join("%s;" % p for p in cpp_info.res_paths),
            'include_dirs': "".join("%s;" % p for p in cpp_info.include_paths),
            'lib_dirs': "".join("%s;" % p for p in cpp_info.lib_paths),
            'libs': "".join(['%s.lib;' % lib if not has_valid_ext(lib)
                             else '%s;' % lib for lib in cpp_info.libs]),
            'system_libs': "".join(['%s.lib;' % sys_dep if not has_valid_ext(sys_dep)
                                    else '%s;' % sys_dep for sys_dep in cpp_info.system_libs]),
            'definitions': "".join("%s;" % d for d in cpp_info.defines),
            'compiler_flags': " ".join(cpp_info.cxxflags + cpp_info.cflags),
            'linker_flags': " ".join(cpp_info.sharedlinkflags),
            'exe_flags': " ".join(cpp_info.exelinkflags)
        }
        formatted_template = self.dep_conf_props.format(**fields)
        return formatted_template

    @property
    def content(self):
        self.conanfile.output.warn("*** The 'msvc' generator is EXPERIMENTAL ***")
        result = {}
        general_name = "conan_deps.props"
        conf_name, condition = self._name_condition(self.conanfile.settings)
        public_deps = self.conanfile.requires.keys()
        result[general_name] = self._general(general_name, public_deps, conf_name, condition)
        for dep_name, cpp_info in self._deps_build_info.dependencies:
            props_name = "conan_%s.props" % dep_name
            conf_props_name = "conan_%s%s.props" % (dep_name, conf_name)
            dep_content = self._multi(props_name, conf_props_name, condition)
            result[props_name] = dep_content
            dep_conf_content = self._dep_conf(dep_name, cpp_info, conf_name)
            result[conf_props_name] = dep_conf_content
        return result
