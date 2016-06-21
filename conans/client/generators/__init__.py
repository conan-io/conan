from conans.model import registered_generators
from conans.util.files import save, normalize
from os.path import join
from .text import TXTGenerator
from .gcc import GCCGenerator
from .cmake import CMakeGenerator
from .qmake import QmakeGenerator
from .qbs import QbsGenerator
from .visualstudio import VisualStudioGenerator
from .xcode import XCodeGenerator
from .ycm import YouCompleteMeGenerator


def _save_generator(name, klass):
    if name not in registered_generators:
        registered_generators.add(name, klass)

_save_generator("txt", TXTGenerator)
_save_generator("gcc", GCCGenerator)
_save_generator("cmake", CMakeGenerator)
_save_generator("qmake", QmakeGenerator)
_save_generator("qbs", QbsGenerator)
_save_generator("visual_studio", VisualStudioGenerator)
_save_generator("xcode", XCodeGenerator)
_save_generator("ycm", YouCompleteMeGenerator)


def write_generators(conanfile, path, output):
    """ produces auxiliary files, required to build a project or a package.
    """

    from conans.model.build_info import CppInfo

    conanfile.cpp_info = CppInfo(path)
    conanfile.cpp_info.dependencies = []
    conanfile.package_info()

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
            content = normalize(generator.content)
            if isinstance(content, basestring) and not generator.filename is None:
                output.info("Generated %s created %s" % (generator_name, generator.filename))
                save(join(path, generator.filename), content)
            elif isinstance(content, dict):
                for k, v in content.iteritems():
                    output.info("Generated %s created %s" % (generator_name, k))
                    save(join(path, k), v)
            else:
                output.warn("Generator %s didn't generate anything" % generator_name)

