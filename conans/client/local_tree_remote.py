import copy
import os
from distutils.dir_util import copy_tree
from fnmatch import fnmatch

import yaml

from conan.tools.files import load
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.model.recipe_ref import RecipeReference


class LocalTreeApiClient:

    def __init__(self, remote, config):
        self._remote = remote
        self._config = config
        cache_folder = self._remote.url.replace("file://", "")
        self._remote_cache_dir = "{}/.cache/conan_remote".format(cache_folder)
        print(self._remote_cache_dir)
        from conans.cli.api.conan_api import ConanAPIV2
        self._conan_api = ConanAPIV2(self._remote_cache_dir)
        self._conan_api.out.stream = open(os.devnull, "w")
        self.layout = ConanCenterIndexLayout(cache_folder)

    def _export_recipe(self, ref):
        folder = self.layout.get_recipe_folder(ref)
        conanfile_path = os.path.join(folder, "conanfile.py")
        # FIXME: Redirect stdout to dev/null
        ref = self._conan_api.export.export(conanfile_path, ref.name, ref.version, ref.user,
                                            ref.channel)
        return ref

    def _get_recipe_layout(self, ref):
        from conans.cli.conan_app import ConanApp
        app = ConanApp(self._remote_cache_dir)
        return app.cache.ref_layout(ref)

    def _copy_files(self, source_folder, dest_folder):
        if not os.path.exists(source_folder):
            return {}
        copy_tree(source_folder, dest_folder)
        ret = {}
        for root, _, _files in os.walk(dest_folder):
            for _f in _files:
                rel = os.path.relpath(os.path.join(root, _f), dest_folder)
                ret[rel] = os.path.join(dest_folder, root, _f)
        return ret

    def get_recipe(self, ref, dest_folder):
        """Copy from the tmp cache exports to dest_folder"""
        assert ref.revision
        export_folder = self._get_recipe_layout(ref).export()
        return self._copy_files(export_folder, dest_folder)

    def get_recipe_sources(self, ref, dest_folder):
        export_sources = self._get_recipe_layout(ref).export_sources()
        return self._copy_files(export_sources, dest_folder)

    def search(self, pattern=None, ignorecase=True):
        ret = []
        for ref in self.layout.get_recipes_references():
            if fnmatch(str(ref), pattern):
                ret.append(ref)
        return ret

    def get_recipe_revisions_references(self, ref):
        ref = self._export_recipe(ref)
        tmp = copy.copy(ref)
        tmp.revision = None
        return self._conan_api.list.recipe_revisions(tmp)

    def get_latest_recipe_reference(self, ref):
        ref = self._export_recipe(ref)
        return ref

    def get_recipe_revision_reference(self, ref):
        ref = self._export_recipe(ref)
        if ref in self.get_recipe_revisions_references(ref):
            return ref
        else:
            raise RecipeNotFoundException(ref)

    # Not implemented methods
    def get_package_revisions_references(self, pref, headers=None):
        raise PackageNotFoundException(pref)

    def get_latest_package_reference(self, pref, headers):
        raise PackageNotFoundException(pref)

    def get_package_revision_reference(self, pref):
        raise PackageNotFoundException(pref)

    def get_recipe_file(self, ref, path):
        # Used in not present "conan get", could be easily implemented
        raise ConanException("Cannot read files for remote '{}'".format(self._remote.name))

    def remove_recipe(self, ref):
        raise ConanException("Remove not supported for remote '{}'".format(self._remote.name))

    def remove_all_packages(self, ref):
        raise ConanException("Remove not supported for remote '{}'".format(self._remote.name))

    def remove_packages(self, prefs):
        raise ConanException("Remove not supported for remote '{}'".format(self._remote.name))

    def get_recipe_snapshot(self, ref):
        # Only used in upload
        raise ConanException("Upload not supported for remote '{}'".format(self._remote.name))

    def upload_recipe(self, ref, files_to_upload, deleted):
        raise ConanException("Upload not supported for remote '{}'".format(self._remote.name))

    def upload_package(self, pref, files_to_upload):
        raise ConanException("Upload not supported for remote '{}'".format(self._remote.name))

    def authenticate(self, user, password):
        raise ConanException("This remote do not support authentication "
                             "'{}'".format(self._remote.name))

    def search_packages(self, reference):
        raise ConanException("The remote '{}' doesn't support binary "
                             "packages".format(self._remote.name))

    def get_package(self, pref, dest_folder):
        raise PackageNotFoundException(pref)

    def get_package_file(self, pref, path):
        raise ConanException("The remote '{}' doesn't support binary "
                             "packages".format(self._remote.name))


class ConanCenterIndexLayout:

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
