import os

import yaml

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conans.util.files import load, save


class Workspace:
    """
    The base class for all workspaces
    """

    def __init__(self, folder, conan_api):
        self.folder = folder
        self.conan_data = self._conan_load_data()
        self._conan_api = conan_api
        self.output = ConanOutput(scope=self.name())

    def name(self):
        return os.path.basename(self.folder)

    def _conan_load_data(self):
        data_path = os.path.join(self.folder, "conanws.yml")
        if not os.path.exists(data_path):
            return {}
        try:
            data = yaml.safe_load(load(data_path))
        except Exception as e:
            raise ConanException("Invalid yml format at {}: {}".format("conanws.yml", e))
        return data or {}

    def home_folder(self):
        return self.conan_data.get("home_folder")

    def add(self, ref, path, output_folder, product=False):
        assert os.path.isfile(path)
        path = self._conan_rel_path(os.path.dirname(path))
        editable = {"path": path}
        if output_folder:
            editable["output_folder"] = self._conan_rel_path(output_folder)
        self.conan_data.setdefault("editables", {})[str(ref)] = editable
        if product:
            self.conan_data.setdefault("products", []).append(path)
        save(os.path.join(self.folder, "conanws.yml"), yaml.dump(self.conan_data))

    def remove(self, path):
        found_ref = None
        path = self._conan_rel_path(path)
        for ref, info in self.conan_data.get("editables", {}).items():
            if info["path"].replace("\\", "/") == path:
                found_ref = ref
                break
        if not found_ref:
            raise ConanException(f"No editable package to remove from this path: {path}")
        self.conan_data["editables"].pop(found_ref)
        if path in self.conan_data.get("products", []):
            self.conan_data["products"].remove(path)
        save(os.path.join(self.folder, "conanws.yml"), yaml.dump(self.conan_data))
        return found_ref

    def _conan_rel_path(self, path):
        if path is None:
            return None
        if not os.path.isabs(path):
            raise ConanException(f"Editable path must be absolute: {path}")
        path = os.path.relpath(path, self.folder)
        if path.startswith(".."):
            raise ConanException(f"Editable path must be inside the workspace folder: "
                                 f"{self.folder}")
        return path.replace("\\", "/")  # Normalize to unix path

    def editables(self):
        return self.conan_data.get("editables", {})

    def products(self):
        return self.conan_data.get("products", [])

    def load_conanfile(self, conanfile_path):
        conanfile_path = os.path.join(self.folder, conanfile_path, "conanfile.py")
        from conans.client.loader import ConanFileLoader
        from conan.internal.cache.home_paths import HomePaths
        from conan.internal.conan_app import ConanFileHelpers, CmdWrapper
        cmd_wrap = CmdWrapper(HomePaths(self._conan_api.home_folder).wrapper_path)
        helpers = ConanFileHelpers(None, cmd_wrap, self._conan_api.config.global_conf,
                                   cache=None, home_folder=self._conan_api.home_folder)
        loader = ConanFileLoader(pyreq_loader=None, conanfile_helpers=helpers)
        conanfile = loader.load_named(conanfile_path, name=None, version=None, user=None,
                                      channel=None, remotes=None, graph_lock=None)
        return conanfile

    def root_conanfile(self):  # noqa
        return None
