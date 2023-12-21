import os
import sys
from distutils.dir_util import copy_tree
from fnmatch import fnmatch
from io import StringIO

import yaml

from conan.api.output import ConanOutput
from conans.client.cmd.export import cmd_export
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.model.conf import ConfDefinition
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load


class GitRemoteManager:

    def __init__(self, remote):
        self._remote = remote
        cache_folder = self._remote.url
        self._remote_cache_dir = "{}/.cache".format(cache_folder)
        from conan.internal.conan_app import ConanApp
        global_conf = ConfDefinition()
        self._app = ConanApp(self._remote_cache_dir, global_conf)
        self.layout = _ConanCenterIndexLayout(cache_folder)

    def call_method(self, method_name, *args, **kwargs):
        return getattr(self, method_name)(*args, **kwargs)

    def get_recipe(self, ref, dest_folder):
        export_folder = self._app.cache.recipe_layout(ref).export()
        return self._copy_files(export_folder, dest_folder)

    def get_recipe_sources(self, ref, dest_folder):
        export_sources = self._app.cache.recipe_layout(ref).export_sources()
        return self._copy_files(export_sources, dest_folder)

    def get_package(self, pref, dest_folder, metadata, only_metadata):
        raise ConanException(f"The remote '{self._remote.name}' doesn't support binary packages")

    def upload_recipe(self, ref, files_to_upload):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support upload")

    def upload_package(self, pref, files_to_upload):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support upload")

    def authenticate(self, user, password):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support authentication")

    def check_credentials(self):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support upload")

    def search(self, pattern=None):
        return self.layout.get_recipes_references(pattern)

    def search_packages(self, reference):
        assert self and reference
        return {}

    def remove_recipe(self, ref):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support remove")

    def remove_all_packages(self, ref):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support remove")

    def remove_packages(self, prefs):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support remove")

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
        new_ref = self._export_recipe(ref)
        if new_ref != ref:
            raise RecipeNotFoundException(ref)
        return new_ref

    def get_package_revision_reference(self, pref):
        raise PackageNotFoundException(pref)

    # Helper methods to implement the interface
    def _export_recipe(self, ref):
        folder = self.layout.get_recipe_folder(ref)
        conanfile_path = os.path.join(folder, "conanfile.py")
        original_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            global_conf = ConfDefinition()
            new_ref, _ = cmd_export(self._app, global_conf, conanfile_path,
                                    ref.name, ref.version, None, None)
        except Exception as e:
            raise ConanException(f"Error while exporting recipe from remote: {self._remote.name}\n"
                                 f"{str(e)}")
        finally:
            sys.stderr = original_stderr

        return new_ref

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


class _ConanCenterIndexLayout:

    def __init__(self, base_folder):
        self._base_folder = base_folder

    def _get_base_folder(self, recipe_name):
        return os.path.join(self._base_folder, "recipes", recipe_name)

    @staticmethod
    def _load_config_yml(folder):
        config = os.path.join(folder, "config.yml")
        if not os.path.isfile(config):
            return None
        return yaml.safe_load(load(config))

    def get_recipes_references(self, pattern):
        name_pattern = pattern.split("/", 1)[0]
        recipes_dir = os.path.join(self._base_folder, "recipes")
        recipes = os.listdir(recipes_dir)
        recipes.sort()
        ret = []
        excluded = set()
        for r in recipes:
            if not fnmatch(r, name_pattern):
                continue
            folder = self._get_base_folder(r)
            config_yml = self._load_config_yml(folder)
            if config_yml is None:
                raise ConanException(f"Corrupted repo, folder {r} without 'config.yml'")
            versions = config_yml["versions"]
            for v in versions:
                # TODO: Check the search pattern is the same as remotes and cache
                ref = f"{r}/{v}"
                if not fnmatch(ref, pattern):
                    continue
                subfolder = versions[v]["folder"]
                # This check can be removed after compatibility with 2.0
                conanfile = os.path.join(recipes_dir, r, subfolder, "conanfile.py")
                conanfile_content = load(conanfile)
                if "from conans" in conanfile_content or "import conans" in conanfile_content:
                    excluded.add(r)
                    continue
                ret.append(RecipeReference.loads(ref))
        if excluded:
            ConanOutput().warning(f"Excluding recipes not Conan 2.0 ready: {', '.join(excluded)}")
        return ret

    def get_recipe_folder(self, ref):
        folder = self._get_base_folder(ref.name)
        data = self._load_config_yml(folder)
        if data is None:
            raise RecipeNotFoundException(ref)
        versions = data["versions"]
        if str(ref.version) not in versions:
            raise RecipeNotFoundException(ref)
        subfolder = versions[str(ref.version)]["folder"]
        return os.path.join(folder, subfolder)
