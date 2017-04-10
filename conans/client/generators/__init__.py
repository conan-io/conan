from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator
from conans.errors import ConanException
from conans.model import registered_generators
from conans.util.files import save, normalize
from os.path import join
from .text import TXTGenerator
from .gcc import GCCGenerator
from .cmake import CMakeGenerator
from .qmake import QmakeGenerator
from .qbs import QbsGenerator
from .scons import SConsGenerator
from .visualstudio import VisualStudioGenerator
from .xcode import XCodeGenerator
from .ycm import YouCompleteMeGenerator
from .virtualenv import VirtualEnvGenerator
from .env import ConanEnvGenerator
from .cmake_multi import CMakeMultiGenerator
from .virtualbuildenv import VirtualBuildEnvGenerator


def _save_generator(name, klass):
    if name not in registered_generators:
        registered_generators.add(name, klass)

_save_generator("txt", TXTGenerator)
_save_generator("gcc", GCCGenerator)
_save_generator("cmake", CMakeGenerator)
_save_generator("cmake_multi", CMakeMultiGenerator)
_save_generator("qmake", QmakeGenerator)
_save_generator("qbs", QbsGenerator)
_save_generator("scons", SConsGenerator)
_save_generator("visual_studio", VisualStudioGenerator)
_save_generator("xcode", XCodeGenerator)
_save_generator("ycm", YouCompleteMeGenerator)
_save_generator("virtualenv", VirtualEnvGenerator)
_save_generator("env", ConanEnvGenerator)
_save_generator("virtualbuildenv", VirtualBuildEnvGenerator)
_save_generator("virtualrunenv", VirtualRunEnvGenerator)


def write_generators(conanfile, path, output):
    """ produces auxiliary files, required to build a project or a package.
    """

    for generator_name in conanfile.generators:
        if generator_name not in registered_generators:
            output.warn("Invalid generator '%s'. Available types: %s" %
                        (generator_name, ", ".join(registered_generators.available)))
        else:
            generator_class = registered_generators[generator_name]
            try:
                generator = generator_class(conanfile)
            except TypeError:
                # To allow old-style generator packages to work (e.g. premake)
                output.warn("Generator %s failed with new __init__(), trying old one")
                generator = generator_class(conanfile.deps_cpp_info, conanfile.cpp_info)

            try:
                content = generator.content
                if isinstance(content, dict):
                    if generator.filename:
                        output.warn("Generator %s is multifile. Property 'filename' not used"
                                    % (generator_name,))
                    for k, v in content.items():
                        v = normalize(v)
                        output.info("Generated %s created %s" % (generator_name, k))
                        save(join(path, k), v)
                else:
                    content = normalize(content)
                    output.info("Generated %s created %s" % (generator_name, generator.filename))
                    save(join(path, generator.filename), content)
            except Exception as e:
                output.error("Generator %s(file:%s) failed\n%s"
                             % (generator_name, generator.filename, str(e)))
                raise ConanException(e)
