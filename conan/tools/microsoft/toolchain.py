import os
import textwrap
from xml.dom import minidom

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.build import build_jobs
from conan.tools.intel.intel_cc import IntelCC
from conan.tools.microsoft.visual import VCVars, msvs_toolset
from conans.errors import ConanException
from conans.util.files import save, load


def arch_to_vcproj_platform(arch):
    return {
        "x86": "Win32",
        "x86_64": "x64",
        "armv7": "ARM",
        "armv8": "ARM64",
    }.get(arch)


class MSBuildToolchain(object):

    filename = "conantoolchain.props"

    _config_toolchain_props = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
          <ItemDefinitionGroup>
            <ClCompile>
              <PreprocessorDefinitions>{{ defines }}%(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>{{ compiler_flags }} %(AdditionalOptions)</AdditionalOptions>
              <RuntimeLibrary>{{ runtime_library }}</RuntimeLibrary>
              <LanguageStandard>{{ cppstd }}</LanguageStandard>{{ parallel }}{{ compile_options }}
            </ClCompile>
            <Link>
              <AdditionalOptions>{{ linker_flags }} %(AdditionalOptions)</AdditionalOptions>
            </Link>
            <ResourceCompile>
              <PreprocessorDefinitions>{{ defines }}%(PreprocessorDefinitions)</PreprocessorDefinitions>
              <AdditionalOptions>{{ compiler_flags }} %(AdditionalOptions)</AdditionalOptions>
            </ResourceCompile>
          </ItemDefinitionGroup>
          <PropertyGroup Label="Configuration">
            <PlatformToolset>{{ toolset }}</PlatformToolset>
            {% for k, v in properties.items() %}
            <{{k}}>{{ v }}</{{k}}>
            {% endfor %}
          </PropertyGroup>
        </Project>
    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._conanfile.must_use_new_helpers = True  # TODO: Remove 2.0
        self.preprocessor_definitions = {}
        self.compile_options = {}
        self.cxxflags = []
        self.cflags = []
        self.ldflags = []
        self.configuration = conanfile.settings.build_type
        self.platform = arch_to_vcproj_platform(str(conanfile.settings.arch))
        self.runtime_library = self._runtime_library(conanfile.settings)
        self.cppstd = conanfile.settings.get_safe("compiler.cppstd")
        self.toolset = msvs_toolset(conanfile)
        self.properties = {}
        check_using_build_profile(self._conanfile)

    def _name_condition(self):
        props = [("Configuration", self.configuration),
                 ("Platform", self.platform)]

        name = "".join("_%s" % v for _, v in props if v is not None)
        condition = " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in props if v is not None)
        return name.lower(), condition

    def generate(self):
        name, condition = self._name_condition()
        config_filename = "conantoolchain{}.props".format(name)
        # Writing the props files
        self._write_config_toolchain(config_filename)
        self._write_main_toolchain(config_filename, condition)
        if self._conanfile.settings.get_safe("compiler") == "intel-cc":
            IntelCC(self._conanfile).generate()
        else:
            VCVars(self._conanfile).generate()

    @staticmethod
    def _runtime_library(settings):
        compiler = settings.compiler
        runtime = settings.get_safe("compiler.runtime")
        if compiler == "msvc" or compiler == "intel-cc":
            build_type = settings.get_safe("build_type")
            if build_type != "Debug":
                runtime_library = {"static": "MultiThreaded",
                                   "dynamic": "MultiThreadedDLL"}.get(runtime, "")
            else:
                runtime_library = {"static": "MultiThreadedDebug",
                                   "dynamic": "MultiThreadedDebugDLL"}.get(runtime, "")
        else:
            runtime_library = {"MT": "MultiThreaded",
                               "MTd": "MultiThreadedDebug",
                               "MD": "MultiThreadedDLL",
                               "MDd": "MultiThreadedDebugDLL"}.get(runtime, "")
        return runtime_library

    @property
    def context_config_toolchain(self):

        def format_macro(key, value):
            return '%s=%s' % (key, value) if value is not None else key

        cxxflags, cflags, defines, sharedlinkflags, exelinkflags = self._get_extra_flags()
        preprocessor_definitions = "".join(["%s;" % format_macro(k, v)
                                            for k, v in self.preprocessor_definitions.items()])
        defines = preprocessor_definitions + "".join("%s;" % d for d in defines)
        self.cxxflags.extend(cxxflags)
        self.cflags.extend(cflags)
        self.ldflags.extend(sharedlinkflags + exelinkflags)

        cppstd = "stdcpp%s" % self.cppstd if self.cppstd else ""
        runtime_library = self.runtime_library
        toolset = self.toolset or ""
        compile_options = self._conanfile.conf.get("tools.microsoft.msbuildtoolchain:compile_options",
                                                   default={}, check_type=dict)
        self.compile_options.update(compile_options)
        parallel = ""
        njobs = build_jobs(self._conanfile)
        if njobs:
            parallel = "".join(
                ["\n      <MultiProcessorCompilation>True</MultiProcessorCompilation>",
                 "\n      <ProcessorNumber>{}</ProcessorNumber>".format(njobs)])
        compile_options = "".join("\n      <{k}>{v}</{k}>".format(k=k, v=v)
                                  for k, v in self.compile_options.items())
        return {
            'defines': defines,
            'compiler_flags': " ".join(self.cxxflags + self.cflags),
            'linker_flags': " ".join(self.ldflags),
            "cppstd": cppstd,
            "runtime_library": runtime_library,
            "toolset": toolset,
            "compile_options": compile_options,
            "parallel": parallel,
            "properties": self.properties,
        }

    def _write_config_toolchain(self, config_filename):
        config_filepath = os.path.join(self._conanfile.generators_folder, config_filename)
        config_props = Template(self._config_toolchain_props, trim_blocks=True,
                                lstrip_blocks=True).render(**self.context_config_toolchain)
        self._conanfile.output.info("MSBuildToolchain created %s" % config_filename)
        save(config_filepath, config_props)

    def _write_main_toolchain(self, config_filename, condition):
        main_toolchain_path = os.path.join(self._conanfile.generators_folder, self.filename)
        if os.path.isfile(main_toolchain_path):
            content = load(main_toolchain_path)
        else:
            content = textwrap.dedent("""\
                <?xml version="1.0" encoding="utf-8"?>
                <Project ToolsVersion="4.0"
                        xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
                    <ImportGroup Label="PropertySheets" >
                    </ImportGroup>
                    <PropertyGroup Label="ConanPackageInfo">
                        <ConanPackageName>{}</ConanPackageName>
                        <ConanPackageVersion>{}</ConanPackageVersion>
                    </PropertyGroup>
                </Project>
                """)

            conan_package_name = self._conanfile.name if self._conanfile.name else ""
            conan_package_version = self._conanfile.version if self._conanfile.version else ""
            content = content.format(conan_package_name, conan_package_version)

        dom = minidom.parseString(content)
        try:
            import_group = dom.getElementsByTagName('ImportGroup')[0]
        except Exception:
            raise ConanException("Broken {}. Remove the file and try again".format(self.filename))
        children = import_group.getElementsByTagName("Import")
        for node in children:
            if (config_filename == node.getAttribute("Project") and
                    condition == node.getAttribute("Condition")):
                break  # the import statement already exists
        else:  # create a new import statement
            import_node = dom.createElement('Import')
            import_node.setAttribute('Condition', condition)
            import_node.setAttribute('Project', config_filename)
            import_group.appendChild(import_node)

        conan_toolchain = dom.toprettyxml()
        conan_toolchain = "\n".join(line for line in conan_toolchain.splitlines() if line.strip())
        self._conanfile.output.info("MSBuildToolchain writing {}".format(self.filename))
        save(main_toolchain_path, conan_toolchain)

    def _get_extra_flags(self):
        # Now, it's time to get all the flags defined by the user
        cxxflags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        cflags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        sharedlinkflags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[], check_type=list)
        exelinkflags = self._conanfile.conf.get("tools.build:exelinkflags", default=[], check_type=list)
        defines = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)
        return cxxflags, cflags, defines, sharedlinkflags, exelinkflags
