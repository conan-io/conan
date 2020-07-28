import json
import os
import textwrap
import unittest

from parameterized import parameterized

from conans.model.graph_lock import LOCKFILE
from conans.test.utils.genconanfile import GenConanfile
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
    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
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
        # This should fail, as PkgB/0.2 is not involved in the new resolution
        client.run("lock create --reference=PkgD/0.1@user/channel "
                   "--lockfile=buildb.lock --lockfile-out=conan.lock", assert_error=True)
        self.assertIn("ERROR: The provided lockfile was not used, there is no overlap",
                      client.out)

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
