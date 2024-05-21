import json
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
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
pkgb_01_id = "cee4c64978063c49773213b9c8f6b631c612a00b"
pkgb_012_id = "6b6343eeb8ffeb498b809bca9853fceb7dd0c078"
pkgc_01_id = "1bc0312cddbd3c076e666b84af9cc5ac3d263719"
pkgapp_01_id = "dda63a9bddbbe704d4858d67156d5dad0361dc19"


@pytest.fixture()
def client_setup():
    c = TestClient()
    c.save_home({"global.conf": "core.package_id:default_unknown_mode=recipe_revision_mode"})
    pkb_requirements = """
    def requirements(self):
        if self.settings.os == "Windows":
            self.requires("pkgawin/0.1")
        else:
            self.requires("pkganix/0.1")
    """
    files = {
        "pkga/conanfile.py": conanfile.format(requires=""),
        "pkga/myfile.txt": "HelloA",
        "pkgj/conanfile.py": conanfile.format(requires=""),
        "pkgj/myfile.txt": "HelloJ",
        "pkgb/conanfile.py": conanfile.format(requires=pkb_requirements),
        "pkgb/myfile.txt": "HelloB",
        "pkgc/conanfile.py": conanfile.format(requires='requires="pkgb/0.1"'),
        "pkgc/myfile.txt": "HelloC",
        "app1/conanfile.py": conanfile.format(requires='requires="pkgc/0.1"'),
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
    all versions are "0.1" exact (without pinning revision)
    lock app1.lock to lock graph including pkgawin/0.1#rev1 and pkganix/0.1#rev1
    changes in pkgawin/0.1#rev2 and pkganix/0.1#rev2 are excluded by lockfile
    a change in pkgb produces a new pkgb/0.1#rev2 that we want to test if works in app1 lockfile
    the app1 can be built in a single node, including all necessary dependencies
    the final lockfile will include pkgb/0.1#rev2, and not pkgb/0.1#rev1
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" in app1_lock
    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.1 new revision works
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.1: DEP FILE pkgawin: HelloA" in c.out

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    c.assert_listed_binary({"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.1": (pkgb_01_id, "Cache"),
                            "pkgc/0.1": (pkgc_01_id, "Build"),
                            "app1/0.1": (pkgapp_01_id, "Build")})
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" not in app1_clean
    assert "pkgb/0.1#bb12977c3353d7633b34d55a926fe58c" in app1_clean


def test_single_config_centralized_out_range(client_setup):
    """ same scenario as "test_single_config_centralized()"
    but pkgc pin the exact revision of pkgb/0.1#rev1
    But pkgb/0.1 change produces pkgb/0.1#rev2, which doesn't match the pinned revisions rev1
    Nothing to build in the app1, and the final lockfile doesn't change at all
    """
    # Out of range in revisions means a pinned revision, new revision will not match
    c = client_setup
    c.save({"pkgc/conanfile.py":
            conanfile.format(requires='requires="pkgb/0.1#d03e920d532beeeb198cd886095bcca1"')})
    c.run("create pkgc --name=pkgc --version=0.1 -s os=Windows")
    c.run("create app1 --name=app1 --version=0.1 -s os=Windows --build=missing")
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" in app1_lock

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/1.0 works (but it is not matching the pinned revision)
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.1: DEP FILE pkgawin: HelloA" in c.out
    app1_b_changed = c.load("app1_b_changed.lock")
    assert "pkgb/0.1#bb12977c3353d7633b34d55a926fe58c" in app1_b_changed
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" in app1_b_changed

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    # Nothing changed, the change is outside the range, app1 not affected!!
    c.assert_listed_binary({"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.1": (pkgb_01_id, "Cache"),
                            "pkgc/0.1": ("7dc09fd93c15a010373b013c3a44fc94fc9d3226", "Cache"),
                            "app1/0.1": ("96324a4bf6d4bba4f697919a435eca6d746c2d18", "Cache")})
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in c.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" in app1_clean
    assert "pkgb/0.1#504bc7152c72b49c99a6f16733fb2ff6" not in app1_clean


def test_single_config_centralized_change_dep(client_setup):
    """ same scenario as "test_single_config_centralized()".
    But pkgb/0.1 change producing pkgb/0.1#rev2, and changes dependency from pkgA=>pkgJ
    """
    c = client_setup
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")

    # Build new package alternative J
    c.run("create pkgj --name=pkgj --version=0.1 -s os=Windows")

    # Do a change in B, this is the change that we want to test, remove pkgA, replace with pkgJ
    c.save({"pkgb/conanfile.py": conanfile.format(requires='requires="pkgj/0.1"'),
            "pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.1 new revision works
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows --lockfile-partial "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.1: DEP FILE pkgj: HelloJ" in c.out
    # Build new package alternative J, it won't be included, already locked in this create
    c.run("create pkgj --name=pkgj --version=0.1 -s os=Windows")

    # Now lets build the application, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    assert "pkga" not in c.out
    c.assert_listed_binary({"pkgj/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.1": ("6142fb85ccd4e94afad85a8d01a87234eefa5600", "Cache"),
                            "pkgc/0.1": ("93cfcbc8109eedf4211558258ff5a844fdb62cca", "Build"),
                            "app1/0.1": ("eb241e40d370e1e1b0fd516aff6ffff72de1e37d", "Build")})
    assert "app1/0.1: DEP FILE pkgj: HelloJ" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --lockfile-clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgj/0.1" in app1_clean
    assert "pkgb/0.1" in app1_clean
    assert "pkga" not in app1_clean


def test_multi_config_centralized(client_setup):
    """ same scenario as above, but now we want to manage 2 configurations Windows & Linux
    When pkgB is changed, it is built for both, and produces app1_win.lock and app2_linux.lock
    With those, app1 can be built in a single node for both configurations. After building
    app1, the 2 lockfiles can be cleaned (removing the old pkgb/0.1#rev1, leaving pkgb/0.1#rev2
    in the lock)
    The 2 final lockfiles can be "merged" in a single one for next iteration
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    c.run("lock create --requires=app1/0.1@ --lockfile=app1.lock --lockfile-out=app1.lock "
          "-s os=Linux")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" in app1_lock
    assert "pkgawin/0.1#2f297d19d9ee4827caf97071de449a54" in app1_lock
    assert "pkganix/0.1#2f297d19d9ee4827caf97071de449a54" in app1_lock

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")
    c.run("create pkga --name=pkganix --version=0.1 -s os=Linux")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.1 works
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_win.lock")
    assert "pkgb/0.1: DEP FILE pkgawin: HelloA" in c.out
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Linux "
          "--lockfile=app1.lock --lockfile-out=app1_nix.lock")
    assert "pkgb/0.1: DEP FILE pkganix: HelloA" in c.out

    # Now lets build the application in Windows, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_win.lock --lockfile-out=app1_win.lock "
          "--build=missing  -s os=Windows")
    c.assert_listed_binary({"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                            "pkgb/0.1": (pkgb_01_id, "Cache"),
                            "pkgc/0.1": (pkgc_01_id, "Build"),
                            "app1/0.1": (pkgapp_01_id, "Build")})
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # Now lets build the application in Linux, to see everything ok
    c.run("install --requires=app1/0.1@  --lockfile=app1_nix.lock --lockfile-out=app1_nix.lock "
          "--build=missing  -s os=Linux")
    c.assert_listed_binary({"pkganix/0.1": (pkganix_01_id, "Cache"),
                            "pkgb/0.1": (pkgb_012_id, "Cache"),
                            "pkgc/0.1": ("62b3834a578b45bb303925e1e9cfe0dd9908486e", "Build"),
                            "app1/0.1": ("6a589308a14c21c9082620be4a63240017665e38", "Build")})

    assert "app1/0.1: DEP FILE pkganix: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_win.lock "
          "--lockfile-out=app1_win.lock -s os=Windows --lockfile-clean")
    c.run("lock create --requires=app1/0.1@ --lockfile=app1_nix.lock "
          "--lockfile-out=app1_nix.lock -s os=Linux --lockfile-clean")

    # Finally, merge the 2 clean lockfiles, for keeping just 1 for next iteration
    c.run("lock merge --lockfile=app1_win.lock --lockfile=app1_nix.lock "
          "--lockfile-out=app1_final.lock")
    app1_clean = c.load("app1_final.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" not in app1_clean
    assert "pkgawin/0.1#2f297d19d9ee4827caf97071de449a54" in app1_clean
    assert "pkganix/0.1#2f297d19d9ee4827caf97071de449a54" in app1_clean


def test_single_config_decentralized(client_setup):
    """ same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --requires=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#d03e920d532beeeb198cd886095bcca1" in app1_lock

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.1 works
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.1: DEP FILE pkgawin: HelloA" in c.out

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
    assert pkgb["ref"] == "pkgb/0.1#bb12977c3353d7633b34d55a926fe58c"
    assert pkgb["packages"][0][0]["binary"] == "Cache"

    for level in to_build:
        for elem in level:
            ref = RecipeReference.loads(elem["ref"])
            for package in elem["packages"][0]:  # Assumes no dependencies between packages
                binary = package["binary"]
                package_id = package["package_id"]
                if binary != "Build":
                    continue
                # TODO: The options are completely missing
                c.run(
                    "install --requires=%s@ --build=%s@ --lockfile=app1_b_changed.lock  -s os=Windows"
                    % (ref, ref))
                c.assert_listed_binary(
                    {str(ref): (package_id, "Build"),
                     "pkgawin/0.1": (pkgawin_01_id, "Cache"),
                     "pkgb/0.1": (pkgb_01_id, "Cache")})
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
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")
    c.run("create pkga --name=pkganix --version=0.1 -s os=Linux")

    # Do a change in B, this is the change that we want to test
    c.save({"pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.1 new revision works
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_win.lock")
    assert "pkgb/0.1: DEP FILE pkgawin: HelloA" in c.out
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Linux "
          "--lockfile=app1.lock --lockfile-out=app1_nix.lock")
    assert "pkgb/0.1: DEP FILE pkganix: HelloA" in c.out

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
    assert pkgb["ref"] == "pkgb/0.1#bb12977c3353d7633b34d55a926fe58c"
    assert pkgb["packages"][0][0]["binary"] == "Cache"

    for level in to_build:
        for elem in level:
            ref = elem["ref"]
            ref_without_rev = ref.split("#")[0]
            if "@" not in ref:
                ref = ref.replace("#", "@#")
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
                c.assert_listed_binary({str(ref_without_rev): (package_id, "Build")})

                if the_os == "Windows":
                    c.assert_listed_binary(
                        {"pkgawin/0.1": (pkgawin_01_id, "Cache"),
                         "pkgb/0.1": (pkgb_01_id, "Cache")})
                    assert "DEP FILE pkgawin: HelloA" in c.out
                    assert "DEP FILE pkgb: ByeB World!!" in c.out
                else:
                    c.assert_listed_binary(
                        {"pkganix/0.1": (pkganix_01_id, "Cache"),
                         "pkgb/0.1": (pkgb_012_id, "Cache")})
                    assert "DEP FILE pkganix: HelloA" in c.out
                    assert "DEP FILE pkgb: ByeB World!!" in c.out

    # Just to make sure that the for-loops have been executed
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out
