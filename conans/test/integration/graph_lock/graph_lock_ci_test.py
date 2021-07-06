import json
import os
import textwrap
import unittest

from parameterized import parameterized
import pytest

from conans.model.graph_lock import LOCKFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.env_reader import get_env
from conans.util.files import load


conanfile = textwrap.dedent("""
    from conans import ConanFile, load
    import os
    class Pkg(ConanFile):
        {requires}
        exports_sources = "myfile.txt"
        keep_imports = True
        def imports(self):
            self.copy("myfile.txt", folder=True)
        def package(self):
            self.copy("*myfile.txt")
        def package_info(self):
            self.output.info("SELF FILE: %s"
                % load(os.path.join(self.package_folder, "myfile.txt")))
            for d in os.listdir(self.package_folder):
                p = os.path.join(self.package_folder, d, "myfile.txt")
                if os.path.isfile(p):
                    self.output.info("DEP FILE %s: %s" % (d, load(p)))
        """)


class GraphLockCITest(unittest.TestCase):

    @parameterized.expand([("recipe_revision_mode",), ("package_revision_mode",)])
    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_revisions(self, package_id_mode):
        test_server = TestServer(users={"user": "mypass"})
        client = TestClient(servers={"default": test_server},
                            users={"default": [("user", "mypass")]})
        client.run("config set general.default_package_id_mode=%s" % package_id_mode)
        client.save({"conanfile.py": conanfile.format(requires=""),
                     "myfile.txt": "HelloA"})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgA/0.1@user/channel"'),
                     "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgB/0.1@user/channel"'),
                     "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(
            requires='requires = "PkgC/0.1@user/channel"'),
                     "myfile.txt": "HelloD"})
        client.run("create . PkgD/0.1@user/channel")
        self.assertIn("PkgD/0.1@user/channel: SELF FILE: HelloD", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgC: HelloC", client.out)

        client.run("upload * --all --confirm")

        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        initial_lock_file = client.load(LOCKFILE)

        # Do a change in B, this will be a new revision
        clientb = TestClient(cache_folder=client.cache_folder, servers={"default": test_server})
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"'),
                     "myfile.txt": "ByeB World!!"})
        clientb.run("create . PkgB/0.1@user/channel")

        # Go back to main orchestrator
        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        client.run("lock build-order conan.lock --json=build_order.json")
        master_lockfile = client.load("conan.lock")

        build_order = client.load("build_order.json")
        to_build = json.loads(build_order)
        lock_fileaux = master_lockfile
        while to_build:
            for ref, _, _, _ in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder,
                                        servers={"default": test_server})
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile=conan.lock"
                               " --lockfile-out=conan.lock" % (ref, ref))
                lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("lock update conan.lock new_lock/conan.lock")

            client.run("lock build-order conan.lock --json=bo.json")
            lock_fileaux = client.load(LOCKFILE)
            to_build = json.loads(client.load("bo.json"))

        new_lockfile = client.load(LOCKFILE)
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        client.run("upload * --all --confirm")

        client.save({LOCKFILE: initial_lock_file})
        client.run("remove * -f")
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("remove * -f")
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

    @parameterized.expand([(False,), (True,)])
    def test_version_ranges(self, partial_lock):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        files = {
            "pkga/conanfile.py": conanfile.format(requires=""),
            "pkga/myfile.txt": "HelloA",
            "pkgb/conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
            "pkgb/myfile.txt": "HelloB",
            "pkgc/conanfile.py": conanfile.format(requires='requires="PkgB/[*]@user/channel"'),
            "pkgc/myfile.txt": "HelloC",
            "pkgd/conanfile.py": conanfile.format(requires='requires="PkgC/[*]@user/channel"'),
            "pkgd/myfile.txt": "HelloD",
        }
        client.save(files)

        client.run("create pkga PkgA/0.1@user/channel")
        client.run("create pkgb PkgB/0.1@user/channel")
        client.run("create pkgc PkgC/0.1@user/channel")
        client.run("create pkgd PkgD/0.1@user/channel")
        self.assertIn("PkgD/0.1@user/channel: SELF FILE: HelloD", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgC: HelloC", client.out)

        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        initial_lockfile = client.load("conan.lock")

        # Do a change in B
        client.save({"pkgb/myfile.txt": "ByeB World!!"})
        if not partial_lock:
            client.run("export pkgb PkgB/0.2@user/channel")

            # Go back to main orchestrator
            client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=productd.lock")

            # Now it is locked, PkgA can change
            client.save({"pkga/myfile.txt": "ByeA World!!"})
            client.run("create pkga PkgA/0.2@user/channel")
        else:
            client.run("lock create pkgb/conanfile.py --name=PkgB --version=0.2 --user=user "
                       "--channel=channel --lockfile-out=buildb.lock")
            self.assertIn("PkgA/0.1", client.out)
            self.assertNotIn("PkgA/0.2", client.out)

            # Now it is locked, PkgA can change
            client.save({"pkga/myfile.txt": "ByeA World!!"})
            client.run("create pkga PkgA/0.2@user/channel")

            # Package can be created with previous lock, keep PkgA/0.1
            client.run("create pkgb PkgB/0.2@user/channel --lockfile=buildb.lock "
                       "--lockfile-out=buildb.lock")
            self.assertIn("PkgA/0.1", client.out)
            self.assertNotIn("PkgA/0.2", client.out)
            self.assertIn("PkgB/0.2@user/channel: DEP FILE PkgA: HelloA", client.out)
            self.assertNotIn("ByeA", client.out)
            buildblock = client.load("buildb.lock")

            # Go back to main orchestrator, buildb.lock can be used to lock PkgA/0.1 too
            client.save({"buildb.lock": buildblock})
            client.run("lock create --reference=PkgD/0.1@user/channel --lockfile=buildb.lock "
                       "--lockfile-out=productd.lock")
            self.assertIn("PkgA/0.1", client.out)
            self.assertNotIn("PkgA/0.2", client.out)

        client.run("lock build-order productd.lock --json=build_order.json")
        productd_lockfile = client.load("productd.lock")

        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        lock_fileaux = productd_lockfile
        while to_build:
            for ref, _, _, _ in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder)
                client_aux.save({"productd.lock": lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile=productd.lock "
                               "--lockfile-out=productd.lock" % (ref, ref))
                lock_fileaux = client_aux.load("productd.lock")
                client.save({"new_lock/productd.lock": lock_fileaux})
                client.run("lock update productd.lock new_lock/productd.lock")

            client.run("lock build-order productd.lock --json=bo.json")
            lock_fileaux = client.load("productd.lock")
            to_build = json.loads(client.load("bo.json"))

        # Make sure built packages are marked as modified
        productd_lockfile = client.load("productd.lock")
        productd_lockfile_json = json.loads(productd_lockfile)
        nodes = productd_lockfile_json["graph_lock"]["nodes"]
        pkgb = nodes["0"] if partial_lock else nodes["3"]
        pkgc = nodes["4"] if partial_lock else nodes["2"]
        pkgd = nodes["3"] if partial_lock else nodes["1"]
        self.assertIn("PkgB/0.2", pkgb["ref"])
        self.assertTrue(pkgb["modified"])
        self.assertIn("PkgC/0.1", pkgc["ref"])
        self.assertTrue(pkgc["modified"])
        self.assertIn("PkgD/0.1", pkgd["ref"])
        self.assertTrue(pkgd["modified"])

        new_lockfile = client.load("productd.lock")
        client.run("install PkgD/0.1@user/channel --lockfile=productd.lock")
        self.assertIn("HelloA", client.out)
        self.assertNotIn("ByeA", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

        client.save({LOCKFILE: initial_lockfile})
        self.assertIn("HelloA", client.out)
        self.assertNotIn("ByeA", client.out)
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)

        client.save({LOCKFILE: new_lockfile})
        self.assertIn("HelloA", client.out)
        self.assertNotIn("ByeA", client.out)
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

        # Not locked will retrieve newer versions
        client.run("install PkgD/0.1@user/channel", assert_error=True)
        self.assertIn("PkgA/0.2@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        self.assertIn("PkgB/0.2@user/channel:11b376c6e7a22ec390c215a8584ef9237a6da32f - Missing",
                      client.out)

    def test_version_ranges_diamond(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        client.save({"conanfile.py": conanfile.format(requires=""),
                     "myfile.txt": "HelloA"})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
                     "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
                     "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgB/[*]@user/channel",'
                                                      ' "PkgC/[*]@user/channel"'),
                     "myfile.txt": "HelloD"})
        client.run("create . PkgD/0.1@user/channel")
        self.assertIn("PkgD/0.1@user/channel: SELF FILE: HelloD", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgC: HelloC", client.out)

        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        lock_file = client.load(LOCKFILE)
        initial_lock_file = lock_file

        # Do a change in A
        clientb = TestClient(cache_folder=client.cache_folder)
        clientb.run("config set general.default_package_id_mode=full_package_mode")
        clientb.save({"conanfile.py": conanfile.format(requires=''),
                     "myfile.txt": "ByeA World!!"})
        clientb.run("create . PkgA/0.2@user/channel")

        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        client.run("lock build-order conan.lock --json=build_order.json")
        master_lockfile = client.load("conan.lock")

        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = master_lockfile
        while to_build:
            ref, _, _, _ = to_build[0].pop(0)
            client_aux = TestClient(cache_folder=client.cache_folder)
            client_aux.run("config set general.default_package_id_mode=full_package_mode")
            client_aux.save({LOCKFILE: lock_fileaux})
            client_aux.run("install %s --build=%s --lockfile=conan.lock "
                           "--lockfile-out=conan.lock" % (ref, ref))
            lock_fileaux = load(os.path.join(client_aux.current_folder, "conan.lock"))
            client.save({"new_lock/conan.lock": lock_fileaux})
            client.run("lock update conan.lock new_lock/conan.lock")
            client.run("lock build-order conan.lock")
            lock_fileaux = client.load("conan.lock")
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = client.load(LOCKFILE)
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgB/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)

        client.save({LOCKFILE: initial_lock_file})
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgB/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgB/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)

    def test_override(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")

        # The original (unresolved) graph shows the requirements how they are
        # specified in the package recipes.  The graph contains conflicts:
        # There are three different versions of PkgA and two different versions
        # of PkgB.
        #
        # The overridden (resolved) graph shows the requirements after
        # conflicts have been resolved by overriding required package versions
        # in package PkgE.  This graph contains only one version per package.
        #
        # Original (unresolved) graph:       :  Overridden (resolved) graph:
        # ============================       :  ============================
        #                                    :
        # PkgA/0.1   PkgA/0.2    PkgA/0.3    :                       PkgA/0.3
        #    |          |           |\____   :       __________________/|
        #    |          |           |     \  :      /                   |
        # PkgB/0.1      |        PkgB/0.3 |  :  PkgB/0.1                |
        #    |\____     | _________/      |  :     |\_______   ________/|
        #    |     \    |/                |  :     |        \ /         |
        #    |     | PkgC/0.2             |  :     |      PkgC/0.2      |
        #    |     |    |                 |  :     |         |          |
        #    |     |    |                 |  :     |         |          |
        # PkgD/0.1 |    |                 |  :  PkgD/0.1     |          |
        #    | ___/____/_________________/   :     | _______/__________/
        #    |/                              :     |/
        # PkgE/0.1                           :  PkgE/0.1

        # PkgA/0.1
        client.save({
            "conanfile.py": conanfile.format(requires=""),
            "myfile.txt": "This is PkgA/0.1!",
        })
        client.run("export . PkgA/0.1@user/channel")

        # PkgA/0.2
        client.save({
            "conanfile.py": conanfile.format(requires=""),
            "myfile.txt": "This is PkgA/0.2!",
        })
        client.run("export . PkgA/0.2@user/channel")

        # PkgA/0.3
        client.save({
            "conanfile.py": conanfile.format(requires=""),
            "myfile.txt": "This is PkgA/0.3!",
        })
        client.run("export . PkgA/0.3@user/channel")

        # PkgB/0.1
        client.save({
            "conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"'),
            "myfile.txt": "This is PkgB/0.1!",
        })
        client.run("export . PkgB/0.1@user/channel")

        # PkgB/0.3
        client.save({
            "conanfile.py": conanfile.format(requires='requires="PkgA/0.3@user/channel"'),
            "myfile.txt": "This is PkgB/0.3!",
        })
        client.run("export . PkgB/0.3@user/channel")

        # PkgC/0.2
        client.save({
            "conanfile.py": conanfile.format(requires=textwrap.dedent("""
                # This comment line is required to yield the correct indentation
                    def requirements(self):
                        self.requires("PkgA/0.2@user/channel", override=True)
                        self.requires("PkgB/0.3@user/channel", override=False)
                """)),
            "myfile.txt": "This is PkgC/0.2!",
        })
        client.run("export . PkgC/0.2@user/channel")

        # PkgD/0.1
        client.save({
            "conanfile.py": conanfile.format(requires='requires="PkgB/0.1@user/channel"'),
            "myfile.txt": "This is PkgD/0.1!",
        })
        client.run("export . PkgD/0.1@user/channel")

        # PkgE/0.1
        client.save({
            "conanfile.py": conanfile.format(requires=textwrap.dedent("""
                # This comment line is required to yield the correct indentation
                    def requirements(self):
                        self.requires("PkgA/0.3@user/channel", override=True)
                        self.requires("PkgB/0.1@user/channel", override=True)
                        self.requires("PkgC/0.2@user/channel", override=False)
                        self.requires("PkgD/0.1@user/channel", override=False)
                """)),
            "myfile.txt": "This is PkgE/0.1!",
        })
        client.run("export . PkgE/0.1@user/channel")

        client.run("lock create --reference=PkgE/0.1@user/channel --lockfile-out=master.lock")

        while True:
            client.run("lock build-order master.lock --json=build_order.json")
            json_file = os.path.join(client.current_folder, "build_order.json")
            to_build = json.loads(load(json_file))
            if not to_build:
                break
            ref, _, _, _ = to_build[0].pop(0)
            client.run("lock create --reference=%s --lockfile=master.lock "
                       "--lockfile-out=derived.lock" % ref)
            client.run("install %s --build=%s --lockfile=derived.lock "
                       "--lockfile-out=update.lock" % (ref, ref))
            client.run("lock update master.lock update.lock")

        client.run("install PkgE/0.1@user/channel --lockfile=master.lock")
        filtered_output = [
            line for line in str(client.out).splitlines()
            if any(pattern in line for pattern in ["SELF FILE", "DEP FILE"])
        ]
        expected_output = [
            "PkgA/0.3@user/channel: SELF FILE: This is PkgA/0.3!",
            "PkgB/0.1@user/channel: DEP FILE PkgA: This is PkgA/0.3!",
            "PkgB/0.1@user/channel: SELF FILE: This is PkgB/0.1!",
            "PkgC/0.2@user/channel: DEP FILE PkgA: This is PkgA/0.3!",
            "PkgC/0.2@user/channel: DEP FILE PkgB: This is PkgB/0.1!",
            "PkgC/0.2@user/channel: SELF FILE: This is PkgC/0.2!",
            "PkgD/0.1@user/channel: DEP FILE PkgA: This is PkgA/0.3!",
            "PkgD/0.1@user/channel: DEP FILE PkgB: This is PkgB/0.1!",
            "PkgD/0.1@user/channel: SELF FILE: This is PkgD/0.1!",
            "PkgE/0.1@user/channel: DEP FILE PkgA: This is PkgA/0.3!",
            "PkgE/0.1@user/channel: DEP FILE PkgB: This is PkgB/0.1!",
            "PkgE/0.1@user/channel: DEP FILE PkgC: This is PkgC/0.2!",
            "PkgE/0.1@user/channel: DEP FILE PkgD: This is PkgD/0.1!",
            "PkgE/0.1@user/channel: SELF FILE: This is PkgE/0.1!",
        ]
        self.assertListEqual(
            sorted(filtered_output),
            sorted(expected_output),
            msg = "Original client output:\n%s" % client.out,
        )

    def test_options(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                {requires}
                options = {{"myoption": [1, 2, 3, 4, 5]}}
                default_options = {{"myoption": 1}}
                def build(self):
                    self.output.info("BUILDING WITH OPTION: %s!!" % self.options.myoption)
                def package_info(self):
                    self.output.info("PACKAGE_INFO OPTION: %s!!" % self.options.myoption)
                """)
        client = TestClient()
        client.save({"conanfile.py": conanfile.format(requires="")})
        client.run("export . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"')})
        client.run("export . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgB/0.1@user/channel"')})
        client.run("export . PkgC/0.1@user/channel")
        conanfiled = conanfile.format(requires='requires="PkgC/0.1@user/channel"')
        conanfiled = conanfiled.replace('default_options = {"myoption": 1}',
                                        'default_options = {"myoption": 2, "PkgC:myoption": 3,'
                                        '"PkgB:myoption": 4, "PkgA:myoption": 5}')
        client.save({"conanfile.py": conanfiled})
        client.run("export . PkgD/0.1@user/channel")

        client.run("profile new myprofile")
        # To make sure we can provide a profile as input
        client.run("lock create --reference=PkgD/0.1@user/channel -pr=myprofile "
                   "--lockfile-out=conan.lock")
        lock_file = client.load(LOCKFILE)

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile.format(requires=""), LOCKFILE: lock_file})
        client2.run("create . PkgA/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgA/0.1@user/channel: BUILDING WITH OPTION: 5!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

        client2.save({"conanfile.py": conanfile.format(
            requires='requires="PkgA/0.1@user/channel"')})
        client2.run("create . PkgB/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: BUILDING WITH OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

        client2.save({"conanfile.py": conanfile.format(
            requires='requires="PkgB/0.1@user/channel"')})
        client2.run("create . PkgC/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgC/0.1@user/channel: PACKAGE_INFO OPTION: 3!!", client2.out)
        self.assertIn("PkgC/0.1@user/channel: BUILDING WITH OPTION: 3!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

        client2.save({"conanfile.py": conanfiled})
        client2.run("create . PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgD/0.1@user/channel: PACKAGE_INFO OPTION: 2!!", client2.out)
        self.assertIn("PkgD/0.1@user/channel: BUILDING WITH OPTION: 2!!", client2.out)
        self.assertIn("PkgC/0.1@user/channel: PACKAGE_INFO OPTION: 3!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

    @pytest.mark.skipif(not get_env("TESTING_REVISIONS_ENABLED", False), reason="Only revisions")
    def test_package_revisions_unkown_id_update(self):
        # https://github.com/conan-io/conan/issues/7588
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        files = {
            "pkga/conanfile.py": conanfile.format(requires=""),
            "pkga/myfile.txt": "HelloA",
            "pkgb/conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
            "pkgb/myfile.txt": "HelloB",
            "pkgc/conanfile.py": conanfile.format(requires='requires="PkgB/[*]@user/channel"'),
            "pkgc/myfile.txt": "HelloC",
            "pkgd/conanfile.py": conanfile.format(requires='requires="PkgC/[*]@user/channel"'),
            "pkgd/myfile.txt": "HelloD",
        }
        client.save(files)
        client.run("export pkga PkgA/0.1@user/channel")
        client.run("export pkgb PkgB/0.1@user/channel")
        client.run("export pkgc PkgC/0.1@user/channel")
        client.run("export pkgd PkgD/0.1@user/channel")

        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        lockfile = json.loads(client.load("conan.lock"))
        nodes = lockfile["graph_lock"]["nodes"]
        self.assertEqual(nodes["3"]["ref"], "PkgB/0.1@user/channel#fa97c46bf83849a5db4564327b3cfada")
        self.assertEqual(nodes["3"]["package_id"], "Package_ID_unknown")

        client.run("install PkgA/0.1@user/channel --build=PkgA/0.1@user/channel "
                   "--lockfile=conan.lock --lockfile-out=conan_out.lock")
        client.run("lock update conan.lock conan_out.lock")

        client.run("install PkgB/0.1@user/channel --build=PkgB/0.1@user/channel "
                   "--lockfile=conan.lock --lockfile-out=conan_out.lock")
        lockfile = json.loads(client.load("conan_out.lock"))
        nodes = lockfile["graph_lock"]["nodes"]
        self.assertEqual(nodes["3"]["ref"], "PkgB/0.1@user/channel#fa97c46bf83849a5db4564327b3cfada")
        self.assertEqual(nodes["3"]["package_id"], "6e9742c2106791c1c777da8ccfb12a1408385d8d")
        self.assertEqual(nodes["3"]["prev"], "f971905c142e0de728f32a7237553622")

        client.run("lock update conan.lock conan_out.lock")
        lockfile = json.loads(client.load("conan.lock"))
        nodes = lockfile["graph_lock"]["nodes"]
        self.assertEqual(nodes["3"]["ref"], "PkgB/0.1@user/channel#fa97c46bf83849a5db4564327b3cfada")
        self.assertEqual(nodes["3"]["package_id"], "6e9742c2106791c1c777da8ccfb12a1408385d8d")
        self.assertEqual(nodes["3"]["prev"], "f971905c142e0de728f32a7237553622")


class CIPythonRequiresTest(unittest.TestCase):
    python_req = textwrap.dedent("""
        from conans import ConanFile
        def msg(conanfile):
            conanfile.output.info("{}")
        class Pkg(ConanFile):
            pass
        """)

    consumer = textwrap.dedent("""
        from conans import ConanFile, load
        import os
        class Pkg(ConanFile):
            {requires}
            python_requires = "pyreq/[*]@user/channel"
            def package_info(self):
                self.python_requires["pyreq"].module.msg(self)
            """)

    def setUp(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        client.save({"conanfile.py": self.python_req.format("HelloPyWorld")})
        client.run("export . pyreq/0.1@user/channel")

        client.save({"conanfile.py": self.consumer.format(requires="")})
        client.run("create . PkgA/0.1@user/channel")
        client.save(
            {"conanfile.py": self.consumer.format(requires='requires="PkgA/0.1@user/channel"')})
        client.run("create . PkgB/0.1@user/channel")
        client.save(
            {"conanfile.py": self.consumer.format(requires='requires="PkgB/[~0]@user/channel"')})
        client.run("create . PkgC/0.1@user/channel")
        client.save(
            {"conanfile.py": self.consumer.format(requires='requires="PkgC/0.1@user/channel"')})
        client.run("create . PkgD/0.1@user/channel")
        for pkg in ("PkgA", "PkgB", "PkgC", "PkgD"):
            self.assertIn("{}/0.1@user/channel: HelloPyWorld".format(pkg), client.out)

        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        self.client = client

    def test_version_ranges(self):
        client = self.client
        initial_lockfile = client.load("conan.lock")
        # Do a change in python_require
        client.save({"conanfile.py": self.python_req.format("ByePyWorld")})
        client.run("export . pyreq/0.2@user/channel")

        # Go back to main orchestrator
        client.run("lock create --reference=PkgD/0.1@user/channel --lockfile-out=conan.lock")
        client.run("lock build-order conan.lock --json=build_order.json")
        master_lockfile = client.load("conan.lock")
        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        lock_fileaux = master_lockfile
        while to_build:
            for ref, _, _, _ in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder)
                client_aux.save({"conan.lock": lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile=conan.lock "
                               "--lockfile-out=conan.lock" % (ref, ref))
                lock_fileaux = client_aux.load("conan.lock")
                client.save({"new_lock/conan.lock": lock_fileaux})
                client.run("lock update conan.lock new_lock/conan.lock")

            client.run("lock build-order conan.lock --json=bo.json")
            lock_fileaux = client.load("conan.lock")
            to_build = json.loads(client.load("bo.json"))

        new_lockfile = client.load("conan.lock")
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        for pkg in ("PkgA", "PkgB", "PkgC", "PkgD"):
            self.assertIn("{}/0.1@user/channel: ByePyWorld".format(pkg), client.out)

        client.save({"conan.lock": initial_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        for pkg in ("PkgA", "PkgB", "PkgC", "PkgD"):
            self.assertIn("{}/0.1@user/channel: HelloPyWorld".format(pkg), client.out)

        client.save({"conan.lock": new_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        for pkg in ("PkgA", "PkgB", "PkgC", "PkgD"):
            self.assertIn("{}/0.1@user/channel: ByePyWorld".format(pkg), client.out)

    def test_version_ranges_partial_unused(self):
        client = self.client
        consumer = self.consumer
        # Do a change in B
        client.save({"conanfile.py": consumer.format(requires='requires="PkgA/0.1@user/channel"')})
        client.run("lock create conanfile.py --name=PkgB --version=1.0 --user=user "
                   "--channel=channel --lockfile-out=buildb.lock")

        # Do a change in python_require
        client.save({"conanfile.py": self.python_req.format("ByePyWorld")})
        client.run("export . pyreq/0.2@user/channel")

        # create the package with the previous version of python_require
        client.save({"conanfile.py": consumer.format(requires='requires="PkgA/0.1@user/channel"')})
        # It is a new version, it will not be used in the product build!
        client.run("create . PkgB/1.0@user/channel --lockfile=buildb.lock")
        self.assertIn("pyreq/0.1", client.out)
        self.assertNotIn("pyreq/0.2", client.out)

        # Go back to main orchestrator
        # This should fail, as PkgB/1.0 is not involved in the new resolution
        client.run("lock create --reference=PkgD/0.1@user/channel "
                   "--lockfile=buildb.lock --lockfile-out=error.lock")
        # User can perfectly go and check the resulting lockfile and check if PkgB/0.1 is there
        # We can probably help automate this with a "conan lock find" subcommand
        error_lock = client.load("error.lock")
        self.assertNotIn("PkgB/1.0@user/channel", error_lock)

        client.run("lock build-order conan.lock --json=build_order.json")
        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        self.assertEqual(to_build, [])

        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        for pkg in ("PkgA", "PkgB", "PkgC", "PkgD"):
            self.assertIn("{}/0.1@user/channel: HelloPyWorld".format(pkg), client.out)

        client.run("install PkgD/0.1@user/channel", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package", client.out)

        client.run("install PkgD/0.1@user/channel --build=missing")
        for pkg in ("PkgA", "PkgB", "PkgC", "PkgD"):
            self.assertIn("{}/0.1@user/channel: ByePyWorld".format(pkg), client.out)

    def test_version_ranges_partial(self):
        client = self.client
        consumer = self.consumer
        # Do a change in B
        client.save({"conanfile.py": consumer.format(requires='requires="PkgA/0.1@user/channel"')})
        client.run("lock create conanfile.py --name=PkgB --version=0.2 --user=user "
                   "--channel=channel --lockfile-out=buildb.lock")

        # Do a change in python_require
        client.save({"conanfile.py": self.python_req.format("ByePyWorld")})
        client.run("export . pyreq/0.2@user/channel")

        # create the package with the previous version of python_require
        client.save({"conanfile.py": consumer.format(requires='requires="PkgA/0.1@user/channel"')})
        # It is a new version, it will not be used in the product build!
        client.run("create . PkgB/0.2@user/channel --lockfile=buildb.lock")
        self.assertIn("pyreq/0.1", client.out)
        self.assertNotIn("pyreq/0.2", client.out)

        # Go back to main orchestrator
        client.run("lock create --reference=PkgD/0.1@user/channel "
                   "--lockfile=buildb.lock --lockfile-out=conan.lock")

        client.run("lock build-order conan.lock --json=build_order.json")
        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        if client.cache.config.revisions_enabled:
            build_order = [[['PkgC/0.1@user/channel#9e5471ca39a16a120b25ee5690539c71',
                             'bca7337f8d2fde6cdc9dd17cdc56bc0b0a0e352d', 'host', '4']],
                           [['PkgD/0.1@user/channel#068fd3ce2a88181dff0b44de344a93a4',
                             '63a3463d4dd4cc8d7bca7a9fe5140abe582f349a', 'host', '3']]]
        else:
            build_order = [[['PkgC/0.1@user/channel',
                             'bca7337f8d2fde6cdc9dd17cdc56bc0b0a0e352d', 'host', '4']],
                           [['PkgD/0.1@user/channel',
                             '63a3463d4dd4cc8d7bca7a9fe5140abe582f349a', 'host', '3']]]
        self.assertEqual(to_build, build_order)

        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock --build=missing")
        self.assertIn("PkgA/0.1@user/channel: HelloPyWorld", client.out)
        self.assertIn("PkgB/0.2@user/channel: HelloPyWorld", client.out)
        self.assertIn("PkgC/0.1@user/channel: ByePyWorld", client.out)
        self.assertIn("PkgD/0.1@user/channel: ByePyWorld", client.out)

        client.run("install PkgD/0.1@user/channel", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package", client.out)

        client.run("install PkgD/0.1@user/channel --build=missing")
        self.assertIn("PkgA/0.1@user/channel: ByePyWorld", client.out)
        self.assertIn("PkgB/0.2@user/channel: ByePyWorld", client.out)
        self.assertIn("PkgC/0.1@user/channel: ByePyWorld", client.out)
        self.assertIn("PkgD/0.1@user/channel: ByePyWorld", client.out)

        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        self.assertIn("PkgA/0.1@user/channel: HelloPyWorld", client.out)
        self.assertIn("PkgB/0.2@user/channel: HelloPyWorld", client.out)
        self.assertIn("PkgC/0.1@user/channel: ByePyWorld", client.out)
        self.assertIn("PkgD/0.1@user/channel: ByePyWorld", client.out)


class CIBuildRequiresTest(unittest.TestCase):
    def test_version_ranges(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        myprofile = textwrap.dedent("""
            [build_requires]
            br/[>=0.1]@user/channel
            """)
        files = {
            "myprofile": myprofile,
            "br/conanfile.py": GenConanfile(),
            "pkga/conanfile.py": conanfile.format(requires=""),
            "pkga/myfile.txt": "HelloA",
            "pkgb/conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
            "pkgb/myfile.txt": "HelloB",
            "pkgc/conanfile.py": conanfile.format(requires='requires="PkgB/[*]@user/channel"'),
            "pkgc/myfile.txt": "HelloC",
            "pkgd/conanfile.py": conanfile.format(requires='requires="PkgC/[*]@user/channel"'),
            "pkgd/myfile.txt": "HelloD",
        }
        client.save(files)
        client.run("create br br/0.1@user/channel")
        client.run("create pkga PkgA/0.1@user/channel -pr=myprofile")
        client.run("create pkgb PkgB/0.1@user/channel -pr=myprofile")
        client.run("create pkgc PkgC/0.1@user/channel -pr=myprofile")
        client.run("create pkgd PkgD/0.1@user/channel -pr=myprofile")

        self.assertIn("PkgD/0.1@user/channel: SELF FILE: HelloD", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgC: HelloC", client.out)

        # Go back to main orchestrator
        client.run("lock create --reference=PkgD/0.1@user/channel --build -pr=myprofile "
                   " --lockfile-out=conan.lock")

        # Do a change in br
        client.run("create br br/0.2@user/channel")

        client.run("lock build-order conan.lock --json=build_order.json")
        self.assertIn("br/0.1", client.out)
        self.assertNotIn("br/0.2", client.out)
        master_lockfile = client.load("conan.lock")

        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        if client.cache.config.revisions_enabled:
            build_order = [[['br/0.1@user/channel#f3367e0e7d170aa12abccb175fee5f97',
                             '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '5']],
                           [['PkgA/0.1@user/channel#189390ce059842ce984e0502c52cf736',
                             '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                           [['PkgB/0.1@user/channel#fa97c46bf83849a5db4564327b3cfada',
                             '096f747d204735584fa0115bcbd7482d424094bc', 'host', '3']],
                           [['PkgC/0.1@user/channel#c6f95948619d28d9d96b0ae86c46a482',
                             'f6d5dbb6f309dbf8519278bae8d07d3b739b3dec', 'host', '2']],
                           [['PkgD/0.1@user/channel#fce78c934bc0de73eeb05eb4060fc2b7',
                             'de4467a3fa6ef01b09b7464e85553fb4be2d2096', 'host', '1']]]
        else:
            build_order = [[['br/0.1@user/channel',
                             '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '5']],
                           [['PkgA/0.1@user/channel',
                             '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                           [['PkgB/0.1@user/channel',
                             '096f747d204735584fa0115bcbd7482d424094bc', 'host', '3']],
                           [['PkgC/0.1@user/channel',
                             'f6d5dbb6f309dbf8519278bae8d07d3b739b3dec', 'host', '2']],
                           [['PkgD/0.1@user/channel',
                             'de4467a3fa6ef01b09b7464e85553fb4be2d2096', 'host', '1']]]

        self.assertEqual(to_build, build_order)
        lock_fileaux = master_lockfile
        while to_build:
            for ref, _, _, _ in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder)
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile=conan.lock "
                               "--lockfile-out=conan.lock" % (ref, ref))
                self.assertIn("br/0.1", client_aux.out)
                self.assertNotIn("br/0.2", client_aux.out)
                lock_fileaux = client_aux.load(LOCKFILE)
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("lock update conan.lock new_lock/conan.lock")

            client.run("lock build-order conan.lock --json=build_order.json")
            lock_fileaux = client.load(LOCKFILE)
            to_build = json.loads(client.load("build_order.json"))

        client.run("install PkgD/0.1@user/channel --lockfile=conan.lock")
        # No build require at all
        self.assertNotIn("br/0.", client.out)

        client.run("install PkgD/0.1@user/channel --build -pr=myprofile")
        self.assertIn("br/0.2", client.out)
        self.assertNotIn("br/0.1", client.out)


class CIBuildRequiresTwoProfilesTest(unittest.TestCase):
    def test_version_ranges(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        myprofile_host = textwrap.dedent("""
            [settings]
            os=Linux
            [build_requires]
            br/[>=0.1]
            """)
        myprofile_build = textwrap.dedent("""
           [settings]
           os=Windows
           """)
        conanfile_os = textwrap.dedent("""
            from conans import ConanFile, load
            from conans.tools import save
            import os
            class Pkg(ConanFile):
                settings = "os"
                {requires}

                keep_imports = True
                def imports(self):
                    self.copy("myfile.txt", folder=True)
                def package(self):
                    save(os.path.join(self.package_folder, "myfile.txt"),
                         "%s %s" % (self.name, self.settings.os))
                    self.copy("*myfile.txt")
                def package_info(self):
                    self.output.info("MYOS=%s!!!" % self.settings.os)
                    self.output.info("SELF FILE: %s"
                        % load(os.path.join(self.package_folder, "myfile.txt")))
                    for d in os.listdir(self.package_folder):
                        p = os.path.join(self.package_folder, d, "myfile.txt")
                        if os.path.isfile(p):
                            self.output.info("DEP FILE %s: %s" % (d, load(p)))
                """)
        files = {
            "profile_host": myprofile_host,
            "profile_build": myprofile_build,
            "br/conanfile.py": conanfile_os.format(requires=""),
            "pkga/conanfile.py": conanfile_os.format(requires=""),
            "pkgb/conanfile.py": conanfile_os.format(requires='requires="PkgA/[*]"'),
            "pkgc/conanfile.py": conanfile_os.format(requires='requires="PkgB/[*]"'),
            "pkgd/conanfile.py": conanfile_os.format(requires='requires="PkgC/[*]"'),
        }
        client.save(files)
        # Note the creating of BR is in the BUILD profile
        client.run("create br br/0.1@ --build-require -pr:h=profile_host -pr:b=profile_build")
        assert "br/0.1: SELF FILE: br Linux" not in client.out
        client.run("create pkga PkgA/0.1@ -pr:h=profile_host -pr:b=profile_build")
        client.run("create pkgb PkgB/0.1@ -pr:h=profile_host -pr:b=profile_build")
        client.run("create pkgc PkgC/0.1@ -pr:h=profile_host -pr:b=profile_build")
        client.run("create pkgd PkgD/0.1@ -pr:h=profile_host -pr:b=profile_build")

        self.assertIn("PkgD/0.1: SELF FILE: PkgD Linux", client.out)
        self.assertIn("PkgD/0.1: DEP FILE PkgA: PkgA Linux", client.out)
        self.assertIn("PkgD/0.1: DEP FILE PkgB: PkgB Linux", client.out)
        self.assertIn("PkgD/0.1: DEP FILE PkgC: PkgC Linux", client.out)

        # Go back to main orchestrator
        client.run("lock create --reference=PkgD/0.1@ --build -pr:h=profile_host -pr:b=profile_build"
                   " --lockfile-out=conan.lock")

        # Do a change in br
        client.run("create br br/0.2@ ")

        client.run("lock build-order conan.lock --json=build_order.json")
        self.assertIn("br/0.1", client.out)
        self.assertNotIn("br/0.2", client.out)
        master_lockfile = client.load("conan.lock")

        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        if client.cache.config.revisions_enabled:
            build_order = [[['br/0.1@#583b8302673adce66f12f2bec01fe9c3',
                             '3475bd55b91ae904ac96fde0f106a136ab951a5e', 'build', '5']],
                           [['PkgA/0.1@#583b8302673adce66f12f2bec01fe9c3',
                             'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31', 'host', '4']],
                           [['PkgB/0.1@#4b1da86739946fe16a9545d1f6bc9022',
                             '4a87f1e30266a1c1c685c0904cfb137a3dba11c7', 'host', '3']],
                           [['PkgC/0.1@#3e1048668b2a795f6742d04971f11a7d',
                             '50ad117314ca51a58e427a26f264e27e79b94cd4', 'host', '2']],
                           [['PkgD/0.1@#e6cc0ca095ca32bba1a6dff0af6f4eb3',
                             'e66cc39a683367fdd17218bdbab7d6e95c0414e1', 'host', '1']]]
        else:
            build_order = [[['br/0.1@', '3475bd55b91ae904ac96fde0f106a136ab951a5e', 'build', '5']],
                           [['PkgA/0.1@', 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31', 'host', '4']],
                           [['PkgB/0.1@', '4a87f1e30266a1c1c685c0904cfb137a3dba11c7', 'host', '3']],
                           [['PkgC/0.1@', '50ad117314ca51a58e427a26f264e27e79b94cd4', 'host', '2']],
                           [['PkgD/0.1@', 'e66cc39a683367fdd17218bdbab7d6e95c0414e1', 'host', '1']]]

        self.assertEqual(to_build, build_order)
        lock_fileaux = master_lockfile
        while to_build:
            for ref, _, build, _ in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder)
                client_aux.save({LOCKFILE: lock_fileaux})
                is_build_require = "--build-require" if build == "build" else ""
                client_aux.run("install %s --build=%s --lockfile=conan.lock "
                               "--lockfile-out=conan.lock %s" % (ref, ref, is_build_require))
                assert "br/0.1: SELF FILE: br Windows" in client_aux.out
                self.assertIn("br/0.1", client_aux.out)
                self.assertNotIn("br/0.2", client_aux.out)
                lock_fileaux = client_aux.load(LOCKFILE)
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("lock update conan.lock new_lock/conan.lock")

            client.run("lock build-order conan.lock --json=build_order.json")
            lock_fileaux = client.load(LOCKFILE)
            to_build = json.loads(client.load("build_order.json"))

        client.run("install PkgD/0.1@ --lockfile=conan.lock")
        # No build require at all
        self.assertNotIn("br/0.", client.out)

        client.run("install PkgD/0.1@ --build  -pr:h=profile_host -pr:b=profile_build")
        self.assertIn("br/0.2", client.out)
        self.assertNotIn("br/0.1", client.out)


class CIPrivateRequiresTest(unittest.TestCase):
    def test(self):
        # https://github.com/conan-io/conan/issues/7985
        client = TestClient()
        files = {
            "private/conanfile.py": GenConanfile().with_option("myoption", [True, False]),
            "pkga/conanfile.py": textwrap.dedent("""
                from conans import ConanFile
                class PkgA(ConanFile):
                    requires = ("private/0.1", "private"),
                    def configure(self):
                        self.options["private"].myoption = True
                """),
            "pkgb/conanfile.py": textwrap.dedent("""
                from conans import ConanFile
                class PkgB(ConanFile):
                    requires = "pkga/0.1", ("private/0.1", "private"),
                    def configure(self):
                        self.options["private"].myoption = False
                """),
            "pkgc/conanfile.py": GenConanfile().with_require("pkgb/0.1")
        }
        client.save(files)
        client.run("export private private/0.1@")
        client.run("export pkga pkga/0.1@")
        client.run("export pkgb pkgb/0.1@")

        client.run("lock create pkgc/conanfile.py --name=pkgc --version=0.1 --build "
                   "--lockfile-out=conan.lock")
        client.run("lock build-order conan.lock --json=build_order.json")
        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        if client.cache.config.revisions_enabled:
            build_order = [[['private/0.1@#e31c7a656abb86256b08af0e64d37d42',
                             'd2560ba1787c188a1d7fabeb5f8e012ac53301bb', 'host', '3'],
                            ['private/0.1@#e31c7a656abb86256b08af0e64d37d42',
                             '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                           [['pkga/0.1@#edf085c091f9f4adfdb623bda9415a79',
                             '5b0fc4382d9c849ae3ef02a57b62b26ad5137990', 'host', '2']],
                           [['pkgb/0.1@#9b0edf8f61a88f92e05919b406d74089',
                             'd7d6ac48b43e368b0a5ff79015acea49b758ffdf', 'host', '1']]]
        else:
            build_order = [[['private/0.1@',
                             'd2560ba1787c188a1d7fabeb5f8e012ac53301bb', 'host', '3'],
                            ['private/0.1@',
                             '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9', 'host', '4']],
                           [['pkga/0.1@',
                             '5b0fc4382d9c849ae3ef02a57b62b26ad5137990', 'host', '2']],
                           [['pkgb/0.1@',
                             'd7d6ac48b43e368b0a5ff79015acea49b758ffdf', 'host', '1']]]

        self.assertEqual(to_build, build_order)

        for ref, pid, _, node_id in build_order[0]:
            client.run("install %s --build=%s --lockfile=conan.lock --lockfile-out=conan.lock "
                       "--lockfile-node-id=%s" % (ref, ref, node_id))
            self.assertIn('private/0.1:{} - Build'.format(pid), client.out)
