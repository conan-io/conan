import os
from pathlib import Path

import yaml

from conan.api.output import ConanOutput
from conans.client.loader import load_python_file
from conan.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load, save


def _find_ws_folder():
    path = Path(os.getcwd())
    while path.is_dir() and len(path.parts) > 1:  # finish at '/'
        if (path / "conanws.yml").is_file() or (path / "conanws.py").is_file():
            return str(path)
        else:
            path = path.parent


class _UserWorkspaceAPI:
    def __init__(self, folder):
        self.folder = folder

    def load(self, conanfile_path):
        conanfile_path = os.path.join(self.folder, conanfile_path)
        from conans.client.loader import ConanFileLoader
        loader = ConanFileLoader(pyreq_loader=None, conanfile_helpers=None)
        conanfile = loader.load_named(conanfile_path, name=None, version=None, user=None,
                                      channel=None, remotes=None, graph_lock=None)
        return conanfile


class Workspace:
    TEST_ENABLED = False

    def __init__(self):
        self._folder = _find_ws_folder()
        if self._folder:
            ConanOutput().warning(f"Workspace found: {self._folder}")
            if (Workspace.TEST_ENABLED or os.getenv("CONAN_WORKSPACE_ENABLE")) != "will_break_next":
                ConanOutput().warning("Workspace ignored as CONAN_WORKSPACE_ENABLE is not set")
                self._folder = None
            else:
                ConanOutput().warning(f"Workspace is a dev-only feature, exclusively for testing")

        self._yml = None
        self._py = None
        if self._folder is not None:
            self._yml_file = os.path.join(self._folder, "conanws.yml")
            if os.path.exists(self._yml_file):
                try:
                    self._yml = yaml.safe_load(load(self._yml_file))
                except Exception as e:
                    raise ConanException(f"Invalid workspace yml format at {self._folder}: {e}")

            py_file = os.path.join(self._folder, "conanws.py")
            if os.path.exists(py_file):
                self._py, _ = load_python_file(py_file)
                setattr(self._py, "workspace_api", _UserWorkspaceAPI(self._folder))
                setattr(self._py, "conanws_data", self._yml)

    @property
    def name(self):
        return self._attr("name") or os.path.basename(self._folder)

    @property
    def folder(self):
        return self._folder

    def _attr(self, value):
        if self._py and getattr(self._py, value, None):
            attr = getattr(self._py, value)
            return attr() if callable(attr) else attr
        if self._yml:
            return self._yml.get(value)

    def home_folder(self):
        if not self._folder:
            return
        home = self._attr("home_folder")
        if home is None or os.path.isabs(home):
            return home
        return os.path.normpath(os.path.join(self._folder, home))

    def config_folder(self):
        folder = self._attr("config_folder")
        if folder is None or os.path.isabs(folder):
            return folder
        return os.path.normpath(os.path.join(self._folder, folder))

    def _check_ws(self):
        if not self._folder:
            raise ConanException("Workspace not defined, please create a "
                                 "'conanws.py' or 'conanws.yml' file")

    def add(self, ref, path, output_folder):
        """
        Add a new editable to the current workspace 'conanws.yml' file.
        If existing, the 'conanws.py' must use this via 'conanws_data' attribute
        """
        self._check_ws()
        self._yml = self._yml or {}
        editable = {"path": self._rel_path(path)}
        if output_folder:
            editable["output_folder"] = self._rel_path(output_folder)
        self._yml.setdefault("editables", {})[str(ref)] = editable
        save(self._yml_file, yaml.dump(self._yml))

    def _rel_path(self, path):
        if path is None:
            return None
        if not os.path.isabs(path):
            raise ConanException(f"Editable path must be absolute: {path}")
        path = os.path.relpath(path, self._folder)
        if path.startswith(".."):
            raise ConanException(f"Editable path must be inside the workspace folder: "
                                 f"{self._folder}")
        return path.replace("\\", "/")  # Normalize to unix path

    def remove(self, path):
        self._check_ws()
        self._yml = self._yml or {}
        found_ref = None
        path = self._rel_path(path)
        for ref, info in self._yml.get("editables", {}).items():
            if os.path.dirname(info["path"]).replace("\\", "/") == path:
                found_ref = ref
                break
        if not found_ref:
            raise ConanException(f"No editable package to remove from this path: {path}")
        self._yml["editables"].pop(found_ref)
        save(self._yml_file, yaml.dump(self._yml))
        return found_ref

    def editables(self):
        if not self._folder:
            return
        editables = self._attr("editables")
        if editables:
            editables = {RecipeReference.loads(r): v.copy() for r, v in editables.items()}
            for v in editables.values():
                v["path"] = os.path.normpath(os.path.join(self._folder, v["path"]))
                if v.get("output_folder"):
                    v["output_folder"] = os.path.normpath(os.path.join(self._folder,
                                                                       v["output_folder"]))
        return editables

    def serialize(self):
        self._check_ws()
        return {"name": self.name,
                "folder": self._folder,
                "editables": self._attr("editables")}
