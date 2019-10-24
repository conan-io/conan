import os

from conans import DEFAULT_REVISION_V1
from conans.client.graph.graph import Node, RECIPE_CONSUMER, CONTEXT_HOST
from conans.client.tools.files import save
from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.test_files import temp_folder


class Retriever(object):
    def __init__(self, loader):
        self.loader = loader
        self.folder = temp_folder()

    def root(self, content, profile):
        conan_path = os.path.join(self.folder, "data", "root.py")
        save(conan_path, content)
        conanfile = self.loader.load_consumer(conan_path, profile)
        node = Node(None, conanfile, context=CONTEXT_HOST, recipe="rootpath")
        node.recipe = RECIPE_CONSUMER
        return node

    def save_recipe(self, ref, content):
        content = str(content)
        if isinstance(ref, str):
            ref = ConanFileReference.loads(ref)
        conan_path = os.path.join(self.folder, "data", ref.dir_repr(), CONANFILE)
        save(conan_path, content)

    def get_recipe(self, ref, check_updates, update, remote_name, recorder):  # @UnusedVariable
        conan_path = os.path.join(self.folder, "data", ref.dir_repr(), CONANFILE)
        return conan_path, None, None, ref.copy_with_rev(DEFAULT_REVISION_V1)
