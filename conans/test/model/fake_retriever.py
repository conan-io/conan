import os

from conans import DEFAULT_REVISION_V1
from conans.client.graph.graph import Node
from conans.client.tools.files import save
from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.test_files import temp_folder


class Retriever(object):
    def __init__(self, loader, output):
        self.loader = loader
        self.output = output
        self.folder = temp_folder()
        self._client_cache = None

    def root(self, content, processed_profile):
        conan_path = os.path.join(self.folder, "root.py")
        save(conan_path, content)
        conanfile = self.loader.load_conanfile(conan_path, self.output, processed_profile,
                                               consumer=True)
        return Node(None, conanfile)

    def conan(self, conan_ref, content):
        if isinstance(conan_ref, str):
            conan_ref = ConanFileReference.loads(conan_ref)
        conan_path = os.path.join(self.folder, conan_ref.dir_repr(), CONANFILE)
        save(conan_path, content)

    def get_recipe(self, conan_ref, check_updates, update, remote_name, recorder):  # @UnusedVariable
        conan_path = os.path.join(self.folder, conan_ref.dir_repr(), CONANFILE)
        return conan_path, None, None, conan_ref.copy_with_rev(DEFAULT_REVISION_V1)
