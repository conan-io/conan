import os
import textwrap

from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir


def test_third_party_patch_flow():
    """ this test emulates the work of a developer contributing recipes to ConanCenter, and having
    to do multiple patches to the original library source code:
    - Everything is local, not messing with the cache
    - Using layout() to define location of things
    """
    conanfile = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.files import save, load, apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "*"

            def layout(self):
                self.folders.source = "src"
                self.folders.build = "build"

            def source(self):
                # emulate a download from web site
                save(self, "myfile.cpp", "mistake1\nsomething\nmistake2\nmistake3\nsome\n")
                apply_conandata_patches(self)

            def build(self):
                content = load(self,  os.path.join(self.source_folder, "myfile.cpp"))
                for i in (1, 2, 3):
                    if "mistake{}".format(i) in content:
                        raise Exception("MISTAKE{} BUILD!".format(i))
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "conandata.yml": ""})
    client.run("install .")
    client.run("source .")
    assert "apply_conandata_patches(): No patches defined in conandata" in client.out

    client.save({"conandata.yml": "patches: {}"})
    client.run("source .")
    client.run("build .", assert_error=True)
    assert "MISTAKE1 BUILD!" in client.out

    # user decides to create patches, first init the repo
    client.init_git_repo(folder="src")  # Using helper for user/email repo init
    client.save({"src/myfile.cpp": "correct1\nsomething\nmistake2\nmistake3\nsome\n"})
    # compute the patch
    mkdir(os.path.join(client.current_folder, "patches"))
    client.run_command("cd src && git diff > ../patches/patch1")
    client.run_command("cd src && git add . && git commit -m patch1")
    conandata = textwrap.dedent("""
        patches:
          "1.0":
            - patch_file: "patches/patch1"
        """)
    client.save({"conandata.yml": conandata})

    client.run("source .")
    client.run("build .", assert_error=True)
    assert "MISTAKE2 BUILD!" in client.out

    client.save({"src/myfile.cpp": "correct1\nsomething\ncorrect2\nmistake3\nsome\n"})
    # compute the patch
    mkdir(os.path.join(client.current_folder, "patches"))
    client.run_command("cd src && git diff > ../patches/patch2")
    client.run_command("cd src && git add . && git commit -m patch1")

    conandata = textwrap.dedent("""
        patches:
          "1.0":
            - patch_file: "patches/patch1"
            - patch_file: "patches/patch2"
        """)
    client.save({"conandata.yml": conandata})
    client.run("source .")
    client.run("build .", assert_error=True)
    assert "MISTAKE3 BUILD!" in client.out

    client.save({"src/myfile.cpp": "correct1\nsomething\ncorrect2\ncorrect3\nsome\n"})
    # compute the patch
    mkdir(os.path.join(client.current_folder, "patches"))
    client.run_command("cd src && git diff > ../patches/patch3")
    client.run_command("cd src && git add . && git commit -m patch1")

    conandata = textwrap.dedent("""
           patches:
             "1.0":
               - patch_file: "patches/patch1"
               - patch_file: "patches/patch2"
               - patch_file: "patches/patch3"
           """)
    client.save({"conandata.yml": conandata})
    client.run("source .")
    client.run("build .")
    assert "conanfile.py (mypkg/1.0): Calling build()" in client.out

    # of course create should work too
    client.run("create .")
    assert "mypkg/1.0: Created package" in client.out


def test_third_party_overwrite_build_file():
    """ this test emulates the work of a developer contributing recipes to ConanCenter, and
    replacing the original build script with your one one.

    The export_sources is actually copying CMakeLists.txt into the "src" folder, but the
    'download' will overwrite it, so it is necessary to copy it again
    """
    conanfile = textwrap.dedent(r"""
        import os, shutil
        from conan import ConanFile
        from conan.tools.files import save, load

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "CMakeLists.txt"

            def layout(self):
                self.folders.source = "src"
                self.folders.build = "build"

            def source(self):
                # emulate a download from web site
                save(self, "CMakeLists.txt", "MISTAKE: Very old CMakeLists to be replaced")
                # Now I fix it with one of the exported files
                shutil.copy("../CMakeLists.txt", ".")

            def build(self):
                if "MISTAKE" in load(self, os.path.join(self.source_folder, "CMakeLists.txt")):
                    raise Exception("MISTAKE BUILD!")
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "conandata.yml": "",
                 "CMakeLists.txt": "My better cmake"})
    client.run("install .")
    client.run("source .")
    client.run("build .")
    assert "conanfile.py (mypkg/1.0): Calling build()" in client.out

    # of course create should work too
    client.run("create .")
    assert "mypkg/1.0: Created package" in client.out


def test_third_party_git_overwrite_build_file():
    """ Same as the above, but using git clone
    The trick: "git clone <url> ." needs an empty directory. No reason why the ``src`` folder should
    be polluted automatically with exports, so just removing things works
    """
    git_repo = temp_folder().replace("\\", "/")
    create_local_git_repo({"CMakeLists.txt": "MISTAKE Cmake"}, folder=git_repo)

    conanfile = textwrap.dedent(r"""
        import os, shutil
        from conan import ConanFile
        from conan.tools.files import save, load

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "CMakeLists.txt"

            def layout(self):
                self.folders.source = "src"
                self.folders.build = "build"

            def source(self):
                self.output.info("CWD: {{}}!".format(os.getcwd()))
                self.output.info("FILES: {{}}!".format(sorted(os.listdir("."))))
                self.run('git clone "{}" .')
                # Now I fix it with one of the exported files
                shutil.copy("../CMakeLists.txt", ".")

            def build(self):
                if "MISTAKE" in load(self, os.path.join(self.source_folder, "CMakeLists.txt")):
                    raise Exception("MISTAKE BUILD!")
        """.format(git_repo))

    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "conandata.yml": "",
                 "CMakeLists.txt": "My better cmake"})
    client.run("install .")
    client.run("source .")
    assert "FILES: []!" in client.out
    client.run("build .")
    assert "conanfile.py (mypkg/1.0): Calling build()" in client.out

    # of course create should work too
    client.run("create .")
    assert "mypkg/1.0: Created package" in client.out
