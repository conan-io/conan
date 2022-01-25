import copy
import os
from distutils.dir_util import copy_tree

import yaml

from conan.tools.files import load
from conans.errors import ConanException, PackageNotFoundException, RecipeNotFoundException
from conans.paths import get_conan_user_home


class GitRepoRemote:

    def __init__(self, remote, config):
        self._remote = remote
        self._config = config
        self._remote_cache_dir = "{}/git-remote-caches/{}".format(get_conan_user_home(),
                                                                  self._remote.name)
        from conans.cli.api.conan_api import ConanAPIV2
        self._conan_api = ConanAPIV2(self._remote_cache_dir)
        self._conan_api.out.stream = open(os.devnull, "w")
        self.layout = ConanCenterIndexLayout(self._remote.url)

    def _export_recipe(self, ref):
        folder = self.layout.get_recipe_folder(ref)
        conanfile_path = os.path.join(folder, "conanfile.py")
        # FIXME: Redirect stdout to dev/null
        ref = self._conan_api.export.export(conanfile_path, ref.name, ref.version, ref.user,
                                            ref.channel)
        return ref

    def _raise_package_not_implemented(self):
        raise ConanException("The remote {} doesn't support binary packages")

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
        print(ret)
        return ret

    def get_recipe(self, ref, dest_folder):
        """Copy from the tmp cache exports to dest_folder"""
        print("\n\nget_recipe\n\n")
        assert ref.revision
        export_folder = self._get_recipe_layout(ref).export()
        return self._copy_files(export_folder, dest_folder)

    def get_recipe_snapshot(self, ref):
        print("\n\nget_recipe_snapshot\n\n")

    def get_recipe_sources(self, ref, dest_folder):
        print("\n\nget_recipe_sources\n\n")
        export_sources = self._get_recipe_layout(ref).export_sources()
        return self._copy_files(export_sources, dest_folder)

    def get_package(self, pref, dest_folder):
        raise PackageNotFoundException(pref)

    def get_recipe_file(self, ref, path):
        print("\n\nget_recipe_file\n\n")

    def get_package_file(self, pref, path):
        self._raise_package_not_implemented()

    def upload_recipe(self, ref, files_to_upload, deleted):
        raise ConanException("Upload not supported for repo {}".format(self._remote.name))

    def upload_package(self, pref, files_to_upload):
        raise ConanException("Upload not supported for repo {}".format(self._remote.name))

    def authenticate(self, user, password):
        return "", ""

    def check_credentials(self):
        print("check_credentials")

    def search(self, pattern=None, ignorecase=True):
        print("\n\nsearch\n\n")

    def search_packages(self, reference):
        self._raise_package_not_implemented()

    def remove_recipe(self, ref):
        raise ConanException("Remove not supported for repo {}".format(self.repo.name))

    def remove_all_packages(self, ref):
        raise ConanException("Remove not supported for repo {}".format(self.repo.name))

    def remove_packages(self, prefs):
        raise ConanException("Remove not supported for repo {}".format(self.repo.name))

    def server_capabilities(self):
        return []

    def get_recipe_revisions_references(self, ref):
        print("\n\nget_recipe_revisions_references\n\n")
        tmp = copy.copy(ref)
        tmp.revision = None
        return self._conan_api.list.recipe_revisions(tmp)

    def get_package_revisions_references(self, pref, headers=None):
        raise PackageNotFoundException(pref)

    def get_latest_recipe_reference(self, ref):
        print("\n\nget_latest_recipe_reference\n\n")
        ref = self._export_recipe(ref)
        return ref

    def get_latest_package_reference(self, pref, headers):
        raise PackageNotFoundException(pref)

    def get_recipe_revision_reference(self, ref):
        print("\n\get_recipe_revision_reference\n\n")

    def get_package_revision_reference(self, pref):
        raise PackageNotFoundException(pref)


class ConanCenterIndexLayout:

    def __init__(self, base_folder):
        self._base_folder = base_folder

    def get_base_folder(self, ref):
        return os.path.join(self._base_folder, "recipes", ref.name)

    def _load_config_yml(self, ref):
        content = load(None, os.path.join(self.get_base_folder(ref), "config.yml"))
        return yaml.safe_load(content)

    def get_recipe_folder(self, ref):
        data = self._load_config_yml(ref)
        versions = data["versions"]
        if str(ref.version) not in versions:
            raise RecipeNotFoundException(ref)
        subfolder = versions[str(ref.version)]["folder"]
        return os.path.join(self.get_base_folder(ref), subfolder)
