import os

from collections import OrderedDict

import yaml

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.files import load, save
from conans.model.editable_cpp_info import get_editable_abs_path
from conans.client.graph.graph import RECIPE_EDITABLE


class LocalPackage(object):
    def __init__(self, base_folder, data, cache, ws_layout):
        self._base_folder = base_folder
        self._conanfile_folder = data.get("folder")  # The folder with the conanfile
        layout = data.get("layout")
        if layout:
            self.layout = get_editable_abs_path(data.get("layout"), self._base_folder,
                                                cache.conan_folder)
        else:
            self.layout = ws_layout

    @property
    def root_folder(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder))


class Workspace(object):

    def generate(self, cwd, graph):
        editables = {node.ref: node.conanfile for node in graph.nodes
                     if node.recipe == RECIPE_EDITABLE}
        if self._generator == "cmake":
            cmake = ""
            for ref, ws_pkg in self._workspace_packages.items():
                layout = self._cache.package_layout(ref)
                editable = layout.editable_cpp_info()
                conanfile = editables[ref]
                build = editable.folder(ref, "build_folder", conanfile.settings, conanfile.options)
                src = editable.folder(ref, "source_folder", conanfile.settings, conanfile.options)
                if src:
                    src = os.path.join(ws_pkg.root_folder, src).replace("\\", "/")
                    cmake += 'set(PACKAGE_%s_SRC "%s")\n' % (ref.name, src)
                if build:
                    build = os.path.join(ws_pkg.root_folder, build).replace("\\", "/")
                    cmake += 'set(PACKAGE_%s_BUILD "%s")\n' % (ref.name, build)

                if src and build:
                    cmake += ('add_subdirectory(${PACKAGE_%s_SRC} ${PACKAGE_%s_BUILD})\n'
                              % (ref.name, ref.name))
            cmake_path = os.path.join(cwd, "conanworkspace.cmake")
            save(cmake_path, cmake)

    def __init__(self, path, cache):
        self._cache = cache
        self._generator = None
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
        yml.pop("name", None)
        self._layout = yml.pop("layout", None)
        if self._layout:
            self._layout = get_editable_abs_path(self._layout, self._base_folder,
                                                 self._cache.conan_folder)
        self._root = [ConanFileReference.loads(s.strip())
                      for s in yml.pop("root", "").split(",") if s.strip()]
        if not self._root:
            raise ConanException("Conan workspace needs at least 1 root conanfile")
        for package_name, data in yml.items():
            workspace_package = LocalPackage(self._base_folder, data,
                                             self._cache, self._layout)
            package_name = ConanFileReference.loads(package_name)
            self._workspace_packages[package_name] = workspace_package
        for package_name in self._root:
            if package_name not in self._workspace_packages:
                raise ConanException("Root %s is not a local package" % package_name)
