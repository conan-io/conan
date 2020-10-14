import traceback
from os.path import join

from conans.client.generators.cmake_find_package import CMakeFindPackageGenerator
from conans.client.generators.cmake_find_package_multi import CMakeFindPackageMultiGenerator
from conans.client.generators.compiler_args import CompilerArgsGenerator
from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.errors import ConanException
from conans.util.env_reader import get_env
from conans.util.files import normalize, save
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
from .msbuild import MSBuildGenerator
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
                            "msbuild": MSBuildGenerator,
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

    def add(self, name, generator_class, custom=False):
        if name not in self._generators or custom:
            self._generators[name] = generator_class

    @property
    def available(self):
        return list(self._generators.keys())

    def __contains__(self, name):
        return name in self._generators

    def __getitem__(self, key):
        return self._generators[key]

    def write_generators(self, conanfile, path, output):
        """ produces auxiliary files, required to build a project or a package.
        """
        for generator_name in set(conanfile.generators):
            try:
                generator_class = self._generators[generator_name]
            except KeyError:
                raise ConanException("Invalid generator '%s'. Available types: %s" %
                                     (generator_name, ", ".join(self.available)))
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
