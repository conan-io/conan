import os
import shutil

from conan.cli import make_abs_path
from conan.internal.conan_app import ConanApp
from conan.internal.workspace import Workspace
from conan.tools.scm import Git
from conan.errors import ConanException
from conans.client.graph.graph import RECIPE_EDITABLE
from conans.client.source import retrieve_exports_sources
from conan.internal.model.recipe_ref import RecipeReference
from conans.util.files import merge_directories


class WorkspaceAPI:

    def __init__(self, conan_api):
        self._conan_api = conan_api
        self._workspace = Workspace(conan_api)

    def home_folder(self):
        return self._workspace.home_folder()

    def folder(self):
        return self._workspace.folder

    def config_folder(self):
        return self._workspace.config_folder()

    @property
    def editable_packages(self):
        return self._workspace.editables()

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
            output_folder=None, remotes=None):
        path = self._conan_api.local.get_conanfile_path(path, cwd, py=True)
        app = ConanApp(self._conan_api)
        conanfile = app.loader.load_named(path, name, version, user, channel, remotes=remotes)
        if conanfile.name is None or conanfile.version is None:
            raise ConanException("Editable package recipe should declare its name and version")
        ref = RecipeReference(conanfile.name, conanfile.version, conanfile.user, conanfile.channel)
        ref.validate_ref()
        output_folder = make_abs_path(output_folder) if output_folder else None
        # Check the conanfile is there, and name/version matches
        self._workspace.add(ref, path, output_folder=output_folder)
        return ref

    def remove(self, path):
        return self._workspace.remove(path)

    def info(self):
        return self._workspace.serialize()
