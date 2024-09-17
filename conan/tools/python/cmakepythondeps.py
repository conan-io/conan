from conan.tools.python.virtualenv import PythonVirtualEnv
from conans import tools
from pathlib import Path
import os
import json
import textwrap
import sys


class CMakePythonDeps(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def binpath(self):
        return "Scripts" if sys.platform == "win32" else "bin"

    @property
    def content(self):
        config = {}
        for dep_name, user_info in self._conanfile.deps_user_info.items():
            requirements = {}
            virtualenv = PythonVirtualEnv(self._conanfile)
            package_targets = {}
            if "python_requirements" in user_info.vars:
                requirements = json.loads(user_info.python_requirements)

            if "python_envdir" in user_info.vars:
                path = Path(user_info.python_envdir, self.binpath, "python")
                realname = path.resolve(strict=True).name
                interpreter = str(path.with_name(realname))
                virtualenv = PythonVirtualEnv(
                    self._conanfile,
                    python=interpreter,
                    env_folder=user_info.python_envdir,
                )

            for requirement in requirements:
                package = requirement.split("==")[0]
                entry_points = virtualenv.entry_points(package)
                package_targets[package] = entry_points.get("console_scripts", [])

            extension = ""
            if self._conanfile.settings.os == "Windows":
                extension = ".exe"
            for package, targets in package_targets.items():
                for target in targets:
                    exe_path = None
                    for path_ in [
                        Path(self.binpath, f"{target}{extension}"),
                        Path("lib", f"{target}{extension}"),
                    ]:
                        if Path(user_info.python_envdir, path_).is_file():
                            exe_path = Path(user_info.python_envdir, path_)
                            break
                    if not exe_path:
                        self.output.warn(f"Could not find path to {target}{extension}")
                    else:
                        filename = f"{package}-config.cmake"
                        config[filename] = config.get(filename, "") + textwrap.dedent(
                            f"""\
                            if(NOT TARGET {package}::{target})
                                add_executable({package}::{target} IMPORTED)
                                set_target_properties({package}::{target} PROPERTIES IMPORTED_LOCATION {exe_path})
                            endif()
                            """
                        )

        return config

    def generate(self):
        for filename, content in self.content.items():
            tools.save(
                os.path.join(self._conanfile.generators_folder, filename), content
            )
