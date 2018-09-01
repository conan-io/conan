import os

from conans.test.utils.test_files import temp_folder
from conans.model.ref import ConanFileReference
from conans.tools import save
from conans.paths import CONANFILE


class Retriever(object):
    def __init__(self, loader, output):
        self.loader = loader
        self.output = output
        self.folder = temp_folder()

    def root(self, content, processed_profile):
        conan_path = os.path.join(self.folder, "root.py")
        save(conan_path, content)
        conanfile = self.loader.load_conanfile(conan_path, self.output, processed_profile, consumer=True)
        return conanfile

    def conan(self, conan_ref, content):
        if isinstance(conan_ref, str):
            conan_ref = ConanFileReference.loads(conan_ref)
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        save(conan_path, content)

    def get_recipe(self, conan_ref, check_updates, update, remote_name, recorder):  # @UnusedVariable
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        return conan_path, None, None, conan_ref
