import unittest
from conans.test.tools import TestBufferConanOutput
from conans.paths import CONANFILE
import os
from conans.client.deps_builder import DepsBuilder
from conans.model.ref import ConanFileReference
from conans.model.options import OptionsValues
from conans.client.loader import ConanFileLoader
from conans.util.files import save
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.client.installer import init_cpp_info


class Retriever(object):
    def __init__(self, loader, output):
        self.loader = loader
        self.output = output
        self.folder = temp_folder()

    def _libs(self, name):
        if name == "LibPNG":
            libs = '"m"'
        elif name == "SDL2":
            libs = '"m", "rt", "pthread", "dl"'
        else:
            libs = ""
        return libs

    def root(self, name, requires=None):
        content = base_content % (name, self._reqs(requires), name, self._libs(name))
        conan_path = os.path.join(self.folder, "root")
        save(conan_path, content)
        conanfile = self.loader.load_conan(conan_path, self.output, consumer=True)
        return conanfile

    def _ref(self, name):
        return ConanFileReference.loads(name+"package/1.0@lasote/testing")

    def _reqs(self, reqs):
        reqs = reqs or []
        return ", ".join('"%s"' % str(self._ref(r)) for r in reqs)

    def conan(self, name, requires=None):
        conan_ref = self._ref(name)
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        content = base_content % (name, self._reqs(requires), name, self._libs(name))
        save(conan_path, content)

    def get_conanfile(self, conan_ref):
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        return conan_path

    def package(self, conan_reference):
        return "PATH_TO:%s" % (str(conan_reference))

base_content = """
from conans import ConanFile

class PackageConan(ConanFile):
    name = "%s"
    version = "0.1"
    requires = (%s)
    generators = "cmake"

    def package_info(self):
        self.cpp_info.libs = ["%s", %s]
"""


class ConanRequirementsTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, Settings.loads(""),
                                      OptionsValues.loads(""))
        self.retriever = Retriever(self.loader, self.output)
        self.builder = DepsBuilder(self.retriever, self.output, self.loader)


    def test_diamond_no_conflict(self):
        self.retriever.conan("ZLib")
        self.retriever.conan("BZip2")
        self.retriever.conan("SDL2", ["ZLib"])
        self.retriever.conan("LibPNG", ["ZLib"])
        self.retriever.conan("freeType", ["BZip2", "LibPNG"])
        self.retriever.conan("SDL2_ttf", ["freeType", "SDL2"])
        root = self.retriever.root("MyProject", ["SDL2_ttf"])
        deps_graph = self.builder.load(None, root)
        init_cpp_info(deps_graph, self.retriever)
        bylevel = deps_graph.propagate_buildinfo()
        E = bylevel[-1][0]
        self.assertEqual(E.conanfile.deps_cpp_info.libs,
                         ['SDL2_ttf', 'SDL2', 'rt', 'pthread', 'dl', 'freeType',
                          'BZip2', 'LibPNG', 'm', 'ZLib'])



