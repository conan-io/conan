import os
import shutil

from conan.api.model import RecipeReference
from conan.api.output import ConanOutput
from conan.cli import make_abs_path
from conan.errors import ConanException
from conan.internal.conan_app import ConanApp
from conan.internal.workspace import Workspace
from conan.tools.scm import Git
from conans.client.graph.graph import RECIPE_EDITABLE, TransitiveRequirement
from conans.client.source import retrieve_exports_sources
from conans.util.files import merge_directories


class WorkspaceAPI:

    def __init__(self, conan_api):
        self._conan_api = conan_api
        self._workspace = Workspace(conan_api)

    def home_folder(self):
        """
        @return: The custom defined Conan home/cache folder if defined, else None
        """
        return self._workspace.home_folder()

    def folder(self):
        """
        @return: the current workspace folder where the conanws.yml or conanws.py is located
        """
        return self._workspace.folder

    def config_folder(self):
        return self._workspace.config_folder()

    @property
    def editable_packages(self):
        return self._workspace.editables()

    @property
    def products(self):
        return self._workspace.products

    def open(self, require, remotes, cwd=None):
        app = ConanApp(self._conan_api)
        ref = RecipeReference.loads(require)
        recipe = app.proxy.get_recipe(ref, remotes, update=False, check_update=False)

        layout, recipe_status, remote = recipe
        if recipe_status == RECIPE_EDITABLE:
            raise ConanException(f"Can't open a dependency that is already an editable: {ref}")
        ref = layout.reference
        conanfile_path = layout.conanfile()
        conanfile, module = app.loader.load_basic_module(conanfile_path, remotes=remotes)

        scm = conanfile.conan_data.get("scm") if conanfile.conan_data else None
        dst_path = os.path.join(cwd or os.getcwd(), ref.name)
        if scm is None:
            conanfile.output.warning("conandata doesn't contain 'scm' information\n"
                                     "doing a local copy!!!")
            shutil.copytree(layout.export(), dst_path)
            retrieve_exports_sources(app.remote_manager, layout, conanfile, ref, remotes)
            export_sources = layout.export_sources()
            if os.path.exists(export_sources):
                conanfile.output.warning("There are export-sources, copying them, but the location"
                                         " might be incorrect, use 'scm' approach")
                merge_directories(export_sources, dst_path)
        else:
            git = Git(conanfile, folder=cwd)
            git.clone(url=scm["url"], target=ref.name)
            git.folder = ref.name  # change to the cloned folder
            git.checkout(commit=scm["commit"])
        return dst_path

    def add(self, path, name=None, version=None, user=None, channel=None, cwd=None,
            output_folder=None, remotes=None, product=False):
        """
        Add a new editable package to the current workspace (the current workspace must exist)
        @param path: The path to the folder containing the conanfile.py that defines the package
        @param name: (optional) The name of the package to be added if not defined in recipe
        @param version:
        @param user:
        @param channel:
        @param cwd:
        @param output_folder:
        @param remotes:
        @param product:
        @return: The reference of the added package
        """
        full_path = self._conan_api.local.get_conanfile_path(path, cwd, py=True)
        app = ConanApp(self._conan_api)
        conanfile = app.loader.load_named(full_path, name, version, user, channel, remotes=remotes)
        if conanfile.name is None or conanfile.version is None:
            raise ConanException("Editable package recipe should declare its name and version")
        ref = RecipeReference(conanfile.name, conanfile.version, conanfile.user, conanfile.channel)
        ref.validate_ref()
        output_folder = make_abs_path(output_folder) if output_folder else None
        # Check the conanfile is there, and name/version matches
        self._workspace.add(ref, full_path, output_folder=output_folder,  product=product)
        return ref

    def remove(self, path, cwd=None):
        return self._workspace.remove(path)

    def info(self):
        return self._workspace.serialize()

    def editable_from_path(self, path):
        return self._workspace.editable_from_path(path)

    @staticmethod
    def collapse_editables(root_node, deps_graph):
        ConanOutput().title(f"Collapsing workspace editables")

        for node in deps_graph.nodes:
            if node.recipe != RECIPE_EDITABLE:
                continue
            for r, t in node.transitive_deps.items():
                if t.node.recipe == RECIPE_EDITABLE:
                    continue
                existing = root_node.transitive_deps.pop(r, None)
                if existing is None:
                    root_node.transitive_deps[r] = t
                else:
                    require = existing.require
                    require.aggregate(r)
                    root_node.transitive_deps[require] = TransitiveRequirement(require, t.node)

        # The graph edges must be defined too
        for r, t in root_node.transitive_deps.items():
            deps_graph.add_edge(root_node, t.node, r)

        # Now drop the root and the editables
        deps_graph.nodes = [node for node in deps_graph.nodes[1:] if node.recipe != RECIPE_EDITABLE]
        # And inject the new root
        deps_graph.nodes.insert(0, root_node)
