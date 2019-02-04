import os
import platform
from collections import OrderedDict

import yaml

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.files import load, mkdir, save
from conans.model.editable_cpp_info import get_editable_abs_path


class LocalPackage(object):
    def __init__(self, base_folder, install_folder, data, cache, ws_layout):
        self._base_folder = base_folder
        self._install_folder = install_folder
        self._conanfile_folder = data.get("folder")  # The folder with the conanfile
        self._build_folder = data.get("build", "")
        layout = data.get("layout")
        if layout:
            self.layout = get_editable_abs_path(data.get("layout"), self._base_folder,
                                                cache.conan_folder)
        else:
            self.layout = ws_layout

        # package_folder can be None, then it will directly use build_folder
        self._package_folder = data.get("package", "")
        self._cmakedir = data.get("cmakedir")
        includedirs = data.get("includedirs", [])  # To override includedirs, mainly for build_folder
        self._includedirs = [includedirs] if not isinstance(includedirs, list) else includedirs
        libdirs = data.get("libdirs", [])  # To override libdirs...
        self._libdirs = [libdirs] if not isinstance(libdirs, list) else libdirs

    @property
    def root_folder(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder))

    @property
    def conanfile_path(self):
        return os.path.join(self.root_folder, "conanfile.py")

    def build_folder(self, conanfile):
        folder = self._evaluate(self._build_folder, conanfile)
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

    def _evaluate(self, value, conanfile):
        settings = conanfile.settings
        v = value.format(build_type=settings.get_safe("build_type"),
                         arch=settings.get_safe("arch"),
                         os=platform.system())
        try:
            result = eval('%s' % v)
        except Exception:
            result = v
        return result

    @property
    def local_cmakedir(self):
        if not self._cmakedir:
            return self._conanfile_folder
        return os.path.join(self._conanfile_folder, self._cmakedir).replace("\\", "/")


class Workspace(object):

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
                cmake += 'add_subdirectory(%s "%s")\n' % (workspace_package.local_cmakedir,
                                                          build_folder)
            cmake_path = os.path.join(self._base_folder, "CMakeLists.txt")
            if os.path.exists(cmake_path) and not load(cmake_path).startswith("# conanws"):
                raise ConanException("Can't generate CMakeLists.txt, will overwrite existing one")
            save(cmake_path, cmake)

    def __init__(self, path, install_folder, cache):
        self._cache = cache
        self._install_folder = install_folder
        self._generator = None
        self._name = "ConanWorkspace"
        self._workspace_packages = OrderedDict()  # {reference: LocalPackage}
        self._base_folder = os.path.dirname(path)
        try:
            content = load(path)
        except IOError:
            raise ConanException("Couldn't load workspace file in %s" % path)
        try:
            self._loads(content)
        except Exception as e:
            raise ConanException("There was an error parsing %s: %s" % (path, str(e)))

    def get_editable_dict(self):
        return {ref: {"path": ws_package.root_folder, "layout": ws_package.layout}
                for ref, ws_package in self._workspace_packages.items()}

    def __getitem__(self, ref):
        return self._workspace_packages.get(ref)

    @property
    def root(self):
        return self._root

    def _loads(self, text):
        yml = yaml.safe_load(text)
        self._generator = yml.pop("generator", None)
        self._name = yml.pop("name", None)
        self._layout = yml.pop("layout", None)
        if self._layout:
            self._layout = get_editable_abs_path(self._layout, self._base_folder,
                                                 self._cache.conan_folder)
        self._root = [ConanFileReference.loads(s.strip())
                      for s in yml.pop("root", "").split(",") if s.strip()]
        if not self._root:
            raise ConanException("Conan workspace needs at least 1 root conanfile")
        for package_name, data in yml.items():
            workspace_package = LocalPackage(self._base_folder, self._install_folder, data,
                                             self._cache, self._layout)
            package_name = ConanFileReference.loads(package_name)
            self._workspace_packages[package_name] = workspace_package
        for package_name in self._root:
            if package_name not in self._workspace_packages:
                raise ConanException("Root %s is not a local package" % package_name)
