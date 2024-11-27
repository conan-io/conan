import os
import textwrap

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.file_server import TestFileServer
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, zipdir
from conans.util.files import save_files, sha256sum


class TestLocalRecipeIndexNew:
    def test_conan_new_local_recipes_index(self):
        # Setup the release pkg0.1.zip http server
        file_server = TestFileServer()
        zippath = os.path.join(file_server.store, "pkg0.1.zip")
        repo_folder = temp_folder()
        cmake = gen_cmakelists(libname="pkg", libsources=["pkg.cpp"], install=True,
                               public_header="pkg.h")
        save_files(repo_folder, {"pkg/CMakeLists.txt": cmake,
                                 "pkg/pkg.h": gen_function_h(name="pkg"),
                                 "pkg/pkg.cpp": gen_function_cpp(name="pkg")})
        zipdir(repo_folder, zippath)
        sha256 = sha256sum(zippath)
        url = f"{file_server.fake_url}/pkg0.1.zip"

        c0 = TestClient()
        c0.servers["file_server"] = file_server
        c0.run(f"new local_recipes_index -d name=pkg -d version=0.1 -d url={url} -d sha256={sha256}")
        # A local create is possible, and it includes a test_package
        c0.run("create recipes/pkg/all --version=0.1")
        assert "pkg: Release!" in c0.out
        remote_folder = c0.current_folder

        c = TestClient()
        c.servers["file_server"] = file_server
        c.run(f"remote add local '{remote_folder}'")
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=pkg/0.1")
        c.run("create . --version=0.1 --build=missing")
        assert "pkg: Release!" in c.out


class TestInRepo:
    def test_in_repo(self):
        """testing that it is possible to put a "recipes" folder inside a source repo, and
        use it as local-recipes-index repository, exporting the source from itself
        """
        repo_folder = temp_folder()
        cmake = gen_cmakelists(libname="pkg", libsources=["pkg.cpp"], install=True,
                               public_header="pkg.h")
        config_yml = textwrap.dedent("""\
            versions:
              "0.1":
                folder: all
            """)
        conanfile = textwrap.dedent("""\
            import os
            from conan import ConanFile
            from conan.tools.cmake import CMake, cmake_layout
            from conan.tools.files import copy

            class PkgRecipe(ConanFile):
                name = "pkg"
                package_type = "library"

                # Binary configuration
                settings = "os", "compiler", "build_type", "arch"
                options = {"shared": [True, False], "fPIC": [True, False]}
                default_options = {"shared": False, "fPIC": True}

                generators = "CMakeToolchain"

                def export_sources(self):
                    src = os.path.dirname(os.path.dirname(os.path.dirname(self.recipe_folder)))
                    copy(self, "*", src=src, dst=self.export_sources_folder, excludes=["recipes*"])

                def config_options(self):
                    if self.settings.os == "Windows":
                        self.options.rm_safe("fPIC")

                def configure(self):
                    if self.options.shared:
                        self.options.rm_safe("fPIC")

                def layout(self):
                    cmake_layout(self)

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    cmake = CMake(self)
                    cmake.install()

                def package_info(self):
                    self.cpp_info.libs = [self.name]
            """)

        save_files(repo_folder, {"recipes/pkg/config.yml": config_yml,
                                 "recipes/pkg/all/conanfile.py": conanfile,
                                 "CMakeLists.txt": cmake,
                                 "pkg.h": gen_function_h(name="pkg"),
                                 "pkg.cpp": gen_function_cpp(name="pkg")})

        c = TestClient()
        c.run(f"remote add local '{repo_folder}'")
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=pkg/0.1")
        c.run("create . --build=missing")
        assert "pkg: Release!" in c.out

        # Of course the recipe can also be created locally
        path = os.path.join(repo_folder, "recipes/pkg/all")
        c.run(f'create "{path}" --version=0.1')
        assert "pkg/0.1: Created package" in c.out

        # Finally lets remove the remote, check that the clone is cleared
        c.run('remote remove local')
        assert "Removing temporary files for 'local' local-recipes-index remote" in c.out

    def test_not_found(self):
        """testing that the correct exception is raised when a recipe is not found
        """
        repo1_folder = temp_folder()
        repo2_folder = temp_folder()
        config_yml = textwrap.dedent("""\
            versions:
              "0.1":
                folder: all
            """)
        conanfile = textwrap.dedent("""\
            import os
            from conan import ConanFile
            from conan.tools.files import copy

            class PkgRecipe(ConanFile):
                name = "pkg"

                def export_sources(self):
                    copy(self, "*", src=self.recipe_folder, dst=self.export_sources_folder)
            """)

        save_files(repo2_folder, {"recipes/pkg/config.yml": config_yml,
                                  "recipes/pkg/all/conanfile.py": conanfile,
                                  "recipes/pkg/all/pkg.h": gen_function_h(name="pkg")})

        c = TestClient()
        c.run(f"remote add local1 '{repo1_folder}'")
        c.run(f"remote add local2 '{repo2_folder}'")
        c.run("install --requires=pkg/0.1 --build=missing")
        assert "Install finished successfully" in c.out
