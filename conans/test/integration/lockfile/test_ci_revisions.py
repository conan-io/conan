import json
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient

conanfile = textwrap.dedent("""
    from conan import ConanFile, load
    import os
    class Pkg(ConanFile):
        settings = "os"
        {requires}
        exports_sources = "myfile.txt"
        keep_imports = True
        def imports(self):
            self.copy("myfile.txt", folder=True)
        def package(self):
            self.copy("*myfile.txt")
        def package_info(self):
            self.output.info("SELF OS: %s!!" % self.settings.os)
            self.output.info("SELF FILE: %s"
                % load(os.path.join(self.package_folder, "myfile.txt")))
            for d in os.listdir(self.package_folder):
                p = os.path.join(self.package_folder, d, "myfile.txt")
                if os.path.isfile(p):
                    self.output.info("DEP FILE %s: %s" % (d, load(p)))
        """)


@pytest.fixture()
def client_setup():
    c = TestClient()
    c.save({"global.conf": "core.package_id:default_mode=recipe_revision_mode"},
           path=c.cache.cache_folder)
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
    c.run("lock create --reference=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" in app1_lock
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
    c.run("install --reference=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    c.assert_listed_binary({"pkgawin/0.1": ("cf2e4ff978548fafd099ad838f9ecb8858bf25cb", "Cache"),
                            "pkgb/0.1": ("3e8c50da4b8eaceb85316d725f9034e6b41da06f", "Cache"),
                            "pkgc/0.1": ("f227aad67640133f2fafc9a6153e573b414c23a4", "Build"),
                            "app1/0.1": ("dd27c0479fc3a34163b0418920c26d2f515c79da", "Build")})
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    c.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" not in app1_clean
    assert "pkgb/0.1#504bc7152c72b49c99a6f16733fb2ff6" in app1_clean


def test_single_config_centralized_out_range(client_setup):
    """ same scenario as "test_single_config_centralized()"
    but pkgc pin the exact revision of pkgb/0.1#rev1
    But pkgb/0.1 change produces pkgb/0.1#rev2, which doesn't match the pinned revisions rev1
    Nothing to build in the app1, and the final lockfile doesn't change at all
    """
    # Out of range in revisions means a pinned revision, new revision will not match
    c = client_setup
    c.save({"pkgc/conanfile.py":
            conanfile.format(requires='requires="pkgb/0.1#22b62df19ae387d159447df568be38be"')})
    c.run("create pkgc --name=pkgc --version=0.1 -s os=Windows")
    c.run("create app1 --name=app1 --version=0.1 -s os=Windows --build=missing")
    c.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" in app1_lock

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
    assert "pkgb/0.1#504bc7152c72b49c99a6f16733fb2ff6" in app1_b_changed
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" in app1_b_changed

    # Now lets build the application, to see everything ok
    c.run("install --reference=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    # Nothing changed, the change is outside the range, app1 not affected!!
    c.assert_listed_binary({"pkgawin/0.1": ("cf2e4ff978548fafd099ad838f9ecb8858bf25cb", "Cache"),
                            "pkgb/0.1": ("3e8c50da4b8eaceb85316d725f9034e6b41da06f", "Cache"),
                            "pkgc/0.1": ("aa90815e58086351afd7d5ab7fa5287af982acb6", "Cache"),
                            "app1/0.1": ("e627293089d8b36d9d9478461b7fd01c3ac286d8", "Cache")})
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: HelloB" in c.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    c.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --clean")
    app1_clean = c.load("app1_clean.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" in app1_clean
    assert "pkgb/0.1#504bc7152c72b49c99a6f16733fb2ff6" not in app1_clean


def test_single_config_centralized_change_dep(client_setup):
    """ same scenario as "test_single_config_centralized()".
    But pkgb/0.1 change producing pkgb/0.1#rev2, and changes dependency from pkgA=>pkgJ
    """
    c = client_setup
    c.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")

    # Do an unrelated change in A, should not be used, this is not the change we are testing
    c.save({"pkga/myfile.txt": "ByeA World!!"})
    c.run("create pkga --name=pkgawin --version=0.1 -s os=Windows")

    # Build new package alternative J
    c.run("create pkgj --name=pkgj --version=0.1 -s os=Windows")

    # Do a change in B, this is the change that we want to test, remove pkgA, replace with pkgJ
    c.save({"pkgb/conanfile.py": conanfile.format(requires='requires="pkgj/0.1"'),
            "pkgb/myfile.txt": "ByeB World!!"})

    # Test that pkgb/0.1 new revision works
    c.run("create pkgb --name=pkgb --version=0.1 -s os=Windows "
          "--lockfile=app1.lock --lockfile-out=app1_b_changed.lock")
    assert "pkgb/0.1: DEP FILE pkgj: HelloJ" in c.out
    # Build new package alternative J, it won't be included, already locked in this create
    c.run("create pkgj --name=pkgj --version=0.1 -s os=Windows")

    # Now lets build the application, to see everything ok
    c.run("install --reference=app1/0.1@  --lockfile=app1_b_changed.lock "
          "--lockfile-out=app1_b_integrated.lock "
          "--build=missing  -s os=Windows")
    assert "pkga" not in c.out
    c.assert_listed_binary({"pkgj/0.1": ("cf2e4ff978548fafd099ad838f9ecb8858bf25cb", "Cache"),
                            "pkgb/0.1": ("fb6238c20d81f88c307d341c56bf3a27145c0262", "Cache"),
                            "pkgc/0.1": ("ee8c0aeee144aad328c8adb700a717f1681876fb", "Build"),
                            "app1/0.1": ("f5f2e51efdc8b21c078b8f418b510b0ee8efddf5", "Build")})
    assert "app1/0.1: DEP FILE pkgj: HelloJ" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/1.0 version in the lockfile
    c.run("lock create --reference=app1/0.1@ --lockfile=app1_b_integrated.lock "
          "--lockfile-out=app1_clean.lock -s os=Windows --clean")
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
    c.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    c.run("lock create --reference=app1/0.1@ --lockfile=app1.lock --lockfile-out=app1.lock "
          "-s os=Linux")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" in app1_lock
    assert "pkgawin/0.1#db3fc7dcc844836cbb7e2b9671a14160" in app1_lock
    assert "pkganix/0.1#db3fc7dcc844836cbb7e2b9671a14160" in app1_lock

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
    c.run("install --reference=app1/0.1@  --lockfile=app1_win.lock --lockfile-out=app1_win.lock "
          "--build=missing  -s os=Windows")
    c.assert_listed_binary({"pkgawin/0.1": ("cf2e4ff978548fafd099ad838f9ecb8858bf25cb", "Cache"),
                            "pkgb/0.1": ("3e8c50da4b8eaceb85316d725f9034e6b41da06f", "Cache"),
                            "pkgc/0.1": ("f227aad67640133f2fafc9a6153e573b414c23a4", "Build"),
                            "app1/0.1": ("dd27c0479fc3a34163b0418920c26d2f515c79da", "Build")})
    assert "app1/0.1: DEP FILE pkgawin: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # Now lets build the application in Linux, to see everything ok
    c.run("install --reference=app1/0.1@  --lockfile=app1_nix.lock --lockfile-out=app1_nix.lock "
          "--build=missing  -s os=Linux")
    c.assert_listed_binary({"pkganix/0.1": ("02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8", "Cache"),
                            "pkgb/0.1": ("48cae6faa6110bd97886038c08784f97d640ccfc", "Cache"),
                            "pkgc/0.1": ("3f98ad394d851082d3639b413d5c34823740e06e", "Build"),
                            "app1/0.1": ("e00918341aa6017467809a9e76bce87bfa65c743", "Build")})
    assert "app1/0.1: DEP FILE pkganix: HelloA" in c.out
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out

    # All good! We can get rid of the now unused pkgb/0.1 version in the lockfile
    c.run("lock create --reference=app1/0.1@ --lockfile=app1_win.lock "
          "--lockfile-out=app1_win.lock -s os=Windows --clean")
    app1_clean = c.load("app1_win.lock")
    c.run("lock create --reference=app1/0.1@ --lockfile=app1_nix.lock "
          "--lockfile-out=app1_nix.lock -s os=Linux --clean")
    app1_clean = c.load("app1_nix.lock")

    # Finally, merge the 2 clean lockfiles, for keeping just 1 for next iteration
    c.run("lock merge --lockfile=app1_win.lock --lockfile=app1_nix.lock "
          "--lockfile-out=app1_final.lock")
    app1_clean = c.load("app1_final.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" not in app1_clean
    assert "pkgawin/0.1#db3fc7dcc844836cbb7e2b9671a14160" in app1_clean
    assert "pkganix/0.1#db3fc7dcc844836cbb7e2b9671a14160" in app1_clean


def test_single_config_decentralized(client_setup):
    """ same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    """
    c = client_setup
    # capture the initial lockfile of our product
    c.run("lock create --reference=app1/0.1@  --lockfile-out=app1.lock -s os=Windows")
    app1_lock = c.load("app1.lock")
    assert "pkgb/0.1#22b62df19ae387d159447df568be38be" in app1_lock

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
    c.run("graph build-order --reference=app1/0.1@ --lockfile=app1_b_changed.lock "
          "--build=missing --format=json -s os=Windows", redirect_stdout="build_order.json")
    json_file = c.load("build_order.json")
    to_build = json.loads(json_file)
    level0 = to_build[0]
    assert len(level0) == 1
    pkgawin = level0[0]
    assert pkgawin["ref"] == "pkgawin/0.1#db3fc7dcc844836cbb7e2b9671a14160"
    assert pkgawin["packages"][0]["binary"] == "Cache"
    level1 = to_build[1]
    assert len(level1) == 1
    pkgb = level1[0]
    assert pkgb["ref"] == "pkgb/0.1#504bc7152c72b49c99a6f16733fb2ff6"
    assert pkgb["packages"][0]["binary"] == "Cache"

    for level in to_build:
        for elem in level:
            ref = RecipeReference.loads(elem["ref"])
            for package in elem["packages"]:
                binary = package["binary"]
                package_id = package["package_id"]
                if binary != "Build":
                    continue
                # TODO: The options are completely missing
                c.run(
                    "install --reference=%s@ --build=%s@ --lockfile=app1_b_changed.lock  -s os=Windows"
                    % (ref, ref))
                c.assert_listed_binary(
                    {str(ref): (package_id, "Build"),
                     "pkgawin/0.1": ("cf2e4ff978548fafd099ad838f9ecb8858bf25cb", "Cache"),
                     "pkgb/0.1": ("3e8c50da4b8eaceb85316d725f9034e6b41da06f", "Cache")})

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
    c.run("lock create --reference=app1/0.1@ --lockfile-out=app1.lock -s os=Windows")
    c.run("lock create --reference=app1/0.1@ --lockfile=app1.lock --lockfile-out=app1.lock "
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
    c.run("graph build-order --reference=app1/0.1@ --lockfile=app1_win.lock "
          "--build=missing --format=json -s os=Windows", redirect_stdout="app1_win.json")
    c.run("graph build-order --reference=app1/0.1@ --lockfile=app1_nix.lock "
          "--build=missing --format=json -s os=Linux", redirect_stdout="app1_nix.json")
    c.run("graph build-order-merge --file=app1_win.json --file=app1_nix.json"
          " --format=json", redirect_stdout="build_order.json")

    json_file = c.load("build_order.json")
    to_build = json.loads(json_file)
    level0 = to_build[0]
    assert len(level0) == 2
    pkgawin = level0[0]
    assert pkgawin["ref"] == "pkgawin/0.1#db3fc7dcc844836cbb7e2b9671a14160"
    assert pkgawin["packages"][0]["binary"] == "Cache"
    pkgawin = level0[1]
    assert pkgawin["ref"] == "pkganix/0.1#db3fc7dcc844836cbb7e2b9671a14160"
    assert pkgawin["packages"][0]["binary"] == "Cache"
    level1 = to_build[1]
    assert len(level1) == 1
    pkgb = level1[0]
    assert pkgb["ref"] == "pkgb/0.1#504bc7152c72b49c99a6f16733fb2ff6"
    assert pkgb["packages"][0]["binary"] == "Cache"

    for level in to_build:
        for elem in level:
            ref = elem["ref"]
            ref_without_rev = ref.split("#")[0]
            if "@" not in ref:
                ref = ref.replace("#", "@#")
            for package in elem["packages"]:
                binary = package["binary"]
                package_id = package["package_id"]
                if binary != "Build":
                    continue
                # TODO: The options are completely missing
                filenames = package["filenames"]
                lockfile = filenames[0] + ".lock"
                the_os = "Windows" if "win" in lockfile else "Linux"
                c.run("install --reference=%s --build=%s --lockfile=%s -s os=%s"
                      % (ref, ref, lockfile, the_os))
                c.assert_listed_binary({str(ref_without_rev): (package_id, "Build")})

                if the_os == "Windows":
                    c.assert_listed_binary(
                        {"pkgawin/0.1": ("cf2e4ff978548fafd099ad838f9ecb8858bf25cb", "Cache"),
                         "pkgb/0.1": ("3e8c50da4b8eaceb85316d725f9034e6b41da06f", "Cache")})
                    assert "DEP FILE pkgawin: HelloA" in c.out
                    assert "DEP FILE pkgb: ByeB World!!" in c.out
                else:
                    c.assert_listed_binary(
                        {"pkganix/0.1": ("02145fcd0a1e750fb6e1d2f119ecdf21d2adaac8", "Cache"),
                         "pkgb/0.1": ("48cae6faa6110bd97886038c08784f97d640ccfc", "Cache")})
                    assert "DEP FILE pkganix: HelloA" in c.out
                    assert "DEP FILE pkgb: ByeB World!!" in c.out

    # Just to make sure that the for-loops have been executed
    assert "app1/0.1: DEP FILE pkgb: ByeB World!!" in c.out
