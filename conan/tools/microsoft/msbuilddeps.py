import os
import textwrap
from xml.dom import minidom

from conans.client.tools import VALID_LIB_EXTENSIONS
from conans.errors import ConanException
from conans.util.files import load, save


class MSBuildDeps(object):

    _vars_conf_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
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
        </Project>
        """)

    _dep_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="ConanDependencies">
          </ImportGroup>
          <ImportGroup Label="Configurations">
          </ImportGroup>
          <PropertyGroup>
            <conan_{name}_props_imported>True</conan_{name}_props_imported>
          </PropertyGroup>
          <PropertyGroup>
            <LocalDebuggerEnvironment>PATH=%PATH%;$(Conan{name}BinaryDirectories)$(LocalDebuggerEnvironment)</LocalDebuggerEnvironment>
            <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>
          </PropertyGroup>
          <ItemDefinitionGroup>
            <ClCompile>
              <AdditionalIncludeDirectories>$(Conan{name}IncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
              <PreprocessorDefinitions>$(Conan{name}PreprocessorDefinitions)%(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>$(Conan{name}CompilerFlags) %(AdditionalOptions)</AdditionalOptions>
            </ClCompile>
            <Link>
              <AdditionalLibraryDirectories>$(Conan{name}LibraryDirectories)%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
              <AdditionalDependencies>$(Conan{name}Libraries)%(AdditionalDependencies)</AdditionalDependencies>
              <AdditionalDependencies>$(Conan{name}SystemDeps)%(AdditionalDependencies)</AdditionalDependencies>
              <AdditionalOptions>$(Conan{name}LinkerFlags) %(AdditionalOptions)</AdditionalOptions>
            </Link>
            <Midl>
              <AdditionalIncludeDirectories>$(Conan{name}IncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
            </Midl>
            <ResourceCompile>
              <AdditionalIncludeDirectories>$(Conan{name}IncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
              <PreprocessorDefinitions>$(Conan{name}PreprocessorDefinitions)%(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>$(Conan{name}CompilerFlags) %(AdditionalOptions)</AdditionalOptions>
            </ResourceCompile>
          </ItemDefinitionGroup>
        </Project>
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.build_type
        self.platform = {'x86': 'Win32',
                         'x86_64': 'x64'}.get(str(conanfile.settings.arch))
        # TODO: this is ugly, improve this
        self.output_path = os.getcwd()

    def generate(self):
        # TODO: Apply config from command line, something like
        # configuration = self.conanfile.config.generators["msbuild"].configuration
        # if configuration is not None:
        #     self.configuration = configuration
        # platform
        # config_filename
        # TODO: This is duplicated in write_generators() function, would need to be moved
        # to generators and called from there
        if self.configuration is None:
            raise ConanException("MSBuildDeps.configuration is None, it should have a value")
        if self.platform is None:
            raise ConanException("MSBuildDeps.platform is None, it should have a value")
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            generator_file_path = os.path.join(self.output_path, generator_file)
            save(generator_file_path, content)

    def _config_filename(self):
        # Default name
        props = [("Configuration", self.configuration),
                 ("Platform", self.platform)]
        name = "".join("_%s" % v for _, v in props)
        return name.lower()

    def _condition(self):
        props = [("Configuration", self.configuration),
                 ("Platform", self.platform)]
        condition = " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in props)
        return condition

    def _deps_props(self, name_general, deps):
        """ this is a .props file including all declared dependencies
        """
        # read the existing multi_filename or use the template if it doesn't exist
        template = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                <ImportGroup Label="ConanDependencies" >
                </ImportGroup>
            </Project>
            """)
        multi_path = os.path.join(self.output_path, name_general)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = template

        # parse the multi_file and add a new import statement if needed
        dom = minidom.parseString(content_multi)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for dep in deps:
            conf_props_name = "conan_%s.props" % dep
            for node in children:
                if conf_props_name == node.getAttribute("Project"):
                    # the import statement already exists
                    break
            else:
                # create a new import statement
                import_node = dom.createElement('Import')
                dep_imported = "'$(conan_%s_props_imported)' != 'True'" % dep
                import_node.setAttribute('Project', conf_props_name)
                import_node.setAttribute('Condition', dep_imported)
                # add it to the import group
                import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()
        # To remove all extra blank lines
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _pkg_config_props(self, name, cpp_info):
        # returns a .props file with the variables definition for one package for one configuration
        def add_valid_ext(libname):
            ext = os.path.splitext(libname)[1]
            return '%s;' % libname if ext in VALID_LIB_EXTENSIONS else '%s.lib;' % libname

        fields = {
            'name': name,
            'bin_dirs': "".join("%s;" % p for p in cpp_info.bin_paths),
            'res_dirs': "".join("%s;" % p for p in cpp_info.res_paths),
            'include_dirs': "".join("%s;" % p for p in cpp_info.include_paths),
            'lib_dirs': "".join("%s;" % p for p in cpp_info.lib_paths),
            'libs': "".join([add_valid_ext(lib) for lib in cpp_info.libs]),
            'system_libs': "".join([add_valid_ext(sys_dep) for sys_dep in cpp_info.system_libs]),
            'definitions': "".join("%s;" % d for d in cpp_info.defines),
            'compiler_flags': " ".join(cpp_info.cxxflags + cpp_info.cflags),
            'linker_flags': " ".join(cpp_info.sharedlinkflags),
            'exe_flags': " ".join(cpp_info.exelinkflags)
        }
        formatted_template = self._vars_conf_props.format(**fields)
        return formatted_template

    def _pkg_props(self, name_multi, dep_name, vars_props_name, condition, cpp_info):
        # read the existing mult_filename or use the template if it doesn't exist
        multi_path = os.path.join(self.output_path, name_multi)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._dep_props

        content_multi = content_multi.format(name=dep_name)

        # parse the multi_file and add new import statement if needed
        dom = minidom.parseString(content_multi)
        import_deps, import_vars = dom.getElementsByTagName('ImportGroup')

        # Transitive Deps
        children = import_deps.getElementsByTagName("Import")
        for dep in cpp_info.public_deps:
            dep_props_name = "conan_%s.props" % dep
            dep_imported = "'$(conan_%s_props_imported)' != 'True'" % dep
            for node in children:
                if (dep_props_name == node.getAttribute("Project") and
                        dep_imported == node.getAttribute("Condition")):
                    break  # the import statement already exists
            else:  # create a new import statement
                import_node = dom.createElement('Import')
                import_node.setAttribute('Condition', dep_imported)
                import_node.setAttribute('Project', dep_props_name)
                import_deps.appendChild(import_node)

        # Current vars
        children = import_vars.getElementsByTagName("Import")
        for node in children:
            if (vars_props_name == node.getAttribute("Project") and
                    condition == node.getAttribute("Condition")):
                break  # the import statement already exists
        else:  # create a new import statement
            import_node = dom.createElement('Import')
            import_node.setAttribute('Condition', condition)
            import_node.setAttribute('Project', vars_props_name)
            import_vars.appendChild(import_node)

        content_multi = dom.toprettyxml()
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _content(self):
        print("*** The 'msbuild' generator is EXPERIMENTAL ***")
        if not self._conanfile.settings.get_safe("build_type"):
            raise ConanException("The 'msbuild' generator requires a 'build_type' setting value")
        result = {}
        general_name = "conan_deps.props"
        conf_name = self._config_filename()
        condition = self._condition()
        public_deps = self._conanfile.requires.keys()
        result[general_name] = self._deps_props(general_name, public_deps)
        for dep_name, cpp_info in self._conanfile.deps_cpp_info.dependencies:
            # One file per configuration, with just the variables
            vars_props_name = "conan_%s%s.props" % (dep_name, conf_name)
            vars_conf_content = self._pkg_config_props(dep_name, cpp_info)
            result[vars_props_name] = vars_conf_content

            # The entry point for each package, it will have conditionals to the others
            props_name = "conan_%s.props" % dep_name
            dep_content = self._pkg_props(props_name, dep_name, vars_props_name, condition, cpp_info)
            result[props_name] = dep_content

        return result
