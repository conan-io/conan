import os
from conan.api.output import Color
from conan.tools.files import save


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
        for key, value in self.variables.items():
            line = f"export {key}=\"{value}\""
            content.append(line)
        conanrun_path = os.path.join(output_folder, "conanrun.sh")
        content.append(f". \"{conanrun_path}\"")
        filename = f"{self.filename}.bash"
        conanrosenv_path = os.path.join(output_folder, filename)
        save(self, conanrosenv_path, "\n".join(content))

        msg = f"Generated ROSEnv Conan file: {filename}\n" + \
              f"Use 'source {conanrosenv_path}' to set the ROSEnv Conan before 'colcon build'"
        self._conanfile.output.info(msg, fg=Color.CYAN)
