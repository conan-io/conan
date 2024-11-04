import os
from pathlib import Path

import yaml

from conans.client.loader import load_python_file
from conan.errors import ConanException
from conans.util.files import load, save


def _find_ws_folder():
    path = Path(os.getcwd())
    while path.is_dir() and len(path.parts) > 1:  # finish at '/'
        if (path / "conanws.yml").is_file() or (path / "conanws.py").is_file():
            return str(path)
        else:
            path = path.parent


class Workspace:
    def __init__(self):
        self._folder = _find_ws_folder()
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
        self._yml.setdefault("editables", {})[str(ref)] = {"path": path,
                                                           "output_folder": output_folder}
        save(self._yml_file, yaml.dump(self._yml))

    def remove(self, path):
        self._check_ws()
        self._yml = self._yml or {}
        found_ref = None
        path = path.replace("\\", "/")
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
            for v in editables.values():
                v["workspace"] = {"name": self.name,
                                  "folder": self._folder}
        return editables

    def serialize(self):
        return {"name": self.name,
                "folder": self._folder,
                "editables": self._attr("editables")}
