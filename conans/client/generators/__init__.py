from os.path import join

from conans.client.generators.cmake_find_package import CMakeFindPackageGenerator
from conans.client.generators.compiler_args import CompilerArgsGenerator
from conans.client.generators.pkg_config import PkgConfigGenerator
from conans.errors import ConanException
from conans.util.files import save, normalize

from .virtualrunenv import VirtualRunEnvGenerator
from .text import TXTGenerator
from .gcc import GCCGenerator
from .cmake import CMakeGenerator
from .cmake_paths import CMakePathsGenerator
from .cmake_multi import CMakeMultiGenerator
from .qmake import QmakeGenerator
from .qbs import QbsGenerator
from .scons import SConsGenerator
from .visualstudio import VisualStudioGenerator
from .visualstudio_multi import VisualStudioMultiGenerator
from .visualstudiolegacy import VisualStudioLegacyGenerator
from .xcode import XCodeGenerator
from .ycm import YouCompleteMeGenerator
from .virtualenv import VirtualEnvGenerator
from .virtualbuildenv import VirtualBuildEnvGenerator
from .boostbuild import BoostBuildGenerator
from .json_generator import JsonGenerator
import traceback
from conans.util.env_reader import get_env
from .b2 import B2Generator


class _GeneratorManager(object):
    def __init__(self):
        self._generators = {}

    def add(self, name, generator_class):
        if name not in self._generators:
            self._generators[name] = generator_class

    @property
    def available(self):
        return list(self._generators.keys())

    def __contains__(self, name):
        return name in self._generators

    def __getitem__(self, key):
        return self._generators[key]


registered_generators = _GeneratorManager()

registered_generators.add("txt", TXTGenerator)
registered_generators.add("gcc", GCCGenerator)
registered_generators.add("compiler_args", CompilerArgsGenerator)
registered_generators.add("cmake", CMakeGenerator)
registered_generators.add("cmake_multi", CMakeMultiGenerator)
registered_generators.add("cmake_paths", CMakePathsGenerator)
registered_generators.add("cmake_find_package", CMakeFindPackageGenerator)
registered_generators.add("qmake", QmakeGenerator)
registered_generators.add("qbs", QbsGenerator)
registered_generators.add("scons", SConsGenerator)
registered_generators.add("visual_studio", VisualStudioGenerator)
registered_generators.add("visual_studio_multi", VisualStudioMultiGenerator)
registered_generators.add("visual_studio_legacy", VisualStudioLegacyGenerator)
registered_generators.add("xcode", XCodeGenerator)
registered_generators.add("ycm", YouCompleteMeGenerator)
registered_generators.add("virtualenv", VirtualEnvGenerator)
registered_generators.add("virtualbuildenv", VirtualBuildEnvGenerator)
registered_generators.add("virtualrunenv", VirtualRunEnvGenerator)
registered_generators.add("boost-build", BoostBuildGenerator)
registered_generators.add("pkg_config", PkgConfigGenerator)
registered_generators.add("json", JsonGenerator)
registered_generators.add("b2", B2Generator)


def write_generators(conanfile, path, output):
    """ produces auxiliary files, required to build a project or a package.
    """
    for generator_name in conanfile.generators:
        try:
            generator_class = registered_generators[generator_name]
        except KeyError:
            raise ConanException("Invalid generator '%s'. Available types: %s" %
                                 (generator_name, ", ".join(registered_generators.available)))
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
