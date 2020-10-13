import os
from collections import OrderedDict

import yaml

from conans.client.graph.graph import RECIPE_EDITABLE
from conans.errors import ConanException
from conans.model.editable_layout import get_editable_abs_path, EditableLayout
from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.util.files import load, save


class LocalPackage(object):
    def __init__(self, base_folder, data, cache, ws_layout, ws_generators, ref):
        if not data or not data.get("path"):
            raise ConanException("Workspace editable %s does not define path" % str(ref))
        self._base_folder = base_folder
        self._conanfile_folder = data.pop("path", None)  # The folder with the conanfile
        layout = data.pop("layout", None)
        if layout:
            self.layout = get_editable_abs_path(layout, self._base_folder, cache.cache_folder)
        else:
            self.layout = ws_layout

        generators = data.pop("generators", None)
        if isinstance(generators, str):
            generators = [generators]
        if generators is None:
            generators = ws_generators
        self.generators = generators

        if data:
            raise ConanException("Workspace unrecognized fields: %s" % data)

    @property
    def root_folder(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder))


class Workspace(object):
    default_filename = "conanws.yml"

    def __init__(self, path, cache):
        self._cache = cache
        self._ws_generator = None
        self._workspace_packages = OrderedDict()  # {reference: LocalPackage}

        if not os.path.isfile(path):
            path = os.path.join(path, self.default_filename)

        self._base_folder = os.path.dirname(path)
        try:
            content = load(path)
        except IOError:
            raise ConanException("Couldn't load workspace file in %s" % path)
        try:
            self._loads(content)
        except Exception as e:
            raise ConanException("There was an error parsing %s: %s" % (path, str(e)))

    def generate(self, install_folder, graph, output):
        if self._ws_generator == "cmake":
            cmake = ""
            add_subdirs = ""
            # To avoid multiple additions (can happen for build_requires repeated nodes)
            unique_refs = OrderedDict()
            for node in graph.ordered_iterate():
                if node.recipe != RECIPE_EDITABLE:
                    continue
                unique_refs[node.ref] = node
            for ref, node in unique_refs.items():
                ws_pkg = self._workspace_packages[ref]
                layout = self._cache.package_layout(ref)
                editable = layout.editable_cpp_info()

                conanfile = node.conanfile
                src = build = None
                if editable:
                    build = editable.folder(ref, EditableLayout.BUILD_FOLDER, conanfile.settings,
                                            conanfile.options)
                    src = editable.folder(ref, EditableLayout.SOURCE_FOLDER, conanfile.settings,
                                          conanfile.options)
                if src is not None:
                    src = os.path.join(ws_pkg.root_folder, src).replace("\\", "/")
                    cmake += 'set(PACKAGE_%s_SRC "%s")\n' % (ref.name, src)
                else:
                    output.warn("CMake workspace: source_folder is not defined for %s" % str(ref))
                if build is not None:
                    build = os.path.join(ws_pkg.root_folder, build).replace("\\", "/")
                    cmake += 'set(PACKAGE_%s_BUILD "%s")\n' % (ref.name, build)
                else:
                    output.warn("CMake workspace: build_folder is not defined for %s" % str(ref))

                if src and build:
                    add_subdirs += ('    add_subdirectory(${PACKAGE_%s_SRC} ${PACKAGE_%s_BUILD})\n'
                                    % (ref.name, ref.name))
                else:
                    output.warn("CMake workspace: cannot 'add_subdirectory()'")

            if add_subdirs:
                cmake += "macro(conan_workspace_subdirectories)\n"
                cmake += add_subdirs
                cmake += "endmacro()"
            cmake_path = os.path.join(install_folder, "conanworkspace.cmake")
            save(cmake_path, cmake)

    def get_editable_dict(self):
        ret = {}
        for ref, ws_package in self._workspace_packages.items():
            path = ws_package.root_folder
            if os.path.isdir(path):
                path = os.path.join(path, CONANFILE)
            ret[ref] = {"path": path, "layout": ws_package.layout}
        return ret

    def __getitem__(self, ref):
        return self._workspace_packages.get(ref)

    @property
    def root(self):
        return self._root

    def _loads(self, text):
        yml = yaml.safe_load(text)
        self._ws_generator = yml.pop("workspace_generator", None)
        yml.pop("name", None)
        ws_layout = yml.pop("layout", None)
        if ws_layout:
            ws_layout = get_editable_abs_path(ws_layout, self._base_folder,
                                              self._cache.cache_folder)
        generators = yml.pop("generators", None)
        if isinstance(generators, str):
            generators = [generators]

        root_list = yml.pop("root", [])
        if isinstance(root_list, str):
            root_list = root_list.split(",")

        self._root = [ConanFileReference.loads(s.strip())
                      for s in root_list if s.strip()]
        if not self._root:
            raise ConanException("Conan workspace needs at least 1 root conanfile")

        editables = yml.pop("editables", {})
        for ref, data in editables.items():
            workspace_package = LocalPackage(self._base_folder, data,
                                             self._cache, ws_layout, generators, ref)
            package_name = ConanFileReference.loads(ref)
            self._workspace_packages[package_name] = workspace_package
        for package_name in self._root:
            if package_name not in self._workspace_packages:
                raise ConanException("Root %s is not defined as editable" % str(package_name))

        if yml:
            raise ConanException("Workspace unrecognized fields: %s" % yml)
