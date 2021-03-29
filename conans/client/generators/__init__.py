import traceback
from os.path import join

from conans.client.generators.cmake_find_package import CMakeFindPackageGenerator
from conans.client.generators.cmake_find_package_multi import CMakeFindPackageMultiGenerator
from conans.client.generators.compiler_args import CompilerArgsGenerator
from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.errors import ConanException, conanfile_exception_formatter
from conans.util.env_reader import get_env
from conans.util.files import normalize, save, mkdir
from .b2 import B2Generator
from .boostbuild import BoostBuildGenerator
from .cmake import CMakeGenerator
from .cmake_multi import CMakeMultiGenerator
from .cmake_paths import CMakePathsGenerator
from .deploy import DeployGenerator
from .gcc import GCCGenerator
from .json_generator import JsonGenerator
from .make import MakeGenerator
from .markdown import MarkdownGenerator
from .premake import PremakeGenerator
from .qbs import QbsGenerator
from .qmake import QmakeGenerator
from .scons import SConsGenerator
from .text import TXTGenerator
from .virtualbuildenv import VirtualBuildEnvGenerator
from .virtualenv import VirtualEnvGenerator
from .virtualenv_python import VirtualEnvPythonGenerator
from .virtualrunenv import VirtualRunEnvGenerator
from .visualstudio import VisualStudioGenerator
from .visualstudio_multi import VisualStudioMultiGenerator
from .visualstudiolegacy import VisualStudioLegacyGenerator
from .xcode import XCodeGenerator
from .ycm import YouCompleteMeGenerator
from ..tools import chdir


class GeneratorManager(object):
    def __init__(self):
        self._generators = {"txt": TXTGenerator,
                            "gcc": GCCGenerator,
                            "compiler_args": CompilerArgsGenerator,
                            "cmake": CMakeGenerator,
                            "cmake_multi": CMakeMultiGenerator,
                            "cmake_paths": CMakePathsGenerator,
                            "cmake_find_package": CMakeFindPackageGenerator,
                            "cmake_find_package_multi": CMakeFindPackageMultiGenerator,
                            "qmake": QmakeGenerator,
                            "qbs": QbsGenerator,
                            "scons": SConsGenerator,
                            "visual_studio": VisualStudioGenerator,
                            "visual_studio_multi": VisualStudioMultiGenerator,
                            "visual_studio_legacy": VisualStudioLegacyGenerator,
                            "xcode": XCodeGenerator,
                            "ycm": YouCompleteMeGenerator,
                            "virtualenv": VirtualEnvGenerator,
                            "virtualenv_python": VirtualEnvPythonGenerator,
                            "virtualbuildenv": VirtualBuildEnvGenerator,
                            "virtualrunenv": VirtualRunEnvGenerator,
                            "boost-build": BoostBuildGenerator,
                            "pkg_config": PkgConfigGenerator,
                            "json": JsonGenerator,
                            "b2": B2Generator,
                            "premake": PremakeGenerator,
                            "make": MakeGenerator,
                            "deploy": DeployGenerator,
                            "markdown": MarkdownGenerator}
        self._new_generators = ["CMakeToolchain", "CMakeDeps", "MakeToolchain", "MSBuildToolchain",
                                "MesonToolchain", "MSBuildDeps", "QbsToolchain", "msbuild",
                                "VirtualEnv", "AutotoolsDeps", "AutotoolsToolchain", "AutotoolsGen"]

    def add(self, name, generator_class, custom=False):
        if name not in self._generators or custom:
            self._generators[name] = generator_class

    def __contains__(self, name):
        return name in self._generators

    def __getitem__(self, key):
        return self._generators[key]

    def _new_generator(self, generator_name, output):
        if generator_name not in self._new_generators:
            return
        if generator_name in self._generators:  # Avoid colisions with user custom generators
            msg = ("******* Your custom generator name '{}' is colliding with a new experimental "
                   "built-in one. It is recommended to rename it. *******".format(generator_name))
            output.warn(msg)
            return
        if generator_name == "CMakeToolchain":
            from conan.tools.cmake import CMakeToolchain
            return CMakeToolchain
        elif generator_name == "CMakeDeps":
            from conan.tools.cmake import CMakeDeps
            return CMakeDeps
        elif generator_name == "MakeToolchain":
            from conan.tools.gnu import MakeToolchain
            return MakeToolchain
        elif generator_name == "AutotoolsDeps":
            from conan.tools.gnu import AutotoolsDeps
            return AutotoolsDeps
        elif generator_name == "AutotoolsToolchain":
            from conan.tools.gnu import AutotoolsToolchain
            return AutotoolsToolchain
        elif generator_name == "AutotoolsGen":
            from conan.tools.gnu import AutotoolsGen
            return AutotoolsGen
        elif generator_name == "MSBuildToolchain":
            from conan.tools.microsoft import MSBuildToolchain
            return MSBuildToolchain
        elif generator_name == "MesonToolchain":
            from conan.tools.meson import MesonToolchain
            return MesonToolchain
        elif generator_name in ("MSBuildDeps", "msbuild"):
            from conan.tools.microsoft import MSBuildDeps
            return MSBuildDeps
        elif generator_name == "CMakeDeps":
            from conan.tools.cmake import CMakeDeps
            return CMakeDeps
        elif generator_name == "QbsToolchain" or generator_name == "QbsProfile":
            from conan.tools.qbs.qbsprofile import QbsProfile
            return QbsProfile
        elif generator_name == "VirtualEnv":
            from conan.tools.env.virtualenv import VirtualEnv
            return VirtualEnv
        else:
            raise ConanException("Internal Conan error: Generator '{}' "
                                 "not commplete".format(generator_name))

    def write_generators(self, conanfile, path, output):
        """ produces auxiliary files, required to build a project or a package.
        """
        for generator_name in set(conanfile.generators):
            generator_class = self._new_generator(generator_name, output)
            if generator_class:
                if generator_name == "msbuild":
                    msg = (
                        "\n*****************************************************************\n"
                        "******************************************************************\n"
                        "'msbuild' has been deprecated and moved.\n"
                        "It will be removed in next Conan release.\n"
                        "Use 'MSBuildDeps' method instead.\n"
                        "********************************************************************\n"
                        "********************************************************************\n")
                    from conans.client.output import Color
                    output.writeln(msg, front=Color.BRIGHT_RED)
                try:
                    generator = generator_class(conanfile)
                    output.highlight("Generator '{}' calling 'generate()'".format(generator_name))
                    generator.output_path = path
                    mkdir(path)
                    with chdir(path):
                        generator.generate()
                    continue
                except Exception as e:
                    raise ConanException("Error in generator '{}': {}".format(generator_name,
                                                                              str(e)))

            try:
                generator_class = self._generators[generator_name]
            except KeyError:
                available = list(self._generators.keys()) + self._new_generators
                raise ConanException("Invalid generator '%s'. Available types: %s" %
                                     (generator_name, ", ".join(available)))
            try:
                generator = generator_class(conanfile)
            except TypeError:
                # To allow old-style generator packages to work (e.g. premake)
                output.warn("Generator %s failed with new __init__(), trying old one")
                generator = generator_class(conanfile.deps_cpp_info, conanfile.cpp_info)

            try:
                generator.output_path = path
                content = generator.content
                if isinstance(content, dict):
                    if generator.filename:
                        output.warn("Generator %s is multifile. Property 'filename' not used"
                                    % (generator_name,))
                    for k, v in content.items():
                        if generator.normalize:  # To not break existing behavior, to be removed 2.0
                            v = normalize(v)
                        output.info("Generator %s created %s" % (generator_name, k))
                        save(join(path, k), v, only_if_modified=True)
                else:
                    content = normalize(content)
                    output.info("Generator %s created %s" % (generator_name, generator.filename))
                    save(join(path, generator.filename), content, only_if_modified=True)
            except Exception as e:
                if get_env("CONAN_VERBOSE_TRACEBACK", False):
                    output.error(traceback.format_exc())
                output.error("Generator %s(file:%s) failed\n%s"
                             % (generator_name, generator.filename, str(e)))
                raise ConanException(e)


def write_toolchain(conanfile, path, output):
    if hasattr(conanfile, "toolchain"):
        msg = ("\n*****************************************************************\n"
               "******************************************************************\n"
               "The 'toolchain' attribute or method has been deprecated and removed\n"
               "Use 'generators = \"ClassName\"' or 'generate()' method instead.\n"
               "********************************************************************\n"
               "********************************************************************\n")
        raise ConanException(msg)

    if hasattr(conanfile, "generate"):
        output.highlight("Calling generate()")
        with chdir(path):
            with conanfile_exception_formatter(str(conanfile), "generate"):
                conanfile.generate()

    # tools.env.virtualenv:auto_use will be always True in Conan 2.0
    if conanfile.conf["tools.env.virtualenv"].auto_use and conanfile.virtualenv:
        with chdir(path):
            from conan.tools.env.virtualenv import VirtualEnv
            env = VirtualEnv(conanfile)
            env.generate()
