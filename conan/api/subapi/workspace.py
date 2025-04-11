import inspect
import os
import shutil
from pathlib import Path

from conan import ConanFile
from conan.api.model import RecipeReference
from conan.api.output import ConanOutput
from conan.cli import make_abs_path
from conan.errors import ConanException
from conan.internal.conan_app import ConanApp
from conan.internal.model.workspace import Workspace
from conan.tools.scm import Git
from conans.client.graph.graph import RECIPE_EDITABLE, DepsGraph, CONTEXT_HOST, RECIPE_VIRTUAL, Node, \
    RECIPE_CONSUMER
from conans.client.graph.graph import TransitiveRequirement
from conans.client.graph.profile_node_definer import consumer_definer
from conans.client.loader import load_python_file
from conans.client.source import retrieve_exports_sources
from conans.util.files import merge_directories


def _find_ws_folder():
    path = Path(os.getcwd())
    while path.is_dir() and len(path.parts) > 1:  # finish at '/'
        if (path / "conanws.yml").is_file() or (path / "conanws.py").is_file():
            return str(path)
        else:
            path = path.parent


def _load_workspace(ws_folder, conan_api):
    """ loads a conanfile basic object without evaluating anything, returns the module too
    """
    wspy = os.path.join(ws_folder, "conanws.py")
    if not os.path.isfile(wspy):
        ConanOutput().info(f"conanws.py doesn't exist in {ws_folder}, using default behavior")
        assert os.path.exists(os.path.join(ws_folder, "conanws.yml"))
        ws = Workspace(ws_folder, conan_api)
    else:
        try:
            module, module_id = load_python_file(wspy)
            ws = _parse_module(module, module_id)
            ws = ws(ws_folder, conan_api)
        except ConanException as e:
            raise ConanException(f"Error loading conanws.py at '{wspy}': {e}")
    return ws


def _parse_module(conanfile_module, module_id):
    result = None
    for name, attr in conanfile_module.__dict__.items():
        if (name.startswith("_") or not inspect.isclass(attr) or
                attr.__dict__.get("__module__") != module_id):
            continue

        if issubclass(attr, Workspace) and attr != Workspace:
            if result is None:
                result = attr
            else:
                raise ConanException("More than 1 Workspace in the file")

    if result is None:
        raise ConanException("No subclass of Workspace")

    return result


class WorkspaceAPI:
    TEST_ENABLED = False

    def __init__(self, conan_api):
        self._conan_api = conan_api
        self._folder = _find_ws_folder()
        if self._folder:
            ConanOutput().warning(f"Workspace found: {self._folder}")
            if (WorkspaceAPI.TEST_ENABLED or os.getenv("CONAN_WORKSPACE_ENABLE")) != "will_break_next":
                ConanOutput().warning("Workspace ignored as CONAN_WORKSPACE_ENABLE is not set")
                self._folder = None
            else:
                ConanOutput().warning(f"Workspace is a dev-only feature, exclusively for testing")
                self._ws = _load_workspace(self._folder, conan_api)  # Error if not loading

    @property
    def name(self):
        self._check_ws()
        return self._ws.name()

    def home_folder(self):
        """
        @return: The custom defined Conan home/cache folder if defined, else None
        """
        if not self._folder:
            return
        folder = self._ws.home_folder()
        if folder is None or os.path.isabs(folder):
            return folder
        return os.path.normpath(os.path.join(self._folder, folder))

    def folder(self):
        """
        @return: the current workspace folder where the conanws.yml or conanws.py is located
        """
        return self._folder

    @property
    def editable_packages(self):
        """
        @return: Returns {RecipeReference: {"path": full abs-path, "output_folder": abs-path}}
        """
        if not self._folder:
            return
        editables = self._ws.editables()
        editables = {RecipeReference.loads(r): v.copy() for r, v in editables.items()}
        for v in editables.values():
            path = os.path.normpath(os.path.join(self._folder, v["path"], "conanfile.py"))
            if not os.path.isfile(path):
                raise ConanException(f"Workspace editable not found: {path}")
            v["path"] = path
            if v.get("output_folder"):
                v["output_folder"] = os.path.normpath(os.path.join(self._folder,
                                                                   v["output_folder"]))
        return editables

    def select_editables(self, paths):
        filtered_refs = [self.editable_from_path(p) for p in paths or []]
        editables = self.editable_packages
        requires = [ref for ref in editables]
        if filtered_refs:
            ConanOutput().info(f"Filtering and installing only selected editable packages")
            requires = [ref for ref in requires if ref in filtered_refs]
            ConanOutput().info(f"Filtered references: {requires}")
        return requires

    @property
    def products(self):
        self._check_ws()
        return self._ws.products()

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

    def _check_ws(self):
        if not self._folder:
            raise ConanException("Workspace not defined, please create a "
                                 "'conanws.py' or 'conanws.yml' file")

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
        self._check_ws()
        full_path = self._conan_api.local.get_conanfile_path(path, cwd, py=True)
        app = ConanApp(self._conan_api)
        conanfile = app.loader.load_named(full_path, name, version, user, channel, remotes=remotes)
        if conanfile.name is None or conanfile.version is None:
            raise ConanException("Editable package recipe should declare its name and version")
        ref = RecipeReference(conanfile.name, conanfile.version, conanfile.user, conanfile.channel)
        ref.validate_ref()
        output_folder = make_abs_path(output_folder) if output_folder else None
        # Check the conanfile is there, and name/version matches
        self._ws.add(ref, full_path, output_folder, product)
        return ref

    def remove(self, path):
        self._check_ws()
        return self._ws.remove(path)

    def info(self):
        self._check_ws()
        return {"name": self.name,
                "folder": self._folder,
                "products": self.products,
                "editables": self._ws.editables()}

    def editable_from_path(self, path):
        editables = self._ws.editables()
        for ref, info in editables.items():
            if info["path"].replace("\\", "/") == path:
                return RecipeReference.loads(ref)

    def collapse_editables(self, deps_graph, profile_host, profile_build):
        ConanOutput().title(f"Collapsing workspace editables")

        root_class = self._ws.root_conanfile()
        if root_class is not None:
            conanfile = root_class("conanws.py base project Conanfile")
            consumer_definer(conanfile, profile_host, profile_build)
            root = Node(None, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER,
                        path=self._folder)  # path lets use the conanws.py folder
            root.should_build = True  # It is a consumer, this is something we are building
            for field in ("requires", "build_requires", "test_requires", "requirements", "build",
                          "source", "package"):
                if getattr(conanfile, field, None):
                    raise ConanException(f"Conanfile in conanws.py shouldn't have '{field}'")
        else:
            ConanOutput().info("Workspace conanfilews.py not found in the workspace folder, "
                               "using default behavior")
            conanfile = ConanFile(display_name="cli")
            consumer_definer(conanfile, profile_host, profile_build)
            root = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)

        result = DepsGraph()  # TODO: We might need to copy more information from the original graph
        result.add_node(root)
        for node in deps_graph.nodes[1:]:  # Exclude the current root
            if node.recipe != RECIPE_EDITABLE:
                result.add_node(node)
                continue
            for r, t in node.transitive_deps.items():
                if t.node.recipe == RECIPE_EDITABLE:
                    continue
                existing = root.transitive_deps.pop(r, None)
                if existing is None:
                    root.transitive_deps[r] = t
                else:
                    require = existing.require
                    require.aggregate(r)
                    root.transitive_deps[require] = TransitiveRequirement(require, t.node)

        # The graph edges must be defined too
        for r, t in root.transitive_deps.items():
            result.add_edge(root, t.node, r)

        return result
