import os
from pathlib import Path

from conan.api.model import RecipeReference
from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.model.workspace import load_workspace


def _find_ws_folder():
    path = Path(os.getcwd())
    while path.is_dir() and len(path.parts) > 1:  # finish at '/'
        if (path / "conanws.yml").is_file() or (path / "conanws.py").is_file():
            return str(path)
        else:
            path = path.parent


class Workspace:
    TEST_ENABLED = False

    def __init__(self, conan_api):
        self._conan_api = conan_api
        self._folder = _find_ws_folder()
        if self._folder:
            ConanOutput().warning(f"Workspace found: {self._folder}")
            if (Workspace.TEST_ENABLED or os.getenv("CONAN_WORKSPACE_ENABLE")) != "will_break_next":
                ConanOutput().warning("Workspace ignored as CONAN_WORKSPACE_ENABLE is not set")
                self._folder = None
            else:
                ConanOutput().warning(f"Workspace is a dev-only feature, exclusively for testing")
                self._ws = load_workspace(self._folder, conan_api)  # Error if not loading

    @property
    def folder(self):
        return self._folder

    def home_folder(self):
        if not self._folder:
            return
        folder = self._ws.home_folder()

        if folder is None or os.path.isabs(folder):
            return folder
        return os.path.normpath(os.path.join(self._folder, folder))

    def _check_ws(self):
        if not self._folder:
            raise ConanException("Workspace not defined, please create a "
                                 "'conanws.py' or 'conanws.yml' file")

    def add(self, ref, path, output_folder, product=False):
        """
        Add a new editable to the current workspace 'conanws.yml' file.
        If existing, the 'conanws.py' must use this via 'conanws_data' attribute
        """
        self._check_ws()
        self._ws.add(ref, path, output_folder, product)

    @property
    def name(self):
        self._check_ws()
        return self._ws.name()

    @property
    def products(self):
        self._check_ws()
        return self._ws.products()

    def editable_from_path(self, path):
        editables = self._ws.editables()
        for ref, info in editables.items():
            if info["path"].replace("\\", "/") == path:
                return RecipeReference.loads(ref)

    def remove(self, path):
        self._check_ws()
        return self._ws.remove(path)

    def editables(self):
        """
        @return: Returns {RecipeReference: {"path": full abs-path, "output_folder": abs-path}}
        """
        if not self._folder:
            return
        editables = self._ws.editables()
        editables = {RecipeReference.loads(r): v.copy() for r, v in editables.items()}
        for v in editables.values():
            path = os.path.normpath(os.path.join(self.folder, v["path"], "conanfile.py"))
            if not os.path.isfile(path):
                raise ConanException(f"Workspace editable not found: {path}")
            v["path"] = path
            if v.get("output_folder"):
                v["output_folder"] = os.path.normpath(os.path.join(self.folder,
                                                                   v["output_folder"]))
        return editables

    def serialize(self):
        self._check_ws()
        return {"name": self.name,
                "folder": self._folder,
                "products": self.products,
                "editables": self._ws.editables()}
