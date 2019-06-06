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
    root_list = None
    packages = {}

    def __init__(self, cache):
        self._cache = cache

    def validate(self):
        # Every package in the root list must be contained in the packages dictionary
        for ref in self.root_list:
            if ref not in self.packages:
                raise ConanException("Root {} is not defined as editable".format(ref))
        return True

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
        root_list = yml.pop("root", [])
        if isinstance(root_list, str):
            root_list = root_list.split(",")
        ws.root_list = [ConanFileReference.loads(s.strip(), validate=True)
                        for s in root_list if s.strip()]

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

        ws.validate()
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
        {%- for ref in in_ws %}
        list(APPEND ws_targets "{{ ref.name }}")
        {%- endfor %}

        # Override functions to avoid importing existing TARGETs (or calling again Conan Magic)
        function(conan_basic_setup)
            message("Ignored call to 'conan_basic_setup'")
        endfunction()
        
        # Do not use find_package for those packages handled within the workspace
        function(find_package)
            if(NOT "${ARG0}" IN_LIST ws_targets)
                # Note.- If it's been already overridden, it will recurse forever
                message("find_package(${ARG0})")
                _find_package(${ARGV})
            else()
                message("find_package(${ARG0}) ignored, it is a target handled by Conan workspace")
            endif()
        endfunction()
        
        {# Packages that depend on editable ones: out_dependents #}

        {%- if out_consumed %}
        # Packages that are consumed by editable ones
        {%- for pkg in out_consumed %}
        find_package({{ pkg.name }} REQUIRED)
        add_library(CONAN_PKG::{{ pkg.name }} ALIAS {{ pkg.name }}) 
        {%- endfor %}
        {%- endif %}
        
        # Add subdirectories for packages (like it is now) and create aliases
        {%- for ref, pkg in in_ws.items() %}
        add_subdirectory("{{ pkg.source_folder }}" "{{ pkg.build_folder }}")
        add_library({{ ref.name }}::{{ ref.name }} ALIAS {{ ref.name }})
        add_library(CONAN_PKG::{{ ref.name }} ALIAS {{ ref.name }}) 
        {% endfor %}

    """)

    cmakelists_template = textwrap.dedent(r"""
        cmake_minimum_required(VERSION 2.8.12)
        project("{{ ws.name }}")
        
        include(${CMAKE_CURRENT_SOURCE_DIR}/conanbuildinfo.cmake)
        conan_basic_setup()  # Execute Conan magic
        
        include(${CMAKE_CURRENT_SOURCE_DIR}/conanworkspace.cmake)
        
    """)

    def validate(self):
        super(WorkspaceCMake, self).validate()
        for _, pkg in self.packages.items():
            pass

    def generate(self, install_folder, manager, output, **kwargs):
        # Add roots and editables, all together
        roots = list(set(self.root_list + list(self.packages.keys())))
        graph = self._build_graph(manager, refs=roots, **kwargs)

        # Prepare the context for the templates
        in_ws = {}  # {ref: {source_folder: X, build_folder: Y}}
        out_ws = []
        out_dependents = []
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

                in_ws[node.ref] = {'source_folder': self.packages[node.ref].layout_path(source_folder),
                                   'build_folder': self.packages[node.ref].layout_path(build_folder)}
            else:
                out_ws.append(node)
                if node.ref and any([it.ref in in_ws for it in node.public_closure]):
                    out_dependents.append(node.ref)
        out_ws = [it for it in out_ws if it.ref is not None]  # Get rid of the None ref

        # Warn for package not in workspace but depending on packages in the workspace
        if out_dependents:
            output.warn("Packages '{}' are not included in the workspace and depend on"
                        " packages that are included. Binaries for these packages are not"
                        " going to take into account local changes, you'll need to build"
                        " them manually".format("', '".join(map(str, out_dependents))))

        # Gather packages not in workspace but consumed by packages in the workspace
        out_consumed = []
        for it in out_ws:
            if any([n.ref in in_ws for n in it.inverse_closure]):
                out_consumed.append(it.ref)

        # Create the conanworkspace.cmake file
        t = Template(self.conanworkspace_cmake_template)
        content = t.render(ws=self, in_ws=in_ws, out_dependents=out_dependents,
                           out_consumed=out_consumed)
        save(os.path.join(install_folder, 'conanworkspace.cmake'), content)

        # Create the CMakeLists.txt file
        t = Template(self.cmakelists_template)
        content = t.render(ws=self, in_ws=in_ws, out_dependents=out_dependents,
                           out_consumed=out_consumed)
        save(os.path.join(install_folder, 'CMakeLists.txt'), content)

        # Create the conanbuildinfo.cmake (no dependencies)
        # TODO: Silent output here (it will confuse the users)
        manager.install([], manifest_folder=False, install_folder=install_folder,
                        build_modes=["never"], generators=["cmake", ], **kwargs)

        # Create findXXX files for consumed packages
        if out_consumed:
            manager.install([it for it in out_consumed],
                            manifest_folder=False, install_folder=install_folder,
                            build_modes=["never"], generators=["cmake_find_package", ], **kwargs)
