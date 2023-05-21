import os
import sys
from distutils.dir_util import copy_tree
from fnmatch import fnmatch
from io import StringIO

import yaml

from conan.tools.files import load
from conans.client.cmd.export import cmd_export
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.model.recipe_ref import RecipeReference


class LocalTreeApiClient:

    def __init__(self, remote, config):
        self._remote = remote
        self._config = config
        cache_folder = self._remote.url.replace("file://", "")
        self._remote_cache_dir = "{}/.cache".format(cache_folder)
        from conan.internal.conan_app import ConanApp
        self._app = ConanApp(self._remote_cache_dir)
        self.layout = _ConanCenterIndexLayout(cache_folder)

    def get_recipe(self, ref, dest_folder):
        export_folder = self._app.cache.ref_layout(ref).export()
        return self._copy_files(export_folder, dest_folder)

    def get_recipe_sources(self, ref, dest_folder):
        export_sources = self._app.cache.ref_layout(ref).download_export()
        return self._copy_files(export_sources, dest_folder)

    def get_package(self, pref, dest_folder):
        raise ConanException(f"The remote '{self._remote.name}' doesn't support binary packages")

    def upload_recipe(self, ref, files_to_upload):
        raise ConanException(f"Git remote '{self._remote.name}' do not support upload")

    def upload_package(self, pref, files_to_upload):
        raise ConanException(f"Git remote '{self._remote.name}' do not support upload")

    def authenticate(self, user, password):
        raise ConanException(f"Git remote '{self._remote.name}' do not support authentication")

    def check_credentials(self):
        raise ConanException(f"Git remote '{self._remote.name}' do not support check credentials")

    def search(self, pattern=None, ignorecase=True):
        ret = []
        for ref in self.layout.get_recipes_references():
            # TODO: Check the search pattern is the same as remotes and cache
            if fnmatch(str(ref), pattern):
                ret.append(ref)
        return ret

    def search_packages(self, reference):
        return {}

    def remove_recipe(self, ref):
        raise ConanException(f"Git remote '{self._remote.name}' do not support remove")

    def remove_all_packages(self, ref):
        raise ConanException(f"Git remote '{self._remote.name}' do not support remove")

    def remove_packages(self, prefs):
        raise ConanException(f"Git remote '{self._remote.name}' do not support remove")

    def server_capabilities(self):
        raise NotImplementedError("Git remote doesn't implement 'server_capabilities'")

    def get_recipe_revisions_references(self, ref):
        ref = self._export_recipe(ref)
        return [ref]

    def get_package_revisions_references(self, pref, headers=None):
        raise PackageNotFoundException(pref)

    def get_latest_recipe_reference(self, ref):
        ref = self._export_recipe(ref)
        return ref

    def get_latest_package_reference(self, pref, headers):
        raise PackageNotFoundException(pref)

    def get_recipe_revision_reference(self, ref):
        ref = self._export_recipe(ref)
        return ref

    def get_package_revision_reference(self, pref):
        raise PackageNotFoundException(pref)

    #######################################################################################
    #######################################################################################
    #######################################################################################
    def _export_recipe(self, ref):
        folder = self.layout.get_recipe_folder(ref)
        conanfile_path = os.path.join(folder, "conanfile.py")
        original_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            ref, _ = cmd_export(self._app, conanfile_path, ref.name, ref.version, None, None)
            from conans.client.cmd.uploader import PackagePreparator
            preparator = PackagePreparator(self._app)
            recipe_layout = self._app.cache.ref_layout(ref)
            preparator._compress_recipe_files(recipe_layout, ref)
        finally:
            sys.stderr = original_stderr

        return ref

    @staticmethod
    def _copy_files(source_folder, dest_folder):
        if not os.path.exists(source_folder):
            return {}
        copy_tree(source_folder, dest_folder)
        ret = {}
        for root, _, _files in os.walk(dest_folder):
            for _f in _files:
                rel = os.path.relpath(os.path.join(root, _f), dest_folder)
                ret[rel] = os.path.join(dest_folder, root, _f)
        return ret

    '''
    def get_recipe_revisions_references(self, ref):
        ref = self._export_recipe(ref)
        tmp = copy.copy(ref)
        tmp.revision = None
        return self._conan_api.list.recipe_revisions(tmp)

    def get_recipe_revision_reference(self, ref):
        ref = self._export_recipe(ref)
        if ref in self.get_recipe_revisions_references(ref):
            return ref
        else:
            raise RecipeNotFoundException(ref)
    '''


class _ConanCenterIndexLayout:

    def __init__(self, base_folder):
        self._base_folder = base_folder

    def get_base_folder(self, recipe_name):
        return os.path.join(self._base_folder, "recipes", recipe_name)

    def _load_config_yml(self, recipe_name):
        content = load(None, os.path.join(self.get_base_folder(recipe_name), "config.yml"))
        return yaml.safe_load(content)

    def get_versions(self, recipe_name):
        data = self._load_config_yml(recipe_name)["versions"]
        return data.keys()

    def get_recipes_references(self):
        recipes_dir = os.path.join(self._base_folder, "recipes")
        recipes = os.listdir(recipes_dir)
        recipes.sort()
        ret = []
        for r in recipes:
            for v in self.get_versions(r):
                ret.append(RecipeReference.loads("{}/{}".format(r, v)))
        return ret

    def get_recipe_folder(self, ref):
        data = self._load_config_yml(ref.name)
        versions = data["versions"]
        if str(ref.version) not in versions:
            raise RecipeNotFoundException(ref)
        subfolder = versions[str(ref.version)]["folder"]
        return os.path.join(self.get_base_folder(ref.name), subfolder)
