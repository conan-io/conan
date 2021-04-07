import fnmatch
import os
import textwrap
from xml.dom import minidom

from jinja2 import Template

from conans.errors import ConanException
from conans.model.build_info import DepCppInfo
from conans.util.files import load, save

VALID_LIB_EXTENSIONS = (".so", ".lib", ".a", ".dylib", ".bc")


class MSBuildDeps(object):

    _vars_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <PropertyGroup Label="ConanVariables">
            <Conan{{name}}RootFolder>{{root_folder}}</Conan{{name}}RootFolder>
            <Conan{{name}}CompilerFlags>{{compiler_flags}}</Conan{{name}}CompilerFlags>
            <Conan{{name}}LinkerFlags>{{linker_flags}}</Conan{{name}}LinkerFlags>
            <Conan{{name}}PreprocessorDefinitions>{{definitions}}</Conan{{name}}PreprocessorDefinitions>
            <Conan{{name}}IncludeDirectories>{{include_dirs}}</Conan{{name}}IncludeDirectories>
            <Conan{{name}}ResourceDirectories>{{res_dirs}}</Conan{{name}}ResourceDirectories>
            <Conan{{name}}LibraryDirectories>{{lib_dirs}}</Conan{{name}}LibraryDirectories>
            <Conan{{name}}BinaryDirectories>{{bin_dirs}}</Conan{{name}}BinaryDirectories>
            <Conan{{name}}Libraries>{{libs}}</Conan{{name}}Libraries>
            <Conan{{name}}SystemLibs>{{system_libs}}</Conan{{name}}SystemLibs>
            <Conan{{name}}Dependencies>{{dependencies}}</Conan{{name}}Dependencies>
          </PropertyGroup>
        </Project>
        """)

    _conf_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="ConanDependencies">
            {% for dep in deps %}
            <Import Condition="'$(conan_{{dep}}_props_imported)' != 'True'" Project="conan_{{dep}}.props"/>
            {% endfor %}
          </ImportGroup>
          <ImportGroup Label="ConanPackageVariables">
            <Import Project="{{vars_filename}}"/>
          </ImportGroup>
          <PropertyGroup>
            <LocalDebuggerEnvironment>PATH=%PATH%;$(Conan{{name}}BinaryDirectories)$(LocalDebuggerEnvironment)</LocalDebuggerEnvironment>
            <DebuggerFlavor>WindowsLocalDebugger</DebuggerFlavor>
            {% if ca_exclude %}
            <CAExcludePath>$(Conan{{name}}IncludeDirectories);$(CAExcludePath)</CAExcludePath>
            {% endif %}
          </PropertyGroup>
          <ItemDefinitionGroup>
            <ClCompile>
              <AdditionalIncludeDirectories>$(Conan{{name}}IncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
              <PreprocessorDefinitions>$(Conan{{name}}PreprocessorDefinitions)%(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>$(Conan{{name}}CompilerFlags) %(AdditionalOptions)</AdditionalOptions>
            </ClCompile>
            <Link>
              <AdditionalLibraryDirectories>$(Conan{{name}}LibraryDirectories)%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
              <AdditionalDependencies>$(Conan{{name}}Libraries)%(AdditionalDependencies)</AdditionalDependencies>
              <AdditionalDependencies>$(Conan{{name}}SystemLibs)%(AdditionalDependencies)</AdditionalDependencies>
              <AdditionalOptions>$(Conan{{name}}LinkerFlags) %(AdditionalOptions)</AdditionalOptions>
            </Link>
            <Midl>
              <AdditionalIncludeDirectories>$(Conan{{name}}IncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
            </Midl>
            <ResourceCompile>
              <AdditionalIncludeDirectories>$(Conan{{name}}IncludeDirectories)%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
              <PreprocessorDefinitions>$(Conan{{name}}PreprocessorDefinitions)%(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>$(Conan{{name}}CompilerFlags) %(AdditionalOptions)</AdditionalOptions>
            </ResourceCompile>
          </ItemDefinitionGroup>
        </Project>
        """)

    _dep_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="Configurations">
          </ImportGroup>
          <PropertyGroup>
            <conan_{{name}}_props_imported>True</conan_{{name}}_props_imported>
          </PropertyGroup>
        </Project>
        """)

    _all_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="ConanDependencies">
          </ImportGroup>
        </Project>
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.build_type
        self.platform = {'x86': 'Win32',
                         'x86_64': 'x64'}.get(str(conanfile.settings.arch))
        # TODO: this is ugly, improve this
        self.output_path = os.getcwd()
        # ca_exclude section
        self.exclude_code_analysis = None
        ca_exclude = self._conanfile.conf["tools.microsoft.msbuilddeps"].exclude_code_analysis
        if ca_exclude is not None:
            # TODO: Accept single strings, not lists
            self.exclude_code_analysis = eval(ca_exclude)
            if not isinstance(self.exclude_code_analysis, list):
                raise ConanException("tools.microsoft.msbuilddeps:exclude_code_analysis must be a"
                                     " list of package names patterns like ['pkga*']")

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

    def _vars_props_file(self, name, cpp_info, deps):
        """
        content for conan_vars_poco_x86_release.props, containing the variables
        """
        # returns a .props file with the variables definition for one package for one configuration
        def add_valid_ext(libname):
            ext = os.path.splitext(libname)[1]
            return '%s;' % libname if ext in VALID_LIB_EXTENSIONS else '%s.lib;' % libname

        fields = {
            'name': name,
            'root_folder': cpp_info.rootpath,
            'bin_dirs': "".join("%s;" % p for p in cpp_info.bin_paths),
            'res_dirs': "".join("%s;" % p for p in cpp_info.res_paths),
            'include_dirs': "".join("%s;" % p for p in cpp_info.include_paths),
            'lib_dirs': "".join("%s;" % p for p in cpp_info.lib_paths),
            'libs': "".join([add_valid_ext(lib) for lib in cpp_info.libs]),
            'system_libs': "".join([add_valid_ext(sys_dep) for sys_dep in cpp_info.system_libs]),
            'definitions': "".join("%s;" % d for d in cpp_info.defines),
            'compiler_flags': " ".join(cpp_info.cxxflags + cpp_info.cflags),
            'linker_flags': " ".join(cpp_info.sharedlinkflags),
            'exe_flags': " ".join(cpp_info.exelinkflags),
            'dependencies': ";".join(deps)
        }
        formatted_template = Template(self._vars_props).render(**fields)
        return formatted_template

    def _conf_props_file(self, dep_name, vars_props_name, deps):
        """
        content for conan_poco_x86_release.props, containing the activation
        """
        # TODO: This must include somehow the user/channel, most likely pattern to exclude/include
        # Probably also the negation pattern, exclude all not @mycompany/*
        ca_exclude = False
        if isinstance(self.exclude_code_analysis, list):
            for pattern in self.exclude_code_analysis:
                if fnmatch.fnmatch(dep_name, pattern):
                    ca_exclude = True
                    break
        else:
            ca_exclude = self.exclude_code_analysis

        template = Template(self._conf_props, trim_blocks=True, lstrip_blocks=True)
        content_multi = template.render(name=dep_name, ca_exclude=ca_exclude,
                                        vars_filename=vars_props_name, deps=deps)
        return content_multi

    def _dep_props_file(self, name, name_general, dep_props_filename, condition):
        multi_path = os.path.join(self.output_path, name_general)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._dep_props
            content_multi = Template(content_multi).render({"name": name})

        # parse the multi_file and add new import statement if needed
        dom = minidom.parseString(content_multi)
        import_vars = dom.getElementsByTagName('ImportGroup')[0]

        # Current vars
        children = import_vars.getElementsByTagName("Import")
        for node in children:
            if (dep_props_filename == node.getAttribute("Project") and
                    condition == node.getAttribute("Condition")):
                break  # the import statement already exists
        else:  # create a new import statement
            import_node = dom.createElement('Import')
            import_node.setAttribute('Condition', condition)
            import_node.setAttribute('Project', dep_props_filename)
            import_vars.appendChild(import_node)

        content_multi = dom.toprettyxml()
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _all_props_file(self, name_general, deps):
        """ this is a .props file including all declared dependencies
        """
        multi_path = os.path.join(self.output_path, name_general)
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._all_props

        # parse the multi_file and add a new import statement if needed
        dom = minidom.parseString(content_multi)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for dep in deps:
            conf_props_name = "conan_%s.props" % dep.name
            for node in children:
                if conf_props_name == node.getAttribute("Project"):
                    # the import statement already exists
                    break
            else:
                # create a new import statement
                import_node = dom.createElement('Import')
                dep_imported = "'$(conan_%s_props_imported)' != 'True'" % dep.name
                import_node.setAttribute('Project', conf_props_name)
                import_node.setAttribute('Condition', dep_imported)
                # add it to the import group
                import_group.appendChild(import_node)
        content_multi = dom.toprettyxml()
        # To remove all extra blank lines
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _content(self):
        # We cannot use self._conanfile.warn(), because that fails for virtual conanfile
        print("*** The 'msbuild' generator is EXPERIMENTAL ***")
        if not self._conanfile.settings.get_safe("build_type"):
            raise ConanException("The 'msbuild' generator requires a 'build_type' setting value")
        result = {}
        general_name = "conandeps.props"
        conf_name = self._config_filename()
        condition = self._condition()
        # Include all direct build_requires for host context. This might change
        direct_deps = self._conanfile.dependencies.direct_host_requires
        result[general_name] = self._all_props_file(general_name, direct_deps)
        for dep in self._conanfile.dependencies.host_requires:
            cpp_info = DepCppInfo(dep.cpp_info)  # To account for automatic component aggregation
            public_deps = [d.name for d in dep.dependencies.requires]
            # One file per configuration, with just the variables
            vars_props_name = "conan_%s_vars%s.props" % (dep.name, conf_name)
            result[vars_props_name] = self._vars_props_file(dep.name, cpp_info, public_deps)
            props_name = "conan_%s%s.props" % (dep.name, conf_name)
            result[props_name] = self._conf_props_file(dep.name, vars_props_name, public_deps)

            # The entry point for each package, it will have conditionals to the others
            dep_name = "conan_%s.props" % dep.name
            dep_content = self._dep_props_file(dep.name, dep_name, props_name, condition)
            result[dep_name] = dep_content

        return result
