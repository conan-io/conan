import os
from conan.api.output import Color
from conan.tools.files import save
from conan.errors import ConanException


cmake_toolchain_exists_bash = """\
if [ ! -e "$CMAKE_TOOLCHAIN_FILE" ]; then
    echo "Error: CMAKE_TOOLCHAIN_FILE path not found at '$CMAKE_TOOLCHAIN_FILE'."
    echo "Make sure you are using CMakeToolchain and CMakeDeps generators too."
    exit 1
fi
"""


class ROSEnv(object):
    """
    Generator to serve as integration for Robot Operating System 2 development workspaces.
    It generates a conanrosenv.bash file that when sources sets variables so the Conan
    dependencies are found by CMake and the run environment is also set.

    IMPORTANT: This generator should be used together with CMakeDeps and CMakeToolchain generators.
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.filename = "conanrosenv"
        self.variables = {}

    def generate(self):
        output_folder = self._conanfile.generators_folder
        self.variables.setdefault("CMAKE_TOOLCHAIN_FILE",
                                  os.path.join(output_folder, "conan_toolchain.cmake"))
        build_type = self._conanfile.settings.get_safe("build_type")
        if build_type:
            self.variables.setdefault("CMAKE_BUILD_TYPE", build_type)

        content = []
        # TODO: Support ps1 and zsh script generation for Windows/Macos
        if self._conanfile.settings.get_safe("os") == "Windows":
            raise ConanException("ROSEnv generator does not support Windows")
        for key, value in self.variables.items():
            content.append(f"{key}=\"{value}\"")
            content.append(f"export {key}")
        conanrun_path = os.path.join(output_folder, "conanrun.sh")
        content.append(f". \"{conanrun_path}\"")
        filename = f"{self.filename}.bash"
        content.append(cmake_toolchain_exists_bash)
        conanrosenv_path = os.path.join(output_folder, filename)
        save(self, conanrosenv_path, "\n".join(content))

        msg = f"Generated ROSEnv Conan file: {filename}\n" + \
              f"Use 'source {conanrosenv_path}' to set the ROSEnv Conan before 'colcon build'"
        self._conanfile.output.info(msg, fg=Color.CYAN)
