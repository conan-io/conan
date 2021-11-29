import os
import textwrap

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
        from conans import ConanFile, load
        from conans.tools import save
        from conan.tools.files import apply_conandata_patches

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            exports_sources = "*"

            def layout(self):
                self.folders.source = "src"
                self.folders.build = "build"

            def source(self):
                # emulate a download from web site
                save("myfile.cpp", "mistake1\nsomething\nmistake2\nmistake3\nsome\n")
                apply_conandata_patches(self)

            def build(self):
                for i in (1, 2, 3):
                    if "mistake{}".format(i) in load(os.path.join(self.source_folder, "myfile.cpp")):
                        raise Exception("MISTAKE{} BUILD!".format(i))
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "conandata.yml": ""})
    client.run("install .")
    client.run("source .")
    client.run("build .", assert_error=True)
    assert "MISTAKE1 BUILD!" in client.out

    # user decides to create patches, first init the repo
    client.run_command("cd src && git init . && git add . && git commit -m initial")
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
