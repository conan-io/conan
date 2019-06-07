import os
import textwrap

import yaml
from jinja2 import Template

from conans.client.graph.graph import RECIPE_EDITABLE
from conans.errors import ConanException
from conans.model.editable_layout import get_editable_abs_path, EditableLayout
from conans.model.ref import ConanFileReference
from conans.util.files import load, save


class LocalPackage(object):

    def __init__(self, ref, path, layout):
        self._ref = ref
        self.path = path
        self.layout = layout

    def layout_path(self, path):
        path = path or "."
        return os.path.normpath(os.path.join(self.path, path))


class Workspace(object):
    default_filename = "conanws.yml"
    name = None
    packages = {}

    def __init__(self, cache):
        self._cache = cache

    @classmethod
    def create(cls, path, cache):
        # Look for the workspace file
        if not os.path.isfile(path):
            path = os.path.join(path, cls.default_filename)
        base_folder = os.path.dirname(path)

        try:
            content = load(path)
            yml = yaml.safe_load(content)
        except IOError:
            raise ConanException("Couldn't load workspace file in %s" % path)
        except Exception as e:
            raise ConanException("There was an error parsing %s: %s" % (path, str(e)))

        ws_generator = yml.pop("workspace_generator", None)
        if ws_generator == 'cmake':
            ws = WorkspaceCMake(cache)
        else:
            raise ConanException("Generator '{}' not supported for a workspace".format(ws_generator))

        ws.name = yml.pop("name", "Conan Workspace")

        # Global parameters, if not defined for each package
        ws_layout = yml.pop("layout", None)
        if ws_layout:
            ws_layout = get_editable_abs_path(ws_layout, base_folder, cache.cache_folder)

        yml.pop("generators", None)  # Not used

        # Root packages
        yml.pop("root", [])  # Not needed

        # Editable packages
        editables = yml.pop("editables", {})
        for ref, data in editables.items():
            if not data or 'path' not in data:
                raise ConanException("Editable '{}' doesn't define field 'path'".format(ref))
            try:
                layout = data.pop("layout", ws_layout)
                if layout:
                    layout = get_editable_abs_path(layout, base_folder, cache.cache_folder)
                if not layout:
                    raise ConanException("No layout defined for editable '{}' and cannot find the"
                                         " default one neither".format(ref))

                data.pop("generators", None)  # Not used

                ref = ConanFileReference.loads(ref, validate=True)
                path = os.path.normpath(os.path.join(base_folder, data.pop("path")))
                package = LocalPackage(ref, path, layout)
                ws.packages[ref] = package

                if data:
                    raise ConanException("Unrecognized fields '{}' for"
                                         " editable '{}'".format("', '".join(data.keys()), ref))
            except KeyError as e:
                raise ConanException("Field '{}' not found for editable '{}'".format(e, ref))

        if yml:
            raise ConanException("Unrecognized fields '{}'".format("', '".join(yml.keys())))

        return ws

    def _build_graph(self, manager, refs, **kwargs):
        # Load editable packages:
        editables = {ref: {"path": ws_package.path, "layout": ws_package.layout}
                     for ref, ws_package in self.packages.items()}
        self._cache.editable_packages.override(editables)

        return manager.install(refs, manifest_folder=False, install_folder=None,
                               build_modes=["never"],
                               **kwargs)


class WorkspaceCMake(Workspace):
    """ Implements workspaces for a CMake generator """

    conanworkspace_cmake_template = textwrap.dedent(r"""
        # List of targets involved in the workspace
        {%- for _, pkg in ordered_packages %}
        list(APPEND ws_targets "{{ pkg.name }}")
        {%- endfor %}

        {% if out_dependents %}
        # Packages that are consumed by editable ones
        {%- for ref, pkg in out_dependents.items() %}
        find_package({{ pkg.name }} REQUIRED)
        set_target_properties({{pkg.name}}::{{pkg.name}} PROPERTIES IMPORTED_GLOBAL TRUE)
        add_library(CONAN_PKG::{{ pkg.name }} ALIAS {{ pkg.name }}::{{ pkg.name }}) 
        {% endfor %}
        {%- endif %}

        # Override functions to avoid importing their own TARGETs (or calling again Conan Magic)
        function(conan_basic_setup)
            message("Ignored call to 'conan_basic_setup'")
        endfunction()
        
        function(include)
            if ("${ARGV0}" MATCHES ".*/conanbuildinfo(_multi)?.cmake")
                message("Ignore inclusion of ${ARGV0}")
            else()
                _include(${ARGV})
            endif()
        endfunction(include)
        
        # Do not use find_package for those packages handled within the workspace
        function(find_package)
            if(NOT "${ARGV0}" IN_LIST ws_targets)
                # Note.- If it's been already overridden, it will recurse forever
                message("find_package(${ARGV0})")
                _find_package(${ARGV})
            else()
                message("find_package(${ARGV0}) ignored, it is a target handled by Conan workspace")
            endif()
        endfunction()
        
        # Custom target
        function(outer_package PKG_NAME FULL_REF)
            set(PKG_SENTINEL "{{install_folder}}/${PKG_NAME}.setinel")
            add_custom_command(OUTPUT ${PKG_SENTINEL}
                               COMMAND echo "Package ${FULL_REF} not built" > ${PKG_SENTINEL}
                               WORKING_DIRECTORY "{{install_folder}}"
                               COMMENT "Build ${PKG_NAME} outside workspace")
            add_custom_target(${PKG_NAME} DEPENDS ${PKG_SENTINEL})
        endfunction()
        
        {% for ref, pkg in ordered_packages %}
            {%- if pkg.in %}
                # Inner: {{ ref }}
                add_subdirectory("{{ pkg.source_folder }}" "{{ pkg.build_folder }}")
                add_library({{ pkg.name }}::{{ pkg.name }} ALIAS {{ pkg.name }})
                add_library(CONAN_PKG::{{ pkg.name }} ALIAS {{ pkg.name }})
            {%- else %}
                # Outter: {{ ref }}
                outer_package({{pkg.name}} {{ref}})
            {%- endif %}
            {%- for r in pkg.requires %}
                add_dependencies({{ pkg.name }} {{ r }})
            {%- endfor %}
        {% endfor %}
    """)

    cmakelists_template = textwrap.dedent(r"""
        cmake_minimum_required(VERSION 3.3)
        project("{{ ws.name }}")
        
        include(${CMAKE_CURRENT_SOURCE_DIR}/conanbuildinfo.cmake)
        conan_basic_setup()  # Execute Conan magic
        
        include(${CMAKE_CURRENT_SOURCE_DIR}/conanworkspace.cmake)
    """)

    def generate(self, install_folder, manager, output, **kwargs):
        # Add roots and editables, all together
        roots = list(self.packages.keys())
        graph = self._build_graph(manager, refs=roots, **kwargs)

        # Prepare the context for the templates
        ordered_packages = []  # [(ref, pkg), ]
        in_ws = {}  # {ref: {source_folder: X, build_folder: Y}}
        out_dependents = {}  # {ref: {name, requires}}
        for node in graph.ordered_iterate():
            if node.ref in self.packages:
                assert node.recipe == RECIPE_EDITABLE, "Not editable in the graph, but in workspace"
                layout = self._cache.package_layout(node.ref)
                editable = layout.editable_cpp_info()
                conanfile = node.conanfile

                source_folder = editable.folder(node.ref, EditableLayout.SOURCE_FOLDER,
                                                conanfile.settings, conanfile.options)
                build_folder = editable.folder(node.ref, EditableLayout.BUILD_FOLDER,
                                               conanfile.settings, conanfile.options)

                pkg = {'name': node.ref.name,
                                   'source_folder': self.packages[node.ref].layout_path(source_folder),
                                   'build_folder': self.packages[node.ref].layout_path(build_folder),
                                   'requires': [it.ref.name for it in node.neighbors()
                                                if it.ref in in_ws or
                                                it.ref in out_dependents],
                                   'in': True}
                in_ws[node.ref] = pkg
                ordered_packages.append((node.ref, pkg))
            else:
                if node.ref and any([it.ref in in_ws for it in node.public_closure]):
                    pkg = {'name': node.ref.name,
                                                'requires': [it.ref.name for it in node.neighbors()
                                                             if it.ref in in_ws or
                                                             it.ref in out_dependents],
                                                'in': False}
                    out_dependents[node.ref] = pkg
                    ordered_packages.append((node.ref, pkg))

        # Warn for package not in workspace but depending on packages in the workspace
        if out_dependents:
            output.warn("Packages '{}' are not included in the workspace and depend on"
                        " packages that are included. Binaries for these packages are not"
                        " going to take into account local changes, you'll need to build"
                        " them manually".format("', '".join(map(str, out_dependents.keys()))))

        # Create the conanworkspace.cmake file
        t = Template(self.conanworkspace_cmake_template)
        content = t.render(ws=self, out_dependents=out_dependents,
                           ordered_packages=ordered_packages,
                           install_folder=install_folder)
        save(os.path.join(install_folder, 'conanworkspace.cmake'), content)

        # Create the CMakeLists.txt file
        t = Template(self.cmakelists_template)
        content = t.render(ws=self, out_dependents=out_dependents)
        save(os.path.join(install_folder, 'CMakeLists.txt'), content)

        # Create the conanbuildinfo.cmake (no dependencies)
        # TODO: Silent output here (it could confuse the users)
        manager.install([], manifest_folder=False, install_folder=install_folder,
                        build_modes=["never"], generators=["cmake", ], **kwargs)

        # Create findXXX files for consumed packages
        if out_dependents:
            # TODO: Silent output here?
            manager.install(list(out_dependents.keys()),
                            manifest_folder=False, install_folder=install_folder,
                            build_modes=["never"], generators=["cmake_find_package", ], **kwargs)
