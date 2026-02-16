import os

from conan.api.output import Color
from conan.internal import check_duplicated_generator
from conan.tools.files import save
from conan.tools.zig.setup import SetupTemplate
from conan.tools.zig.deps import DepsTemplate


class ZigDeps:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self):
        """
        This method will save the generated files to the ``conanfile.generators_folder`` folder
        """
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(self._conanfile, os.path.join("conan_zig_deps", generator_file), content)

    def _content(self):
        ret = {}
        dep = DepsTemplate(self, self._conanfile)
        ret[dep.filename] = dep.content()
        setup = SetupTemplate(self, self._conanfile)
        ret[setup.filename] = setup.content()
        return ret
