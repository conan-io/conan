import json
import os
import shutil
import textwrap

import pytest

from conan.api.subapi.workspace import WorkspaceAPI
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.scm import create_local_git_repo
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save, save_files

WorkspaceAPI.TEST_ENABLED = "will_break_next"


class TestHomeRoot:
    def test_workspace_home_yml(self):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        save(os.path.join(folder, f"conanws.yml"), "home_folder: myhome")
        c = TestClient(current_folder=cwd, light=True)
        c.run("config home")
        assert os.path.join(folder, "myhome") in c.stdout

    def test_workspace_home_user_py(self):
        folder = temp_folder()
        cwd = os.path.join(folder, "sub1", "sub2")
        conanwspy = textwrap.dedent("""
            from conan import Workspace

            class MyWs(Workspace):
                def home_folder(self):
                    return "new" + self.conan_data["home_folder"]
            """)
        save(os.path.join(folder, f"conanws.py"), conanwspy)
        save(os.path.join(folder, "conanws.yml"), "home_folder: myhome")
        c = TestClient(current_folder=cwd, light=True)
        c.run("config home")
        assert os.path.join(folder, "newmyhome") in c.stdout

    def test_workspace_root(self):
        c = TestClient(light=True)
        # Just check the root command works
        c.run("workspace root", assert_error=True)
        assert "ERROR: No workspace defined, conanws.py file not found" in c.out

        # error, empty .py
        c.save({"conanws.py": ""})
        c.run("workspace root", assert_error=True)
        assert "Error loading conanws.py" in c.out
        assert "No subclass of Workspace" in c.out

        c.save({"conanws.yml": ""}, clean_first=True)
        c.run("workspace root")
        assert c.current_folder in c.stdout


class TestAddRemove:

    def test_add(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "dep2/conanfile.py": GenConanfile("dep2", "0.1"),
                "dep3/conanfile.py": GenConanfile("dep3", "0.1")})
        c.run("workspace add dep1")
        assert "Reference 'dep1/0.1' added to workspace" in c.out
        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out
        c.run("editable list")  # No editables in global
        assert "dep1" not in c.out
        assert "dep2" not in c.out
        c.run("workspace add dep2")
        assert "Reference 'dep2/0.1' added to workspace" in c.out
        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        with c.chdir(temp_folder()):  # If we move to another folder, outside WS, no editables
            c.run("editable list")
            assert "dep1" not in c.out
            assert "dep2" not in c.out

        c.run("workspace info")
        assert "dep1/0.1" in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace remove dep1")
        c.run("workspace info")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" in c.out

        c.run("workspace remove dep2")
        c.run("workspace info")
        assert "dep1/0.1" not in c.out
        assert "dep2/0.1" not in c.out

    def test_add_from_outside(self):
        c = TestClient(light=True)
        c.save({"sub/conanws.yml": "",
                "sub/dep1/conanfile.py": GenConanfile("dep1", "0.1"),
                "sub/dep2/conanfile.py": GenConanfile("dep2", "0.1")})
        with c.chdir("sub"):
            c.run("workspace add dep1")
            assert "Reference 'dep1/0.1' added to workspace" in c.out
            c.run("workspace add dep2")
            assert "Reference 'dep2/0.1' added to workspace" in c.out
            c.run("workspace info")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" in c.out
        assert c.load_home("editable_packages.json") is None

        c.run("editable list")
        assert "dep1" not in c.out
        assert "dep2" not in c.out
        assert c.load_home("editable_packages.json") is None
        with c.chdir("sub"):
            c.run("editable add dep1")
            assert c.load_home("editable_packages.json") is not None
            c.run("editable list")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" not in c.out
            c.run("workspace info")
            assert "dep1" in c.out
            assert "dep2" in c.out

        c.run("editable list")
        assert "dep1/0.1" in c.out
        assert "dep2" not in c.out

    @pytest.mark.parametrize("api", [False, True])
    def test_dynamic_editables(self, api):
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import load
            class Lib(ConanFile):
                def set_name(self):
                    self.name = load(self, os.path.join(self.recipe_folder, "name.txt"))
                def set_version(self):
                    self.version = load(self, os.path.join(self.recipe_folder, "version.txt"))
            """)
        if not api:
            workspace = textwrap.dedent("""\
                import os
                from conan import Workspace

                class MyWorkspace(Workspace):
                    def editables(self):
                        result = {}
                        for f in os.listdir(self.folder):
                            if os.path.isdir(os.path.join(self.folder, f)):
                                full_path = os.path.join(self.folder, f, "name.txt")
                                name = open(full_path).read().strip()
                                version = open(os.path.join(self.folder, f,
                                                            "version.txt")).read().strip()
                                result[f"{name}/{version}"] = {"path": f}
                        return result
                """)
        else:
            workspace = textwrap.dedent("""\
                import os
                from conan import Workspace

                class MyWorkspace(Workspace):
                    def editables(self):
                        result = {}
                        for f in os.listdir(self.folder):
                            if os.path.isdir(os.path.join(self.folder, f)):
                                conanfile = self.load_conanfile(f)
                                result[f"{conanfile.name}/{conanfile.version}"] = {"path": f}
                        return result
               """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile,
                "dep1/name.txt": "pkg",
                "dep1/version.txt": "2.1"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"pkg/2.1": {"path": "dep1"}}
        c.save({"dep1/name.txt": "other",
                "dep1/version.txt": "14.5"})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"other/14.5": {"path": "dep1"}}
        c.run("install --requires=other/14.5")
        # Doesn't fail
        assert "other/14.5 - Editable" in c.out
        with c.chdir("dep1"):
            c.run("install --requires=other/14.5")
            # Doesn't fail
            assert "other/14.5 - Editable" in c.out

    def test_api_dynamic_version_run(self):
        # https://github.com/conan-io/conan/issues/17306
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from io import StringIO
            from conan import ConanFile
            class Lib(ConanFile):
                name= "pkg"
                def set_version(self):
                    my_buf = StringIO()
                    self.run('echo 2.1', stdout=my_buf)
                    self.version = my_buf.getvalue().strip()
            """)

        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def editables(self):
                    conanfile = self.load_conanfile("dep1")
                    return {f"{conanfile.name}/{conanfile.version}": {"path": "dep1"}}
            """)

        c.save({"conanws.py": workspace,
                "dep1/conanfile.py": conanfile})
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["editables"] == {"pkg/2.1": {"path": "dep1"}}
        c.run("install --requires=pkg/2.1")
        # it will not fail

    def test_error_uppercase(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "conanfile.py": GenConanfile("Pkg", "0.1")})
        c.run("workspace add .", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out
        c.save({"conanfile.py": GenConanfile()})
        c.run("workspace add . --name=Pkg --version=0.1", assert_error=True)
        assert "ERROR: Conan packages names 'Pkg/0.1' must be all lowercase" in c.out

    def test_add_open_error(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "dep/conanfile.py": GenConanfile("dep", "0.1")})
        c.run("workspace add dep")
        c.run("workspace open dep/0.1", assert_error=True)
        assert "ERROR: Can't open a dependency that is already an editable: dep/0.1" in c.out

    def test_remove_product(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "mydeppkg/conanfile.py": GenConanfile("mydeppkg", "0.1")})
        c.run("workspace add mydeppkg --product")
        c.run("workspace remove mydeppkg")
        c.run("workspace info")
        assert "mydeppkg" not in c.out

    def test_remove_removed_folder(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": "",
                "mydeppkg/conanfile.py": GenConanfile("mydeppkg", "0.1")})
        c.run("workspace add mydeppkg")
        # If we now remove the folder
        shutil.rmtree(os.path.join(c.current_folder, "mydeppkg"))
        # It can still be removed by path, even if the path doesn't exist
        c.run("workspace remove mydeppkg")
        assert "Removed from workspace: mydeppkg/0.1" in c.out
        c.run("workspace info")
        assert "mydeppkg" not in c.out

    def test_custom_add_remove(self):
        c = TestClient(light=True)

        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def name(self):
                    return "myws"

                def add(self, ref, path, *args, **kwargs):
                    self.output.info(f"Adding {ref} at {path}")
                    super().add(ref, path, *args, **kwargs)

                def remove(self, path, *args, **kwargs):
                    self.output.info(f"Removing {path}")
                    return super().remove(path, *args, **kwargs)
            """)

        c.save({"conanws.py": workspace,
                "dep/conanfile.py": GenConanfile("dep", "0.1")})
        c.run("workspace add dep")
        assert "myws: Adding dep/0.1" in c.out
        c.run("workspace info")
        assert "dep/0.1" in c.out
        c.run("workspace remove dep")
        assert "myws: Removing" in c.out
        c.run("workspace info")
        assert "dep/0.1" not in c.out


class TestOpenAdd:
    def test_without_git(self):
        t = TestClient(default_server_user=True, light=True)
        t.save({"conanfile.py": GenConanfile("pkg", "0.1")})
        t.run("create .")
        t.run("upload * -r=default -c")

        c = TestClient(servers=t.servers, light=True)
        c.run(f"workspace open pkg/0.1")
        assert "name = 'pkg'" in c.load("pkg/conanfile.py")

        # The add should work the same
        c2 = TestClient(servers=t.servers, light=True)
        c2.save({"conanws.yml": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert "name = 'pkg'" in c2.load("pkg/conanfile.py")
        c2.run("workspace info")
        assert "pkg/0.1" in c2.out

    def test_without_git_export_sources(self):
        t = TestClient(default_server_user=True, light=True)
        t.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports_sources("*.txt"),
                "CMakeLists.txt": "mycmake"})
        t.run("create .")
        t.run("upload * -r=default -c")

        c = TestClient(servers=t.servers)
        c.run("workspace open pkg/0.1")
        assert "name = 'pkg'" in c.load("pkg/conanfile.py")
        assert "mycmake" in c.load("pkg/CMakeLists.txt")

    def test_workspace_git_scm(self):
        folder = temp_folder()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.scm import Git

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                def export(self):
                    git = Git(self)
                    git.coordinates_to_conandata()
            """)
        url, commit = create_local_git_repo(files={"conanfile.py": conanfile}, folder=folder,
                                            branch="mybranch")
        t1 = TestClient(default_server_user=True, light=True)
        t1.run_command('git clone "file://{}" .'.format(url))
        t1.run("create .")
        t1.run("upload * -r=default -c")

        c = TestClient(servers=t1.servers, light=True)
        c.run("workspace open pkg/0.1")
        assert c.load("pkg/conanfile.py") == conanfile

        c2 = TestClient(servers=t1.servers, light=True)
        c2.save({"conanws.yml": ""})
        c2.run(f"workspace add --ref=pkg/0.1")
        assert 'name = "pkg"' in c2.load("pkg/conanfile.py")
        c2.run("workspace info")
        assert "pkg/0.1" in c2.out

    def test_workspace_build_editables(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})

        c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_build_msg("BUILD PKGA!"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
                                                                .with_requires("pkga/0.1")})
        c.run("workspace add pkga")
        c.run("workspace add pkgb")

        c.run("install --requires=pkgb/0.1 --build=editable")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild"),
                                "pkgb/0.1": ("47a5f20ec8fb480e1c5794462089b01a3548fdc5",
                                             "EditableBuild")})
        assert "pkga/0.1: WARN: BUILD PKGA!" in c.out
        assert "pkgb/0.1: WARN: BUILD PKGB!" in c.out


class TestWorkspaceBuild:
    def test_dynamic_products(self):
        c = TestClient(light=True)

        workspace = textwrap.dedent("""\
            import os
            from conan import Workspace

            class MyWorkspace(Workspace):
                def products(self):
                    result = []
                    for f in os.listdir(self.folder):
                        if os.path.isdir(os.path.join(self.folder, f)):
                            if f.startswith("product"):
                                result.append(f)
                    return result
            """)

        c.save({"conanws.py": workspace,
                "lib1/conanfile.py": GenConanfile("lib1", "0.1"),
                "product_app1/conanfile.py": GenConanfile("app1", "0.1")})
        c.run("workspace add lib1")
        c.run("workspace add product_app1")
        c.run("workspace info --format=json")
        info = json.loads(c.stdout)
        assert info["products"] == ["product_app1"]

    def test_build(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})

        c.save({"pkga/conanfile.py": GenConanfile("pkga", "0.1").with_build_msg("BUILD PKGA!"),
                "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_build_msg("BUILD PKGB!")
               .with_requires("pkga/0.1")})
        c.run("workspace add pkga")
        c.run("workspace add pkgb --product")
        c.run("workspace info --format=json")
        assert json.loads(c.stdout)["products"] == ["pkgb"]
        c.run("workspace build")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild")})
        assert "pkga/0.1: WARN: BUILD PKGA!" in c.out
        assert "conanfile.py (pkgb/0.1): WARN: BUILD PKGB!" in c.out

        # It is also possible to build a specific package by path
        # equivalent to ``conan build <path> --build=editable``
        # This can be done even if it is not a product
        c.run("workspace build pkgc", assert_error=True)
        assert "ERROR: Product 'pkgc' not defined in the workspace as editable" in c.out
        c.run("workspace build pkgb")
        c.assert_listed_binary({"pkga/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                             "EditableBuild")})
        assert "pkga/0.1: WARN: BUILD PKGA!" in c.out
        assert "conanfile.py (pkgb/0.1): WARN: BUILD PKGB!" in c.out

        c.run("workspace build pkga")
        assert "conanfile.py (pkga/0.1): Calling build()" in c.out
        assert "conanfile.py (pkga/0.1): WARN: BUILD PKGA!" in c.out

    def test_error_if_no_products(self):
        c = TestClient(light=True)
        c.save({"conanws.yml": ""})
        c.run("workspace build", assert_error=True)
        assert "There are no products defined in the workspace, can't build" in c.out


class TestNew:
    def test_new(self):
        # Very basic workspace for testing
        c = TestClient(light=True)
        c.run("new workspace")
        assert 'name = "liba"' in c.load("liba/conanfile.py")
        c.run("workspace info")
        assert "liba/0.1" in c.out
        assert "libb/0.1" in c.out
        assert "app1/0.1" in c.out

    def test_new_dep(self):
        c = TestClient(light=True)
        c.run("new workspace -d requires=dep/0.1")
        assert 'self.requires("dep/0.1")' in c.load("liba/conanfile.py")
        assert 'name = "liba"' in c.load("liba/conanfile.py")
        c.run("workspace info")
        assert "liba/0.1" in c.out
        assert "libb/0.1" in c.out
        assert "app1/0.1" in c.out


class TestMeta:
    def test_install(self):
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile()})
        c.run("create dep --name=dep1 --version=0.1")
        c.run("create dep --name=dep2 --version=0.1")
        c.save({"conanws.yml": "",
                "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("dep1/0.1",
                                                                               "dep2/0.1"),
                "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1",
                                                                               "dep1/0.1")},
               clean_first=True)
        c.run("workspace add liba")
        c.run("workspace add libb")
        c.run("workspace install -g CMakeDeps -g CMakeToolchain -of=build --envs-generation=false")
        assert "Workspace conanfilews.py not found in the workspace folder, using default" in c.out
        files = os.listdir(os.path.join(c.current_folder, "build"))
        assert "conan_toolchain.cmake" in files
        assert "dep1-config.cmake" in files
        assert "dep2-config.cmake" in files
        assert "liba-config.cmake" not in files
        assert "libb-config.cmake" not in files
        assert "conanbuild.bat" not in files
        assert "conanbuild.sh" not in files

    def test_conanfilews_custom(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace

            class MyWs(ConanFile):
                settings = "arch", "build_type"
                generators = "MSBuildDeps"

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                "conanws.py": conanfilews})
        c.run("workspace add dep")
        c.run("workspace install -of=build")
        files = os.listdir(os.path.join(c.current_folder, "build"))
        assert "conandeps.props" in files

    def test_conanfilews_errors(self):
        c = TestClient()
        conanfilews = textwrap.dedent("""
            from conan import ConanFile
            from conan import Workspace
            class MyWs(ConanFile):
                requires = "dep/0.1"

            class Ws(Workspace):
                def root_conanfile(self):
                    return MyWs
            """)

        c.save({"conanws.yml": "conanfilews: myconanfilews.py",
                "dep/conanfile.py": GenConanfile("dep", "0.1"),
                "conanws.py": conanfilews})
        c.run("workspace install", assert_error=True)
        assert "ERROR: This workspace cannot be installed, it doesn't have any editable" in c.out
        c.run("workspace add dep")
        c.run("workspace install", assert_error=True)
        assert "ERROR: Conanfile in conanws.py shouldn't have 'requires'" in c.out

    def test_install_partial(self):
        # If we want to install only some part of the workspace
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile()})
        c.run("create dep --name=dep1 --version=0.1")
        c.run("create dep --name=dep2 --version=0.1")
        c.save({"conanws.yml": "",
                "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("dep1/0.1"),
                "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1"),
                "libc/conanfile.py": GenConanfile("libc", "0.1").with_requires("libb/0.1",
                                                                               "dep2/0.1")},
               clean_first=True)
        c.run("workspace add liba")
        c.run("workspace add libb")
        c.run("workspace add libc")
        for arg in ("libb", "libb liba"):
            c.run(f"workspace install {arg} -g CMakeDeps -of=build")
            assert "dep1/0.1" in c.out
            assert "dep2/0.1" not in c.out
            assert "libc/0.1" not in c.out
            files = os.listdir(os.path.join(c.current_folder, "build"))
            assert "dep1-config.cmake" in files
            assert "dep2-config.cmake" not in files


def test_workspace_with_local_recipes_index():
    c3i_folder = temp_folder()
    recipes_folder = os.path.join(c3i_folder, "recipes")
    zlib_config = textwrap.dedent("""
       versions:
         "1.2.11":
           folder: all
       """)
    save_files(recipes_folder, {"zlib/config.yml": zlib_config,
                                "zlib/all/conanfile.py": str(GenConanfile("zlib")),
                                "zlib/all/conandata.yml": ""})

    c = TestClient(light=True)
    c.save({"conanws.yml": 'home_folder: "deps"'})
    c.run(f'remote add local "{c3i_folder}"')

    c.run("list zlib/1.2.11#* -r=local")
    assert "zlib/1.2.11" in c.out  # It doesn't crash
    c.run("list zlib/1.2.11#*")
    assert "zlib/1.2.11" not in c.out
