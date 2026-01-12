import os
import textwrap
from pathlib import Path

from conan.api.model import RecipeReference
from conan.api.output import ConanOutput
from conan.cli import make_abs_path
from conan.internal.paths import CONANFILE
from conan.internal.util.files import save


class InitAPI:

    def __init__(self, conan_api):
        self._conan_api = conan_api

    def save_conanfile(self, path, ref):
        ref = RecipeReference.loads(ref)
        abs_path = make_abs_path(path)
        os.makedirs(abs_path, exist_ok=True)
        ws_py_file = Path(abs_path, CONANFILE)
        if not ws_py_file.exists():
            ConanOutput().success(f"Created minimal {CONANFILE} in {path}")
            save(ws_py_file, textwrap.dedent(f"""\
            from conan import ConanFile

            class {ref.name}Conan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                name = "{ref.name}"
                version = "{ref.version}"
            """))
