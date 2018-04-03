from collections import OrderedDict
from conans.errors import ConanException
import os
from conans.util.files import load, save
import yaml


class LocalPackage(object):
    def __init__(self, base_folder, data):
        self._base_folder = base_folder
        self._conanfile_folder = data.get("folder")  # The folder with the conanfile
        self._source_folder = ""  # By default the conanfile_folder
        self._build_folder = data.get("build", "build_{build_type}_{arch}")
        # package_folder can be None, then it will directly use build_folder
        self._package_folder = data.get("package", "package_{build_type}_{arch}")
        includedirs = data.get("includedirs")  # To override include dirs, mainly for build_folder
        self._includedirs = [includedirs] if not isinstance(includedirs, list) else includedirs
        libdirs = data.get("libdirs")  # To override libdirs...
        self._libdirs = [libdirs] if not isinstance(libdirs, list) else libdirs

    @property
    def conanfile_path(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, "conanfile.py"))

    def includedirs(self, settings):
        return [self._evaluate(v, settings) for v in self._includedirs]

    def libdirs(self, settings):
        return [self._evaluate(v, settings) for v in self._libdirs]

    def _evaluate(self, value, settings):
        return value.format(build_type=settings.get_safe("build_type"),
                            arch=settings.get_safe("arch"))

    def local_package_path(self, settings):
        package = self._evaluate(self._package_folder, settings)
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, package))

    def local_build_path(self, settings):
        build = self._evaluate(self._build_folder, settings)
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder, build))


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
        return ConanProject(None)

    def generate(self):
        # FIXME: SHITTY I NEED THE settings
        if self._generator == "cmake":
            template = """# conan-project
cmake_minimum_version(3.0)
project({name} CXX)

"""
            cmake = template.format(name=self._name)
            for _, local_package in self._local_packages.items():
                build_folder = "/".join([local_package._conanfile_folder, local_package._build_folder])
                cmake += "add_subdirectory(%s %s)\n" % (local_package._conanfile_folder, build_folder)
            cmake_path = os.path.join(self._base_folder, "CMakeLists.txt")
            if os.path.exists(cmake_path) and not load(cmake_path).startswith("# conan-project"):
                raise ConanException("Can't generate CMakeLists.txt, will overwrite existingone")
            save(cmake_path, cmake)

    def __init__(self, path):
        self._generator = None
        self._name = "conan-project"
        self._local_packages = OrderedDict()  # {reference: LocalPackage}
        if not path:
            return
        self._base_folder = os.path.dirname(path)
        content = load(path)
        self._loads(content)

    def __getitem__(self, reference):
        return self._local_packages.get(reference.name)

    def _loads(self, text):
        try:
            yml = yaml.load(text)
            self._generator = yml.pop("generator", None)
            self._name = yml.pop("name", None)
            for package_name, data in yml.items():
                local_package = LocalPackage(self._base_folder, data)
                self._local_packages[package_name] = local_package
        except Exception as e:
            raise ConanException("There was an error parsing conan-project: %s" % str(e))
