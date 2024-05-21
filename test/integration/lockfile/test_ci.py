import json
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.files import load, copy
    import os
    class Pkg(ConanFile):
        settings = "os"
        {requires}
        exports_sources = "myfile.txt"

        def generate(self):
            # Simulate an "imports"
            for dep in self.dependencies.values():
                dest_folder = os.path.join(self.build_folder, dep.ref.name)
                copy(self, "myfile.txt", dep.package_folder, dest_folder)

        def package(self):
            # Copy the ones from the dependencies
            copied = copy(self, "*myfile.txt", self.build_folder, self.package_folder, keep_path=True)
            # Copy the exported one
            copied = copy(self, "myfile.txt", self.source_folder, self.package_folder)
            assert len(copied) == 1

        def package_info(self):
            self.output.info("SELF OS: %s!!" % self.settings.os)
            self.output.info("SELF FILE: %s"
                % load(self, os.path.join(self.package_folder, "myfile.txt")))
            for d in os.listdir(self.package_folder):
                p = os.path.join(self.package_folder, d, "myfile.txt")
                if os.path.isfile(p):
                    self.output.info("DEP FILE %s: %s" % (d, load(self, p)))
        """)


pkgawin_01_id = "ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715"
pkganix_01_id = "9a4eb3c8701508aa9458b1a73d0633783ecc2270"
pkgb_01_id = "65becc9bdccee92972f365ae4f742dd4b046d1e0"
pkgb_012_id = "c753def4818cdc538183046f6149134eb4be7a32"
pkgc_01_id = "2a23b96aea3b4787fcd1816182e8a403349b0815"
pkgapp_01_id = "f8e4cc2232dff5983eeb2e7403b9c2dc755be44f"


@pytest.fixture()
def client_setup():
    c = TestClient()
    pkb_requirements = """
    def requirements(self):
        if self.settings.os == "Windows":
            self.requires("pkgawin/[>0.0 <1.0]")
        else:
            self.requires("pkganix/[>0.0 <1.0]")
    """
    files = {
        "pkga/conanfile.py": conanfile.format(requires=""),
        "pkga/myfile.txt": "HelloA",
        "pkgj/conanfile.py": conanfile.format(requires=""),
        "pkgj/myfile.txt": "HelloJ",
        "pkgb/conanfile.py": conanfile.format(requires=pkb_requirements),
        "pkgb/myfile.txt": "HelloB",
        "pkgc/conanfile.py": conanfile.format(requires='requires="pkgb/[>0.0 <1.0]"'),
        "pkgc/myfile.txt": "HelloC",
        "app1/conanfile.py": conanfile.format(requires='requires="pkgc/[>0.0 <1.0]"'),
        "app1/myfile.txt": "App1",
    }
    c.save(files)

    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")
    c.run("create pkga --name=pkganix --version=0.1 -s os=Linux")
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows")
    c.run("create pkgc --name=pkgc --version=0.1 -s os=Windows")
    c.run("create app1 --name=app1 --version=0.1 -s os=Windows")
    assert "app1/0.1: SELF FILE: App1" in c.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in c.out
    assert "app1/0.1: DEP FILE pkgc: HelloC" in c.out
    return c


def test_single_config_centralized(client_setup):
    """ app1 -> pkgc/0.1 -> pkgb/0.1 -> pkgawin/0.1 or pkganix/0.1
    all version-ranges [>0 <1.0]
    lock app1.lock to lock graph including pkgawin/0.1 and pkganix/0.1
    changes in pkgawin/0.2 and pkganix/0.2 are excluded by lockfile
    a change in pkgb produces a new pkgb/0.2 that we want to test if works in app1 lockfile
    the app1 can be built in a single node, including all necessary dependencies
    the final lockfile will include pkgb/0.2, and not pkgb/0.1
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!",
            "pkgb/myfile.txt": "ByeB World!!",
            "pkgc/myfile.txt": "ByeC World!!"})
    c.run("export pkga --name=pkgawin --version=0.2")  # this will never be used
    c.run("export pkgc --name=pkgc --version=0.2")  # this will never be used

    # Test that pkgb/0.2 works
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in c.out

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    c.assert_listed_binary({"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.2": (pkgb_01_id, "Cache"),
                            "pkgc/0.1": (pkgc_01_id, "Build"),
                            "app1/0.1": (pkgapp_01_id, "Build")})
    assert "pkgb/0.2" in c.out
    assert "pkgb/0.1" not in c.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean


def test_single_config_centralized_out_range(client_setup):
    """ same scenario as "test_single_config_centralized()"
    But pkgb/0.1 change version is bumped to pkgb/1.0, which doesn't fit in the consumers
    version range, so it is not used.
    Nothing to build in the app1, and the final lockfile doesn't change at all
    """
    c = client_setup
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.2 -s os=Windows")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/1.0 works (but it is out of valid range!)
    c.run("create pkgb --name=pkgb --version=1.0 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/1.0: DEP FILE pkgawin: HelloA" in c.out

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    # Nothing changed, the change is outside the range, app1 not affected!!
    c.assert_listed_binary({"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.1": (pkgb_01_id, "Cache"),
                            "pkgc/0.1": ("3b0c170cc929d4a1916489ce2dbb881fdad07f2e", "Cache"),
                            "app1/0.1": ("3b0234ea72056ce9a0eb06584b4be6d73089e0e2", "Cache")})
    assert "pkgb/0.2" not in c.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in c.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgb/0.1" in app1_clean
    assert "pkgb/1.0" not in app1_clean


def test_single_config_centralized_change_dep(client_setup):
    """ same scenario as "test_single_config_centralized()".
    But pkgb/0.1 change version is bumped to pkgb/0.2, and changes dependency from pkgA=>pkgJ
    """
    c = client_setup
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.2 -s os=Windows")

    # Build new package alternative J
    c.run("create pkgj --name=pkgj --version=0.1 -s os=Windows")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/conanfile.py": conanfile.format(requires='requires="pkgj/[>0.0 <1.0]"'),
            "pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock --lockfile-partial")
    assert "pkgb/0.2: DEP FILE pkgj: HelloJ" in c.out
    # Build new package alternative J, it won't be included, already locked in this create
    c.run("create pkgj --name=pkgj --version=0.2 -s os=Windows")

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    assert "pkga" not in c.out
    c.assert_listed_binary({"pkgj/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.2": ("79caa65bc5877c4ada84a2b454775f47a5045d59", "Cache"),
                            "pkgc/0.1": ("67e4e9b17f41a4c71ff449eb29eb716b8f83767b", "Build"),
                            "app1/0.1": ("f7eb3b81ac34ddecd04301afad031ee078c5ab3c", "Build")})
    assert "app1/0.1: DEP FILE pkgj: HelloJ" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgj/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean


def test_multi_config_centralized(client_setup):
    """ same scenario as above, but now we want to manage 2 configurations Windows & Linux
    When pkgB is changed, it is built for both, and produces app1_win.lock and app2_linux.lock
    With those, app1 can be built in a single node for both configurations. After building
    app1, the 2 lockfiles can be cleaned (removing the old pkgb/0.1, leaving pkgb/0.2 in the lock)
    The 2 final lockfiles can be "merged" in a single one for next iteration
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    c.run("lock create --requires=app1/0.1@ --lockfile=app1.lock --lockfile-out=app1.lock "
          "-s os=Linux")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.2 -s os=Windows")
    c.run("create pkga --name=pkganix --version=0.2 -s os=Linux")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_win.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in c.out
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Linux "
          "--lockfile=app1.lock --lockfile-out=app1_nix.lock")
    assert "pkgb/0.2: DEP FILE pkganix: HelloA" in c.out

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_win.lock --lockfile-out=app1_win.lock "
          "--build=missing  -s os=Windows")
    c.assert_listed_binary({"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.2": (pkgb_01_id, "Cache"),
                            "pkgc/0.1": (pkgc_01_id, "Build"),
                            "app1/0.1": (pkgapp_01_id, "Build")})
    assert "pkgb/0.2" in c.out
    assert "pkgb/0.1" not in c.out
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_nix.lock --lockfile-out=app1_nix.lock "
          "--build=missing  -s os=Linux")
    c.assert_listed_binary({"pkganix/0.1": (pkganix_01_id, "Cache"),
                            "pkgb/0.2": (pkgb_012_id, "Cache"),
                            "pkgc/0.1": ("2a4113733176ffbce61bbcb4dd0e76ecc162439c", "Build"),
                            "app1/0.1": ("6c198f82674d988b90eed54b52a494a5bbf09c41", "Build")})
    assert "pkgb/0.2" in c.out
    assert "pkgb/0.1" not in c.out
    assert "app1/0.1: DEP FILE pkganix: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_win.lock "
          "--lockfile-out=app1_win.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_win.lock")
    assert "pkgawin/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean
    assert "pkgawin/0.2" not in app1_clean
    assert "pkganix/0.2" not in app1_clean
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_nix.lock "
          "--lockfile-out=app1_nix.lock -s os=Linux --lockfile-clean")
    app1_clean = c.load("app1_nix.lock")
    assert "pkganix/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean
    assert "pkgawin/0.2" not in app1_clean
    assert "pkganix/0.2" not in app1_clean

    # Finally, merge the 2 clean lockfiles, for keeping just 1 for next iteration
    c.run("lock merge --lockfile=app1_win.lock --lockfile=app1_nix.lock "
          "--lockfile-out=app1_final.lock")
    app1_clean = c.load("app1_final.lock")
    assert "pkgawin/0.1" in app1_clean
    assert "pkganix/0.1" in app1_clean
    assert "pkgb/0.2" in app1_clean
    assert "pkgb/0.1" not in app1_clean
    assert "pkgawin/0.2" not in app1_clean
    assert "pkganix/0.2" not in app1_clean


def test_single_config_decentralized(client_setup):
    """ same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.2 -s os=Windows")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in c.out

    # Now lets build the application, to see everything ok
    c.run("graph build-order --requires=app1/0.1@ --lockfile=app1_b_changed.lock "
          "--build=missing --format=json -s os=Windows", redirect_stdout="build_order.json")
    json_file = c.load("build_order.json")

    to_build = json.loads(json_file)
    level0 = to_build[0]
    assert len(level0) == 1
    pkgawin = level0[0]
    assert pkgawin["ref"] == "pkgawin/0.1#2f297d19d9ee4827caf97071de449a54"
    assert pkgawin["packages"][0][0]["binary"] == "Cache"
    level1 = to_build[1]
    assert len(level1) == 1
    pkgb = level1[0]
    assert pkgb["ref"] == "pkgb/0.2#476b31358d78b3f04c68c4770bd6a79c"
    assert pkgb["packages"][0][0]["binary"] == "Cache"

    for level in to_build:
        for elem in level:
            ref = RecipeReference.loads(elem["ref"])
            for package in elem["packages"][0]:  # assumes no dependencies between packages
                binary = package["binary"]
                package_id = package["package_id"]
                if binary != "Build":
                    continue
                build_args = package["build_args"]
                c.run(f"install {build_args} --lockfile=app1_b_changed.lock -s os=Windows")

                c.assert_listed_binary(
                    {str(ref): (package_id, "Build"),
                     "pkgawin/0.1": (pkgawin_01_id, "Cache"),
                     "pkgb/0.2": (pkgb_01_id, "Cache")})
                assert "pkgb/0.2" in c.out
                assert "pkgb/0.1" not in c.out
                assert "DEP FILE pkgawin: HelloA" in c.out
                assert "DEP FILE pkgb: ByeB World!!" in c.out

    # Just to make sure that the for-loops have been executed
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out


def test_multi_config_decentralized(client_setup):
    """ same scenario as "test_multi_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    c.run("lock create --requires=app1/0.1@ --lockfile=app1.lock --lockfile-out=app1.lock "
          "-s os=Linux")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.2 -s os=Windows")
    c.run("create pkga --name=pkganix --version=0.2 -s os=Linux")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.2 works
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_win.lock")
    assert "pkgb/0.2: DEP FILE pkgawin: HelloA" in c.out
    c.run("create pkgb --name=pkgb --version=0.2 -s os=Linux "
          "--lockfile=app1.lock --lockfile-out=app1_nix.lock")
    assert "pkgb/0.2: DEP FILE pkganix: HelloA" in c.out

    # Now lets build the application, to see everything ok, for all the configs
    c.run("graph build-order --requires=app1/0.1@ --lockfile=app1_win.lock "
          "--build=missing --format=json -s os=Windows", redirect_stdout="app1_win.json")
    c.run("graph build-order --requires=app1/0.1@ --lockfile=app1_nix.lock "
          "--build=missing --format=json -s os=Linux", redirect_stdout="app1_nix.json")
    c.run("graph build-order-merge --file=app1_win.json --file=app1_nix.json"
          " --format=json", redirect_stdout="build_order.json")

    json_file = c.load("build_order.json")
    to_build = json.loads(json_file)
    level0 = to_build[0]
    assert len(level0) == 2
    pkgawin = level0[0]
    assert pkgawin["ref"] == "pkgawin/0.1#2f297d19d9ee4827caf97071de449a54"
    assert pkgawin["packages"][0][0]["binary"] == "Cache"
    pkgawin = level0[1]
    assert pkgawin["ref"] == "pkganix/0.1#2f297d19d9ee4827caf97071de449a54"
    assert pkgawin["packages"][0][0]["binary"] == "Cache"
    level1 = to_build[1]
    assert len(level1) == 1
    pkgb = level1[0]
    assert pkgb["ref"] == "pkgb/0.2#476b31358d78b3f04c68c4770bd6a79c"
    assert pkgb["packages"][0][0]["binary"] == "Cache"

    for level in to_build:
        for elem in level:
            ref = elem["ref"]
            ref_without_rev = ref.split("#")[0]
            for package in elem["packages"][0]:  # Assumes no dependencies between packages
                binary = package["binary"]
                package_id = package["package_id"]
                if binary != "Build":
                    continue
                # TODO: The options are completely missing
                filenames = package["filenames"]
                lockfile = filenames[0] + ".lock"
                the_os = "Windows" if "win" in lockfile else "Linux"
                c.run("install --requires=%s --build=%s --lockfile=%s -s os=%s"
                      % (ref, ref, lockfile, the_os))
                c.assert_listed_binary({ref_without_rev: (package_id, "Build")})

                if the_os == "Windows":
                    c.assert_listed_binary(
                        {"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                         "pkgb/0.2": (pkgb_01_id, "Cache")})
                    assert "pkgb/0.2" in c.out
                    assert "pkgb/0.1" not in c.out
                    assert "DEP FILE pkgawin: HelloA" in c.out
                    assert "DEP FILE pkgb: ByeB World!!" in c.out
                else:
                    c.assert_listed_binary(
                        {"pkganix/0.1": (pkganix_01_id, "Cache"),
                         "pkgb/0.2": (pkgb_012_id, "Cache")})
                    assert "pkgb/0.2" in c.out
                    assert "pkgb/0.1" not in c.out
                    assert "DEP FILE pkganix: HelloA" in c.out
                    assert "DEP FILE pkgb: ByeB World!!" in c.out

    # Just to make sure that the for-loops have been executed
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out


def test_single_config_decentralized_overrides():
    r""" same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    Now with overrides

    pkga -> toola/1.0 -> toolb/1.0 -> toolc/1.0
                \------override-----> toolc/2.0
    pkgb -> toola/2.0 -> toolb/1.0 -> toolc/1.0
                \------override-----> toolc/3.0
    pkgc -> toola/3.0 -> toolb/1.0 -> toolc/1.0
    """
    c = TestClient()
    c.save({"toolc/conanfile.py": GenConanfile("toolc"),
            "toolb/conanfile.py": GenConanfile("toolb").with_requires("toolc/1.0"),
            "toola/conanfile.py": GenConanfile("toola", "1.0").with_requirement("toolb/1.0")
                                                              .with_requirement("toolc/2.0",
                                                                                override=True),
            "toola2/conanfile.py": GenConanfile("toola", "2.0").with_requirement("toolb/1.0")
                                                               .with_requirement("toolc/3.0",
                                                                                 override=True),
            "toola3/conanfile.py": GenConanfile("toola", "3.0").with_requirement("toolb/1.0"),
            "pkga/conanfile.py": GenConanfile("pkga", "1.0").with_tool_requires("toola/1.0"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "1.0").with_requires("pkga/1.0")
                                                            .with_tool_requires("toola/2.0"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "1.0").with_requires("pkgb/1.0")
                                                            .with_tool_requires("toola/3.0"),
            })
    c.run("export toolc --version=1.0")
    c.run("export toolc --version=2.0")
    c.run("export toolc --version=3.0")

    c.run("export toolb --version=1.0")

    c.run("export toola")
    c.run("export toola2")
    c.run("export toola3")

    c.run("export pkga")
    c.run("export pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["build_requires"])
    assert "toolc/3.0" in requires
    assert "toolc/2.0" in requires
    assert "toolc/1.0" in requires
    assert len(lock["overrides"]) == 1
    assert set(lock["overrides"]["toolc/1.0"]) == {"toolc/3.0", "toolc/2.0", None}

    c.run("graph build-order pkgc --lockfile=pkgc/conan.lock --format=json --build=missing")
    to_build = json.loads(c.stdout)
    for level in to_build:
        for elem in level:
            for package in elem["packages"][0]:  # assumes no dependencies between packages
                binary = package["binary"]
                if binary != "Build":
                    continue
                build_args = package["build_args"]
                c.run(f"install {build_args} --lockfile=pkgc/conan.lock")

    c.run("install pkgc --lockfile=pkgc/conan.lock")
    # All works, all binaries exist now
    assert "pkga/1.0: Already installed!" in c.out
    assert "pkgb/1.0: Already installed!" in c.out
