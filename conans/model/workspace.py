import os
import textwrap
from collections import OrderedDict

import yaml
from jinja2 import Template

from conans.client.graph.graph import RECIPE_EDITABLE
from conans.client.output import ScopedOutput
from conans.errors import ConanException
from conans.model.editable_layout import get_editable_abs_path, EditableLayout
from conans.model.ref import ConanFileReference
from conans.util.files import load, save


class LocalPackage(object):
    def __init__(self, base_folder, data, cache, ws_layout, ws_generators, ref):
        if not data or not data.get("path"):
            raise ConanException("Workspace editable %s does not define path" % str(ref))
        self._base_folder = base_folder
        self._conanfile_folder = data.pop("path", None)  # The folder with the conanfile
        layout = data.pop("layout", None)
        if layout:
            self.layout = get_editable_abs_path(layout, self._base_folder, cache.conan_folder)
        else:
            self.layout = ws_layout

        generators = data.pop("generators", None)
        if isinstance(generators, str):
            generators = [generators]
        if generators is None:
            generators = ws_generators
        self.generators = generators

        self.alias_target = data.pop("alias_target", None)

        if data:
            raise ConanException("Workspace unrecognized fields: %s" % data)

    @property
    def root_folder(self):
        return os.path.abspath(os.path.join(self._base_folder, self._conanfile_folder))


class Workspace(object):
    ws_cmake = Template(textwrap.dedent("""
        {% for item in editables %}
            {% if item.source_folder -%}
                set(PACKAGE_{{ item.name }}_SRC "{{ item.source_folder.replace('\\\\', '/') }}")
            {% endif %}
            {% if item.build_folder -%}
                set(PACKAGE_{{ item.name }}_BUILD "{{ item.build_folder.replace('\\\\', '/') }}")
            {% endif %}
        {% endfor %}
        
        macro(conan_workspace_subdirectories)
            set(CONAN_IS_WS TRUE)
            {% for item in editables %}
                {% if item.source_folder and item.build_folder %}
                    # {{ item.name }}
                    add_subdirectory(${PACKAGE_{{ item.name }}_SRC} ${PACKAGE_{{ item.name }}_BUILD})
                    {% if item.alias_target %}
                    add_library(CONAN_PKG::{{ item.name }} ALIAS {{ item.alias_target }}) # Use our library
                    {% endif %}
                {% endif %}
            {% endfor %}
        endmacro()
    """), trim_blocks=True, lstrip_blocks=True)

    def generate(self, cwd, graph, output):
        if self._ws_generator == "cmake":
            output = ScopedOutput("CMake workspace", output)
            unique_refs = OrderedDict()
            for node in graph.ordered_iterate():
                if node.recipe != RECIPE_EDITABLE:
                    continue
                # To avoid multiple additions: build_requires repeated, diamonds
                if node.ref in unique_refs:
                    continue

                ws_pkg = self._workspace_packages[node.ref]
                layout = self._cache.package_layout(node.ref)
                editable = layout.editable_cpp_info()
                if not editable:
                    output.warn("no layout available for reference '{}'".format(node.ref))
                    continue

                source_folder = editable.folder(node.ref, EditableLayout.SOURCE_FOLDER,
                                                node.conanfile.settings, node.conanfile.options)
                if source_folder is not None:
                    source_folder = os.path.join(ws_pkg.root_folder, source_folder)
                else:
                    output.warn("source_folder is not defined for reference '{}'"
                                " in layout file '{}'".format(node.ref, editable.filepath))

                build_folder = editable.folder(node.ref, EditableLayout.BUILD_FOLDER,
                                               node.conanfile.settings, node.conanfile.options)
                if build_folder is not None:
                    build_folder = os.path.join(ws_pkg.root_folder, build_folder)
                else:
                    output.warn("build_folder is not defined for reference '{}'"
                                " in layout file '{}'".format(node.ref, editable.filepath))

                unique_refs[node.ref] = {
                    'name': node.ref.name,
                    'source_folder': source_folder,
                    'build_folder': build_folder,
                    'alias_target': ws_pkg.alias_target
                }

            cmake_path = os.path.join(cwd, "conanworkspace.cmake")
            save(cmake_path, self.ws_cmake.render(editables=unique_refs.values()))

    def __init__(self, path, cache):
        self._cache = cache
        self._ws_generator = None
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
        self._ws_generator = yml.pop("workspace_generator", None)
        yml.pop("name", None)
        ws_layout = yml.pop("layout", None)
        if ws_layout:
            ws_layout = get_editable_abs_path(ws_layout, self._base_folder,
                                              self._cache.conan_folder)
        generators = yml.pop("generators", None)
        if isinstance(generators, str):
            generators = [generators]
        self._root = [ConanFileReference.loads(s.strip())
                      for s in yml.pop("root", "").split(",") if s.strip()]
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
