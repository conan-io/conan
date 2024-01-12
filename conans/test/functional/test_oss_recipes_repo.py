import os
import textwrap

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.file_server import TestFileServer
from conans.test.utils.scm import create_local_git_repo, git_add_changes_commit
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, zipdir
from conans.util.files import save_files, sha256sum


class TestConanNewOssRecipe:
    def test_conan_new_oss_recipe(self):
        # Setup the release pkg0.1.zip http server
        file_server = TestFileServer()
        zippath = os.path.join(file_server.store, "pkg0.1.zip")
        repo_folder = temp_folder()
        cmake = gen_cmakelists(libname="pkg", libsources=["pkg.cpp"], install=True,
                               public_header="pkg.h")
        save_files(repo_folder, {"CMakeLists.txt": cmake,
                                 "pkg.h": gen_function_h(name="pkg"),
                                 "pkg.cpp": gen_function_cpp(name="pkg")})
        zipdir(repo_folder, zippath)
        sha256 = sha256sum(zippath)
        url = f"{file_server.fake_url}/pkg0.1.zip"

        c0 = TestClient()
        c0.run(f"new oss_recipe -d name=pkg -d version=0.1 -d url={url} -d sha256={sha256}")
        oss_recipe_repo = c0.current_folder

        c = TestClient()
        c.servers["file_server"] = file_server
        c.run(f"remote add local '{oss_recipe_repo}' --type=oss-recipes")
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=pkg/0.1")
        c.run("create . --build=missing")
        assert "pkg: Release!" in c.out


class TestInRepo:
    def test_in_repo(self):
        """testing that it is possible to put a "recipes" folder inside a source repo, and
        use it as oss-recipes-repository, exporting the source from itself
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
        c.run(f"remote add local '{repo_folder}' --type=oss-recipes")
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=pkg/0.1")
        c.run("create . --build=missing")
        assert "pkg: Release!" in c.out

        # Of course the recipe can also be created locally
        path = os.path.join(repo_folder, "recipes/pkg/all")
        c.run(f'create "{path}" --version=0.1')
        assert "pkg/0.1: Created package" in c.out


class TestOssRecipeGit:
    def test_conan_new_oss_recipe(self):
        # save repo
        config_yml = textwrap.dedent("""\
            versions:
              "0.1":
                folder: all
            """)
        conanfile = GenConanfile("pkg")
        files = {"recipes/pkg/config.yml": config_yml,
                 "recipes/pkg/all/conanfile.py": str(conanfile)}
        url_folder, commit = create_local_git_repo(files)

        c = TestClient()
        c.run(f'remote add local "{url_folder}" --type=oss-recipes-git')
        c.run("list *:* -r=local")
        assert "Remote local not cloned yet" in c.out
        assert "pkg/0.1" in c.out
        c.run("list *:* -r=local")
        assert "Remote local not cloned yet" not in c.out
        assert "pkg/0.1" in c.out

        config_yml = textwrap.dedent("""\
            versions:
              "0.1":
                folder: all
              "0.2":
                folder: all
            """)
        save_files(url_folder, {"recipes/pkg/config.yml": config_yml})
        git_add_changes_commit(url_folder)
        c.run("list *:* -r=local")
        assert "pkg/0.1" in c.out
        assert "pkg/0.2" not in c.out
        c.run("remote pull local")
        c.run("list *:* -r=local")
        assert "pkg/0.1" in c.out
        assert "pkg/0.2" in c.out
