from conans.model import registered_generators
from os.path import join
from .text import TXTGenerator
from .gcc import GCCGenerator
from .cmake import CMakeGenerator
from .qmake import QMakeGenerator
from .visualstudio import VisualStudioGenerator
from .xcode import XCodeGenerator
from .ycm import YouCompleteMeGenerator


registered_generators.add("txt", TXTGenerator)
registered_generators.add("gcc", GCCGenerator)
registered_generators.add("cmake", CMakeGenerator)
registered_generators.add("qmake", QmakeGenerator)
registered_generators.add("visual_studio", VisualStudioGenerator)
registered_generators.add("xcode", XCodeGenerator)
registered_generators.add("ycm", YouCompleteMeGenerator)


def write_generators(conanfile, path, output):
    """ produces auxiliary files, required to build a project or a package.
    """

    from conans.model.build_info import CppInfo

    conanfile.cpp_info = CppInfo(path)
    conanfile.cpp_info.dependencies = []
    conanfile.package_info()

    for generator_name in conanfile.generators:
        if generator not in registered_generators:
            output.warn("Invalid generator '%s'. Available types: %s" %
                        (generator_name, ", ".join(registered_generators.available)))
        else:
            generator_class = registered_generators[generator_name]
            generator = generator_class(conanfile.deps_cpp_info, conanfile.cpp_info)
            output.info("Generated %s created %s" % (generator_name, generator.filename))
            save(join(path, generator.filename), generator.content)
