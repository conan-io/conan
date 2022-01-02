import os
import textwrap
from xml.dom import minidom

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.build import build_jobs
from conan.tools.intel.intel_cc import IntelCC
from conan.tools.microsoft.visual import VCVars
from conans.errors import ConanException
from conans.util.files import save, load


class MSBuildToolchain(object):

    filename = "conantoolchain.props"

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.preprocessor_definitions = {}
        self.compile_options = {}
        self.configuration = conanfile.settings.build_type
        self.runtime_library = self._runtime_library(conanfile.settings)
        self.cppstd = conanfile.settings.get_safe("compiler.cppstd")
        self.toolset = self._msvs_toolset(conanfile)
        check_using_build_profile(self._conanfile)

    def _name_condition(self, settings):
        props = [("Configuration", self.configuration),
                 # FIXME: This probably requires mapping ARM architectures
                 ("Platform", {'x86': 'Win32',
                               'x86_64': 'x64'}.get(settings.get_safe("arch")))]

        name = "".join("_%s" % v for _, v in props if v is not None)
        condition = " And ".join("'$(%s)' == '%s'" % (k, v) for k, v in props if v is not None)
        return name.lower(), condition

    def generate(self):
        name, condition = self._name_condition(self._conanfile.settings)
        config_filename = "conantoolchain{}.props".format(name)
        self._write_config_toolchain(config_filename)
        self._write_main_toolchain(config_filename, condition)
        if self._conanfile.settings.get_safe("compiler") == "intel-cc":
            IntelCC(self._conanfile).generate()
        else:
            VCVars(self._conanfile).generate()

    @staticmethod
    def _msvs_toolset(conanfile):
        settings = conanfile.settings
        compiler = settings.get_safe("compiler")
        compiler_version = settings.get_safe("compiler.version")
        if compiler == "msvc":
            toolsets = {'190': 'v140',  # TODO: This is common to CMake, refactor
                        '191': 'v141',
                        '192': 'v142',
                        "193": 'v143'}
            return toolsets[compiler_version]
        if compiler == "intel":
            compiler_version = compiler_version if "." in compiler_version else \
                "%s.0" % compiler_version
            return "Intel C++ Compiler " + compiler_version
        if compiler == "intel-cc":
            return IntelCC(conanfile).ms_toolset
        if compiler == "Visual Studio":
            toolset = settings.get_safe("compiler.toolset")
            if not toolset:
                toolsets = {"17": "v143",
                            "16": "v142",
                            "15": "v141",
                            "14": "v140",
                            "12": "v120",
                            "11": "v110",
                            "10": "v100",
                            "9": "v90",
                            "8": "v80"}
                toolset = toolsets.get(compiler_version)
            return toolset or ""

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

    def _write_config_toolchain(self, config_filename):

        def format_macro(key, value):
            return '%s=%s' % (key, value) if value is not None else key

        toolchain_file = textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ItemDefinitionGroup>
                <ClCompile>
                  <PreprocessorDefinitions>
                     {};%(PreprocessorDefinitions)
                  </PreprocessorDefinitions>
                  <RuntimeLibrary>{}</RuntimeLibrary>
                  <LanguageStandard>{}</LanguageStandard>{}{}
                </ClCompile>
                <ResourceCompile>
                  <PreprocessorDefinitions>
                     {};%(PreprocessorDefinitions)
                  </PreprocessorDefinitions>
                </ResourceCompile>
              </ItemDefinitionGroup>
              <PropertyGroup Label="Configuration">
                <PlatformToolset>{}</PlatformToolset>
              </PropertyGroup>
            </Project>
            """)
        preprocessor_definitions = ";".join([format_macro(k, v)
                                             for k, v in self.preprocessor_definitions.items()])

        cppstd = "stdcpp%s" % self.cppstd if self.cppstd else ""
        runtime_library = self.runtime_library
        toolset = self.toolset
        compile_options = self._conanfile.conf["tools.microsoft.msbuildtoolchain:compile_options"]
        if compile_options is not None:
            compile_options = eval(compile_options)
            self.compile_options.update(compile_options)
        parallel = ""
        njobs = build_jobs(self._conanfile)
        if njobs:
            parallel = "".join(
                ["\n      <MultiProcessorCompilation>True</MultiProcessorCompilation>",
                 "\n      <ProcessorNumber>{}</ProcessorNumber>".format(njobs)])
        compile_options = "".join("\n      <{k}>{v}</{k}>".format(k=k, v=v)
                                  for k, v in self.compile_options.items())
        config_props = toolchain_file.format(preprocessor_definitions, runtime_library, cppstd,
                                             parallel, compile_options, preprocessor_definitions,
                                             toolset)
        config_filepath = os.path.join(self._conanfile.generators_folder, config_filename)
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
