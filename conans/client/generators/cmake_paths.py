from conans.client.generators.cmake import DepsCppCmake
from conans.model import Generator


class CMakePathsGenerator(Generator):

    @property
    def filename(self):
        return "conan_paths.cmake"

    @property
    def content(self):
        deps = DepsCppCmake(self.deps_build_info)

        return """set(CMAKE_MODULE_PATH {deps.build_paths} ${{CMAKE_MODULE_PATH}} ${{CMAKE_CURRENT_LIST_DIR}} )
set(CMAKE_PREFIX_PATH {deps.build_paths} ${{CMAKE_PREFIX_PATH}} ${{CMAKE_CURRENT_LIST_DIR}} )
""".format(deps=deps)
