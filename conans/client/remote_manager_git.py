import json
import os
import sys
from distutils.dir_util import copy_tree
from fnmatch import fnmatch
from io import StringIO

import yaml

from conan.api.output import ConanOutput
from conans.client.cmd.export import cmd_export
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load, save


class GitRemoteManager:

    def __init__(self, remote):
        self._remote = remote
        cache_folder = self._remote.url.replace("file:///", "")
        self._remote_cache_dir = "{}/.cache".format(cache_folder)
        self._exported_file = os.path.join(self._remote_cache_dir, "exported.json")
        from conan.internal.conan_app import ConanApp
        self._app = ConanApp(self._remote_cache_dir)
        self.layout = _ConanCenterIndexLayout(cache_folder)

    def call_method(self, method_name, *args, **kwargs):
        return getattr(self, method_name)(*args, **kwargs)

    def get_recipe(self, ref, dest_folder):
        export_folder = self._app.cache.ref_layout(ref).export()
        return self._copy_files(export_folder, dest_folder)

    def get_recipe_sources(self, ref, dest_folder):
        export_sources = self._app.cache.ref_layout(ref).export_sources()
        return self._copy_files(export_sources, dest_folder)

    def get_package(self, pref, dest_folder):
        raise ConanException(f"The remote '{self._remote.name}' doesn't support binary packages")

    def upload_recipe(self, ref, files_to_upload):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support upload")

    def upload_package(self, pref, files_to_upload):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support upload")

    def authenticate(self, user, password):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support authentication")

    def check_credentials(self):
        raise ConanException(f"Git remote '{self._remote.name}' doesn't support check credentials")

    def search(self, pattern=None, ignorecase=True):
        return self.layout.get_recipes_references(pattern)

    def search_packages(self, reference):
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
        exported = load(self._exported_file) if os.path.isfile(self._exported_file) else "{}"
        exported = json.loads(exported)
        existing = exported.get(str(ref))
        if existing is not None:
            return RecipeReference.loads(existing["ref"])

        folder = self.layout.get_recipe_folder(ref)
        conanfile_path = os.path.join(folder, "conanfile.py")
        original_stderr = sys.stderr
        sys.stderr = StringIO()
        try:
            original_stderr.write(f"Git remote processing {ref}\n")
            new_ref, _ = cmd_export(self._app, conanfile_path, ref.name, ref.version, None, None)
        finally:
            sys.stderr = original_stderr
        # Cache the result, so it is not constantly re-exported
        exported[str(ref)] = {"ref": repr(new_ref)}
        save(self._exported_file, json.dumps(exported))
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

    def _load_config_yml(self, recipe_name):
        content = load(os.path.join(self._get_base_folder(recipe_name), "config.yml"))
        return yaml.safe_load(content)

    def get_recipes_references(self, pattern):
        recipes_dir = os.path.join(self._base_folder, "recipes")
        recipes = os.listdir(recipes_dir)
        recipes.sort()
        ret = []
        excluded = set()
        for r in recipes:
            config_yml = self._load_config_yml(r)
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
                if "from conans" in conanfile_content or "import conants" in conanfile_content:
                    excluded.add(r)
                    continue
                ret.append(RecipeReference.loads(ref))
        if excluded:
            ConanOutput().warning(f"Excluding recipes not Conan 2.0 ready: {', '.join(excluded)}")
        return ret

    def get_recipe_folder(self, ref):
        data = self._load_config_yml(ref.name)
        versions = data["versions"]
        if str(ref.version) not in versions:
            raise RecipeNotFoundException(ref)
        subfolder = versions[str(ref.version)]["folder"]
        return os.path.join(self._get_base_folder(ref.name), subfolder)
