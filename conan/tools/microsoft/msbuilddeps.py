import fnmatch
import os
import textwrap
from xml.dom import minidom

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conans.errors import ConanException
from conans.util.files import load, save

VALID_LIB_EXTENSIONS = (".so", ".lib", ".a", ".dylib", ".bc")


class MSBuildDeps(object):

    _vars_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <PropertyGroup Label="ConanVariables">
            <Conan{{name}}RootFolder>{{root_folder}}</Conan{{name}}RootFolder>
            <Conan{{name}}BinaryDirectories>{{bin_dirs}}</Conan{{name}}BinaryDirectories>
            <Conan{{name}}Dependencies>{{dependencies}}</Conan{{name}}Dependencies>
            {% if host_context %}
            <Conan{{name}}CompilerFlags>{{compiler_flags}}</Conan{{name}}CompilerFlags>
            <Conan{{name}}LinkerFlags>{{linker_flags}}</Conan{{name}}LinkerFlags>
            <Conan{{name}}PreprocessorDefinitions>{{definitions}}</Conan{{name}}PreprocessorDefinitions>
            <Conan{{name}}IncludeDirectories>{{include_dirs}}</Conan{{name}}IncludeDirectories>
            <Conan{{name}}ResourceDirectories>{{res_dirs}}</Conan{{name}}ResourceDirectories>
            <Conan{{name}}LibraryDirectories>{{lib_dirs}}</Conan{{name}}LibraryDirectories>
            <Conan{{name}}Libraries>{{libs}}</Conan{{name}}Libraries>
            <Conan{{name}}SystemLibs>{{system_libs}}</Conan{{name}}SystemLibs>
            {% endif %}
          </PropertyGroup>
        </Project>
        """)

    _conf_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="PropertySheets">
            {% for dep in deps %}
            <Import Condition="'$(conan_{{dep}}_props_imported)' != 'True'" Project="conan_{{dep}}.props"/>
            {% endfor %}
          </ImportGroup>
          <ImportGroup Label="PropertySheets">
            <Import Project="{{vars_filename}}"/>
          </ImportGroup>
          {% if host_context %}
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
          {% else %}
          <PropertyGroup>
            <ExecutablePath>$(Conan{{name}}BinaryDirectories)$(ExecutablePath)</ExecutablePath>
          </PropertyGroup>
          {% endif %}
        </Project>
        """)

    _dep_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="PropertySheets">
          </ImportGroup>
          <PropertyGroup>
            <conan_{{name}}_props_imported>True</conan_{{name}}_props_imported>
          </PropertyGroup>
        </Project>
        """)

    _all_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ImportGroup Label="PropertySheets">
          </ImportGroup>
        </Project>
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.build_type
        self.platform = {'x86': 'Win32',
                         'x86_64': 'x64'}.get(str(conanfile.settings.arch))
        # ca_exclude section
        # TODO: Accept single strings, not lists
        self.exclude_code_analysis = self._conanfile.conf.get("tools.microsoft.msbuilddeps:exclude_code_analysis",
                                                              check_type=list)
        check_using_build_profile(self._conanfile)

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
            save(generator_file, content)

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

    def _vars_props_file(self, dep, name, cpp_info, deps, build=False):
        """
        content for conan_vars_poco_x86_release.props, containing the variables
        """
        # returns a .props file with the variables definition for one package for one configuration
        def add_valid_ext(libname):
            ext = os.path.splitext(libname)[1]
            return '%s;' % libname if ext in VALID_LIB_EXTENSIONS else '%s.lib;' % libname

        pkg_placeholder = "$(Conan{}RootFolder)".format(name)

        def join_paths(paths):
            # ALmost copied from CMakeDeps TargetDataContext
            ret = []
            for p in paths:
                assert os.path.isabs(p), "{} is not absolute".format(p)

                if p.startswith(package_folder):
                    rel = p[len(package_folder):]
                    rel = rel.replace('\\', '/').replace('$', '\\$').replace('"', '\\"').lstrip("/")
                    norm_path = ("${%s}/%s" % (pkg_placeholder, rel))
                else:
                    norm_path = p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
                ret.append(norm_path)
            return "".join("{};".format(e) for e in ret)

        package_folder = dep.package_folder.replace('\\', '/')\
                                           .replace('$', '\\$').replace('"', '\\"')

        fields = {
            'name': name,
            'root_folder': package_folder,
            'bin_dirs': join_paths(cpp_info.bindirs),
            'res_dirs': join_paths(cpp_info.resdirs),
            'include_dirs': join_paths(cpp_info.includedirs),
            'lib_dirs': join_paths(cpp_info.libdirs),
            'libs': "".join([add_valid_ext(lib) for lib in cpp_info.libs]),
            # TODO: Missing objects
            'system_libs': "".join([add_valid_ext(sys_dep) for sys_dep in cpp_info.system_libs]),
            'definitions': "".join("%s;" % d for d in cpp_info.defines),
            'compiler_flags': " ".join(cpp_info.cxxflags + cpp_info.cflags),
            'linker_flags': " ".join(cpp_info.sharedlinkflags + cpp_info.exelinkflags),
            'dependencies': ";".join(deps) if not build else "",
            'host_context': not build
        }
        formatted_template = Template(self._vars_props, trim_blocks=True,
                                      lstrip_blocks=True).render(**fields)
        return formatted_template

    def _conf_props_file(self, dep_name, vars_props_name, deps, build=False):
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

        deps = [] if build else deps  # build-requires do not propagate dependencies
        template = Template(self._conf_props, trim_blocks=True, lstrip_blocks=True)
        content_multi = template.render(host_context=not build,
                                        name=dep_name, ca_exclude=ca_exclude,
                                        vars_filename=vars_props_name, deps=deps)
        return content_multi

    def _dep_props_file(self, name, name_general, dep_props_filename, condition):
        # Current directory is the generators_folder
        multi_path = name_general
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
        # Current directory is the generators_folder
        multi_path = name_general
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._all_props

        # parse the multi_file and add a new import statement if needed
        dom = minidom.parseString(content_multi)
        import_group = dom.getElementsByTagName('ImportGroup')[0]
        children = import_group.getElementsByTagName("Import")
        for req, dep in deps.items():
            dep_name = dep.ref.name.replace(".", "_")
            if req.build:
                dep_name += "_build"
            conf_props_name = "conan_%s.props" % dep_name
            for node in children:
                if conf_props_name == node.getAttribute("Project"):
                    # the import statement already exists
                    break
            else:
                # create a new import statement
                import_node = dom.createElement('Import')
                dep_imported = "'$(conan_%s_props_imported)' != 'True'" % dep_name
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

        host_req = list(self._conanfile.dependencies.host.values())
        test_req = list(self._conanfile.dependencies.test.values())

        for dep in host_req + test_req:
            dep_name = dep.ref.name
            dep_name = dep_name.replace(".", "_")
            cpp_info = dep.cpp_info.aggregated_components()
            public_deps = [d.ref.name.replace(".", "_")
                           for r, d in dep.dependencies.direct_host.items() if r.visible]
            # One file per configuration, with just the variables
            vars_props_name = "conan_%s_vars%s.props" % (dep_name, conf_name)
            result[vars_props_name] = self._vars_props_file(dep, dep_name, cpp_info, public_deps)
            props_name = "conan_%s%s.props" % (dep_name, conf_name)
            result[props_name] = self._conf_props_file(dep_name, vars_props_name, public_deps)

            # The entry point for each package, it will have conditionals to the others
            file_dep_name = "conan_%s.props" % dep_name
            dep_content = self._dep_props_file(dep_name, file_dep_name, props_name, condition)
            result[file_dep_name] = dep_content

        build_req = list(self._conanfile.dependencies.build.values())
        for dep in build_req:
            dep_name = dep.ref.name
            dep_name = dep_name.replace(".", "_") + "_build"
            cpp_info = dep.cpp_info.aggregated_components()
            public_deps = [d.ref.name.replace(".", "_")
                           for r, d in dep.dependencies.direct_host.items() if r.visible]
            # One file per configuration, with just the variables
            vars_props_name = "conan_%s_vars%s.props" % (dep_name, conf_name)
            result[vars_props_name] = self._vars_props_file(dep, dep_name, cpp_info, public_deps,
                                                            build=True)
            props_name = "conan_%s%s.props" % (dep_name, conf_name)
            result[props_name] = self._conf_props_file(dep_name, vars_props_name, public_deps,
                                                       build=True)

            # The entry point for each package, it will have conditionals to the others
            file_dep_name = "conan_%s.props" % dep_name
            dep_content = self._dep_props_file(dep_name, file_dep_name, props_name, condition)
            result[file_dep_name] = dep_content

        # Include all direct build_requires for host context. This might change
        direct_deps = self._conanfile.dependencies.filter({"direct": True})
        result[general_name] = self._all_props_file(general_name, direct_deps)

        return result
