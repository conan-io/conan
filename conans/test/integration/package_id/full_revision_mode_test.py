import textwrap
import unittest
from textwrap import dedent

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, GenConanfile, NO_SETTINGS_PACKAGE_ID
from conans.util.files import save


class FullRevisionModeTest(unittest.TestCase):

    def test_recipe_revision_mode(self):
        liba_ref = RecipeReference.loads("liba/0.1@user/testing")
        libb_ref = RecipeReference.loads("libb/0.1@user/testing")

        clienta = TestClient()
        save(clienta.cache.new_config_path, "core.package_id:default_mode=recipe_revision_mode")
        conanfilea = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfilea})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": GenConanfile().with_name("libb").with_version("0.1")
                                                    .with_require(liba_ref)})
        clientb.run("create . user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": GenConanfile().with_name("libc").with_version("0.1")
                                                    .with_require(libb_ref)})
        clientc.run("install . --user=user --channel=testing")

        # Do a minor change to the recipe, it will change the recipe revision
        clienta.save({"conanfile.py": conanfilea + "# comment"})
        clienta.run("create . liba/0.1@user/testing")

        clientc.run("install . --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        # Building b with the new recipe revision of liba works
        clientc.run("install . --user=user --channel=testing --build=libb")

        # Now change only the package revision of liba
        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . --user=user --channel=testing")
        save(clientc.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientc.run("install . --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        clientc.run("install . --user=user --channel=testing --build=libb")

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)

    def test_binary_id_recomputation_after_build(self):
        clienta = TestClient()
        save(clienta.cache.new_config_path, "core.package_id:default_mode=recipe_revision_mode")
        conanfile = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                %s
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfile % ""})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": conanfile % "requires = 'liba/0.1@user/testing'"})
        save(clientb.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientb.run("create . libb/0.1@user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": conanfile % "requires = 'libb/0.1@user/testing'"})
        save(clientc.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientc.run("create . libc/0.1@user/testing")

        clientd = TestClient(cache_folder=clienta.cache_folder)
        save(clientd.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientd.save({"conanfile.py": conanfile % "requires = 'libc/0.1@user/testing'"})
        clientd.run("install . --name=libd --version=0.1 --user=user --channel=testing")

        # Change A PREV
        clienta.run("create . liba/0.1@user/testing")
        clientd.run("install . --name=libd --version=0.1 --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientd.out)
        clientd.run("install . --name=libd --version=0.1 --user=user --channel=testing --build=missing")

        self.assertIn("libc/0.1@user/testing: Unknown binary", clientd.out)
        self.assertIn("libc/0.1@user/testing: Updated ID", clientd.out)
        self.assertIn("libc/0.1@user/testing: Binary for the updated ID has to be built",
                      clientd.out)
        self.assertIn("libc/0.1@user/testing: Calling build()", clientd.out)

    def test_binary_id_recomputation_with_build_requires(self):
        clienta = TestClient()
        clienta.save({"conanfile.py": GenConanfile().with_name("tool").with_version("0.1")
                                                    .with_package_info(cpp_info={"libs":
                                                                                 ["tool.lib"]},
                                                                       env_info={})})
        clienta.run("create . user/testing")
        save(clienta.cache.new_config_path, "core.package_id:default_mode=recipe_revision_mode")
        conanfile = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                build_requires = "tool/0.1@user/testing"
                %s
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfile % ""})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": conanfile % "requires = 'liba/0.1@user/testing'"})
        save(clientb.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientb.run("create . libb/0.1@user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": conanfile % "requires = 'libb/0.1@user/testing'"})
        save(clientc.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientc.run("create . libc/0.1@user/testing")

        clientd = TestClient(cache_folder=clienta.cache_folder)
        save(clientd.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        clientd.save({"conanfile.py": conanfile % "requires = 'libc/0.1@user/testing'"})
        clientd.run("install . --name=libd --version=0.1@ --user=user --channel=testing")

        # Change A PREV
        clienta.run("create . liba/0.1@user/testing")
        clientd.run("install . --name=libd --version=0.1@ --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientd.out)
        clientd.run("install . --name=libd --version=0.1@ --user=user --channel=testing --build=missing")

        self.assertIn("libc/0.1@user/testing: Unknown binary", clientd.out)
        self.assertIn("libc/0.1@user/testing: Updated ID", clientd.out)
        self.assertIn("libc/0.1@user/testing: Binary for the updated ID has to be built",
                      clientd.out)
        self.assertIn("libc/0.1@user/testing: Calling build()", clientd.out)

    def test_reusing_artifacts_after_build(self):
        # An unknown binary that after build results in the exact same PREF with PREV, doesn't
        # fire build of downstream
        client = TestClient()
        save(client.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require('liba/0.1@user/testing')})
        client.run("create . libb/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require('libb/0.1@user/testing')})
        client.run("create . libc/0.1@user/testing")

        client.save({"conanfile.py": GenConanfile().with_require('libc/0.1@user/testing')})
        # Telling to build LibA doesn't change the final result of LibA, which has same ID and PREV
        client.run("install . --name=libd --version=0.1 --user=user --channel=testing --build=liba")
        # So it is not necessary to build the downstream consumers of LibA
        for lib in ("libb", "libc"):
            self.assertIn("%s/0.1@user/testing: Unknown binary" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Updated ID" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Binary for updated ID from: Cache" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Already installed!" % lib, client.out)

    def test_download_artifacts_after_build(self):
        # An unknown binary that after build results in the exact same PREF with PREV, doesn't
        # fire build of downstream
        client = TestClient(default_server_user=True)
        save(client.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/0.1@user/testing")
        self.assertIn(f"liba/0.1@user/testing:{NO_SETTINGS_PACKAGE_ID} - Build",
                      client.out)
        prev = "a397cb03d51fb3b129c78d2968e2676f"
        self.assertIn(f"liba/0.1@user/testing: Created package revision {prev}", client.out)
        client.save({"conanfile.py": GenConanfile().with_require('liba/0.1@user/testing')})
        client.run("create . libb/0.1@user/testing")
        libb_pkgid = "af0c44b853e4651ccafc636d601d9c65d3fa44a8"
        self.assertIn(f"libb/0.1@user/testing:{libb_pkgid} - Build", client.out)

        client.save({"conanfile.py": GenConanfile().with_require('libb/0.1@user/testing')})
        client.run("create . libc/0.1@user/testing")
        client.run("upload * --all -c -r default")
        client.run("remove * -f")

        client.save({"conanfile.py": GenConanfile().with_require('libc/0.1@user/testing')})
        # Telling to build LibA doesn't change the final result of LibA, which has same ID and PREV
        client.run("install . --build=liba")
        rrev_a = "a397cb03d51fb3b129c78d2968e2676f"
        self.assertIn(f"liba/0.1@user/testing: Created package revision {rrev_a}", client.out)
        # So it is not necessary to build the downstream consumers of LibA
        for lib in ("libb", "libc"):
            self.assertIn("%s/0.1@user/testing: Unknown binary" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Updated ID" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Binary for updated ID from: Download" % lib,
                          client.out)
            self.assertIn("%s/0.1@user/testing: Downloaded package" % lib, client.out)


class PackageRevisionModeTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        save(self.client.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")

    def _generate_graph(self, dependencies):
        for ref, deps in dependencies.items():
            ref = RecipeReference.loads(ref)
            conanfile = GenConanfile().with_name(ref.name).with_version(ref.version)
            for dep in deps:
                conanfile.with_require(RecipeReference.loads(dep))
            filename = "%s.py" % ref.name
            self.client.save({filename: conanfile})
            self.client.run(f"export {filename} --name={ref.name} --version={ref.version}")

    def test_simple_dependency_graph(self):
        dependencies = {
            "log4qt/0.3.0": [],
            "mccapi/3.0.9": ["log4qt/0.3.0"],
            "util/0.3.5": ["mccapi/3.0.9"],
            "invent/1.0": ["util/0.3.5"]
        }
        self._generate_graph(dependencies)

        self.client.run("install invent.py --build missing")
        mcapi_pkg_id = "6b115bc2428b925e8ee4fdb91c700520592e3b29"
        self.assertIn(f"mccapi/3.0.9: Package '{mcapi_pkg_id}' created", self.client.out)
        util_pkg_id = "88d63d5c29a361250e6eba12aae6037b5a4d1e15"
        self.assertIn(f"util/0.3.5: Package '{util_pkg_id}' created", self.client.out)

    def test_triangle_dependency_graph(self):
        dependencies = {
            "log4qt/0.3.0": [],
            "mccapi/3.0.9": ["log4qt/0.3.0"],
            "util/0.3.5": ["mccapi/3.0.9"],
            "genericsu/1.0": ["log4qt/0.3.0", "mccapi/3.0.9", "util/0.3.5"]
                        }
        self._generate_graph(dependencies)

        self.client.run("install genericsu.py --build missing")
        mcapi_pkg_id = "6b115bc2428b925e8ee4fdb91c700520592e3b29"
        self.assertIn(f"mccapi/3.0.9: Package '{mcapi_pkg_id}' created", self.client.out)
        util_pkg_id = "88d63d5c29a361250e6eba12aae6037b5a4d1e15"
        self.assertIn(f"util/0.3.5: Package '{util_pkg_id}' created", self.client.out)

    def test_diamond_dependency_graph(self):
        dependencies = {
            "log4qt/0.3.0": [],
            "mccapi/3.0.9": ["log4qt/0.3.0"],
            "util/0.3.5": ["log4qt/0.3.0"],
            "genericsu/0.3.5": ["mccapi/3.0.9", "util/0.3.5"]
                        }
        self._generate_graph(dependencies)

        self.client.run("install genericsu.py --build missing")
        pkg_id = "6b115bc2428b925e8ee4fdb91c700520592e3b29"
        self.assertIn(f"mccapi/3.0.9: Package '{pkg_id}' created", self.client.out)
        self.assertIn(f"util/0.3.5: Package '{pkg_id}' created", self.client.out)

    @pytest.mark.xfail(reason="package id computation has changed")
    def test_full_dependency_graph(self):
        dependencies = {
            "log4qt/0.3.0": [],
            "mccapi/3.0.9": ["log4qt/0.3.0"],
            "util/0.3.5": ["mccapi/3.0.9"],
            "genericsu/0.3.5": ["log4qt/0.3.0", "mccapi/3.0.9", "util/0.3.5"],
            "ManagementModule/0.3.5": ["log4qt/0.3.0", "mccapi/3.0.9", "util/0.3.5"],
            "StationInterfaceModule/0.13.0": ["ManagementModule/0.3.5", "genericsu/0.3.5"],
            "PleniterGenericSuApp/0.1.8": ["ManagementModule/0.3.5", "genericsu/0.3.5",
                                           "log4qt/0.3.0", "mccapi/3.0.9", "util/0.3.5"],
            "StationinterfaceRpm/2.2.0": ["StationInterfaceModule/0.13.0",
                                          "PleniterGenericSuApp/0.1.8"]
                        }
        self._generate_graph(dependencies)

        # Obtained with with create and reevaluate_node
        ids = {"log4qt/0.3.0": "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
               "mccapi/3.0.9": "3c5ba9bba23b494f3ce0649fd32a8b997098f08e",
               "util/0.3.5": "3b8e8cc0ba9594e28d17856df15bc7287bb4b3eb",
               "genericsu/0.3.5": "e55df1a3e79765d0a29a0cc1630c3a56dfaeea8e",
               "ManagementModule/0.3.5": "e55df1a3e79765d0a29a0cc1630c3a56dfaeea8e",
               "StationInterfaceModule/0.13.0": "d24f5fea9cfbcb155f5be8fb061d6193ea0b62d9",
               "PleniterGenericSuApp/0.1.8": "d24f5fea9cfbcb155f5be8fb061d6193ea0b62d9"}

        rev = {"log4qt/0.3.0": "cf924fbb5ed463b8bb960cf3a4ad4f3a",
               "mccapi/3.0.9": "ee083a6a3593fa42571f9973254cf97c",
               "util/0.3.5": "5c2c94edcdc5d46cd9a0c0c798791e9a",
               "genericsu/0.3.5": "defb3fe7ee1e093b18512555ba04fe7c",
               "ManagementModule/0.3.5": "defb3fe7ee1e093b18512555ba04fe7c",
               "StationInterfaceModule/0.13.0": "d96c69d1c47d66e6c7ed2ede43af3477",
               "PleniterGenericSuApp/0.1.8": "d96c69d1c47d66e6c7ed2ede43af3477"}

        self.client.run("install StationinterfaceRpm.py --build missing")
        for pkg, id_ in ids.items():
            self.assertIn("%s: Package '%s' created" % (pkg, id_), self.client.out)
        for pkg, r in rev.items():
            self.assertIn("%s: Created package revision %s" % (pkg, r), self.client.out)

        self.client.run("install StationinterfaceRpm.py")
        for pkg, id_ in ids.items():
            self.assertIn("%s:%s - Cache" % (pkg, id_), self.client.out)


def test_package_revision_mode_full_transitive_package_id():
    # https://github.com/conan-io/conan/issues/8310
    client = TestClient()
    save(client.cache.new_config_path, "core.package_id:default_mode=package_revision_mode")

    profile = textwrap.dedent("""
        [tool_requires]
        tool/0.1
        """)
    client.save({"tool/conanfile.py": GenConanfile(),
                 "pkga/conanfile.py": GenConanfile(),
                 "pkgb/conanfile.py": GenConanfile().with_requires("tool/0.1", "pkga/0.1"),
                 "profile": profile})
    client.run("export tool --name=tool --version=0.1")
    client.run("export pkga --name=pkga --version=0.1")
    client.run("create pkgb pkgb/0.1@ -pr=profile --build=missing")
    assert "pkgb/0.1:Package_ID_unknown - Unknown" in client.out
    assert "pkgb/0.1: Unknown binary for pkgb/0.1, computing updated ID" in client.out
    pkg_id = "fbdb93dfebd237827767fd6bc7b235c1af5012dd"
    assert f"pkgb/0.1: Package '{pkg_id}' created" in client.out
