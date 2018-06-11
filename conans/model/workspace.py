import platform
import os
import yaml

from collections import OrderedDict

from conans.errors import ConanException
from conans.util.files import load, save, mkdir
from conans.model.ref import ConanFileReference


class LocalPackage(object):
    def __init__(self, base_folder, install_folder, data):
        self._base_folder = base_folder
        self._install_folder = install_folder
        self._conanfile_folder = data.get("folder")  # The folder with the conanfile
        self._source_folder = data.get("source")  # By default the conanfile_folder
        self._build_folder = data.get("build", "")
        # package_folder can be None, then it will directly use build_folder
        self._package_folder = data.get("package", "")
        self._cmakedir = data.get("cmakedir")
        includedirs = data.get("includedirs", [])  # To override include dirs, mainly for build_folder
        self._includedirs = [includedirs] if not isinstance(includedirs, list) else includedirs
        libdirs = data.get("libdirs", [])  # To override libdirs...
        self._libdirs = [libdirs] if not isinstance(libdirs, list) else libdirs
        self.conanfile = None

    @property
    def root_folder(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder))

    @property
    def conanfile_path(self):
        return os.path.join(self.root_folder, "conanfile.py")

    @property
    def build_folder(self):
        folder = self._evaluate(self._build_folder)
        if self._install_folder:
            pkg_folder = os.path.join(self._install_folder, self._conanfile_folder, folder)
        else:
            pkg_folder = os.path.join(self.root_folder, folder)
        mkdir(pkg_folder)
        return pkg_folder

    @property
    def package_folder(self):
        folder = self._evaluate(self._package_folder)
        if self._install_folder:
            pkg_folder = os.path.join(self._install_folder, self._conanfile_folder, folder)
        else:
            pkg_folder = os.path.join(self.root_folder, folder)
        mkdir(pkg_folder)
        return pkg_folder

    @property
    def install_folder(self):
        return self._evaluate(self._install_folder)

    @property
    def includedirs(self):
        return [os.path.join(self._base_folder, self._conanfile_folder, v)
                for v in self._includedirs]

    @property
    def libdirs(self):
        return [self._evaluate(v) for v in self._libdirs]

    def _evaluate(self, value):
        settings = self.conanfile.settings
        v = value.format(build_type=settings.get_safe("build_type"),
                         arch=settings.get_safe("arch"),
                         os=platform.system())
        try:
            result = eval('%s' % v)
        except:
            result = v
        return result

    @property
    def local_cmakedir(self):
        if not self._cmakedir:
            return self._conanfile_folder
        return os.path.join(self._conanfile_folder, self._cmakedir).replace("\\", "/")


WORKSPACE_FILE = "conanws.yml"


class Workspace(object):
    @staticmethod
    def get_workspace(folder, install_folder):
        if isinstance(folder, ConanFileReference):
            return None
        if not os.path.exists(folder):
            return None
        path = os.path.join(folder, WORKSPACE_FILE)
        if os.path.exists(path):
            return Workspace(path, install_folder)
        parent = os.path.dirname(folder)
        if parent and parent != folder:
            return Workspace.get_workspace(parent, install_folder)
        return None

    def generate(self):
        if self._generator == "cmake":
            template = """# conanws
cmake_minimum_required(VERSION 3.3)
project({name} CXX)

"""
            cmake = template.format(name=self._name)
            for _, workspace_package in self._workspace_packages.items():
                build_folder = workspace_package.build_folder
                build_folder = build_folder.replace("\\", "/")
                cmake += 'add_subdirectory(%s "%s")\n' % (workspace_package.local_cmakedir, build_folder)
            cmake_path = os.path.join(self._base_folder, "CMakeLists.txt")
            if os.path.exists(cmake_path) and not load(cmake_path).startswith("# conanws"):
                raise ConanException("Can't generate CMakeLists.txt, will overwrite existing one")
            save(cmake_path, cmake)

    def __init__(self, path, install_folder):
        self._install_folder = install_folder
        self._generator = None
        self._name = "ConanWorkspace"
        self._workspace_packages = OrderedDict()  # {reference: LocalPackage}
        if not path:
            return
        self._base_folder = os.path.dirname(path)
        content = load(path)
        self._loads(content)

    def __getitem__(self, reference):
        return self._workspace_packages.get(reference.name)

    @property
    def root(self):
        return self._root

    def _loads(self, text):
        try:
            yml = yaml.load(text)
            self._generator = yml.pop("generator", None)
            self._name = yml.pop("name", None)
            self._root = [s.strip() for s in yml.pop("root", "").split(",") if s.strip()]
            if not self._root:
                raise ConanException("Conan workspace needs at least 1 root conanfile")
            for package_name, data in yml.items():
                workspace_package = LocalPackage(self._base_folder, self._install_folder, data)
                self._workspace_packages[package_name] = workspace_package
            for package_name in self._root:
                if package_name not in self._workspace_packages:
                    raise ConanException("Root %s is not a local package" % package_name)
        except Exception as e:
            raise ConanException("There was an error parsing %s: %s" % (WORKSPACE_FILE, str(e)))
