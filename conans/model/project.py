from collections import OrderedDict
from conans.errors import ConanException
import os
from conans.util.files import load
import yaml


class LocalPackage(object):
    def __init__(self, base_folder, data):
        self._base_folder = base_folder
        self._conanfile_folder = data.get("folder")  # The folder with the conanfile
        self._source_folder = ""  # By default the conanfile_folder
        self._build_folder = "build_{settings.build_type}_{settings.arch}"
        # package_folder can be None, then it will directly use build_folder
        self._package_folder = "package_{settings.build_type}_{settings.arch}"
        includedirs = data.get("includedirs")  # To override include dirs, mainly for build_folder
        self._includedirs = [includedirs] if not isinstance(includedirs, list) else includedirs
        libdirs = data.get("libdirs")  # To override libdirs...
        self._libdirs = [libdirs] if not isinstance(libdirs, list) else libdirs

    @property
    def conanfile_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "conanfile.py"))

    @property
    def package_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "package"))

    @property
    def build_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "build"))


CONAN_PROJECT = "conan-project.yml"


class ConanProject(object):
    @staticmethod
    def get_conan_project(folder):
        if not os.path.exists(folder):
            return None
        path = os.path.join(folder, CONAN_PROJECT)
        if os.path.exists(path):
            return ConanProject(path)
        parent = os.path.dirname(folder)
        if parent and parent != folder:
            return ConanProject.get_conan_project(parent)

    def __init__(self, path):
        self._base_folder = os.path.dirname(path)
        self._local_packages = OrderedDict()  # {reference: LocalPackage}
        content = load(path)
        self._loads(content)

    def __getitem__(self, reference):
        return self._local_packages.get(reference.name)

    def _loads(self, text):
        try:
            yml = yaml.load(text)
            for package_name, data in yml.items():
                local_package = LocalPackage(self._base_folder, data)
                self._local_packages[package_name] = local_package
        except Exception as e:
            raise ConanException("There was an error parsing conan-project: %s" % str(e))
