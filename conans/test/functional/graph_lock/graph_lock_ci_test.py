import json
import os
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE
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

    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
    def test_revisions(self):
        test_server = TestServer(users={"user": "mypass"})
        client = TestClient(servers={"default": test_server},
                            users={"default": [("user", "mypass")]})
        client.run("config set general.default_package_id_mode=recipe_revision_mode")
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

        client.run("graph lock PkgD/0.1@user/channel")
        initial_lock_file = client.load(LOCKFILE)

        # Do a change in B, this will be a new revision
        clientb = TestClient(cache_folder=client.cache_folder, servers={"default": test_server})
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"'),
                     "myfile.txt": "ByeB World!!"})
        clientb.run("create . PkgB/0.1@user/channel")

        # Go back to main orchestrator
        client.run("graph lock PkgD/0.1@user/channel --build=missing")
        client.run("graph build-order . --json=build_order.json")
        master_lockfile = client.load("conan.lock")

        build_order = client.load("build_order.json")
        to_build = json.loads(build_order)
        lock_fileaux = master_lockfile
        while to_build:
            for _, ref in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder,
                                        servers={"default": test_server})
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile" % (ref, ref))
                lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("graph update-lock . new_lock")

            client.run("graph build-order .")
            lock_fileaux = client.load(LOCKFILE)
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = client.load(LOCKFILE)
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        client.run("upload * --all --confirm")

        client.save({LOCKFILE: initial_lock_file})
        client.run("remove * -f")
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("remove * -f")
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

    @unittest.skipUnless(get_env("TESTING_REVISIONS_ENABLED", False), "Only revisions")
    def test_package_revision_mode(self):
        test_server = TestServer(users={"user": "mypass"})
        client = TestClient(servers={"default": test_server},
                            users={"default": [("user", "mypass")]})
        client.run("config set general.default_package_id_mode=package_revision_mode")
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
        client.run("graph lock PkgD/0.1@user/channel")
        initial_lock_file = client.load(LOCKFILE)

        # Do a change in B
        clientb = TestClient(cache_folder=client.cache_folder, servers={"default": test_server})
        clientb.run("config set general.default_package_id_mode=package_revision_mode")
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"'),
                     "myfile.txt": "ByeB World!!"})
        clientb.run("create . PkgB/0.1@user/channel")

        # Go back to main orchestrator
        client.run("graph lock PkgD/0.1@user/channel --build=missing")
        client.run("graph build-order . --json=build_order.json")
        master_lockfile = client.load("conan.lock")

        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = master_lockfile
        while to_build:
            for _, ref in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder,
                                        servers={"default": test_server})
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile" % (ref, ref))
                lock_fileaux = client_aux.load(LOCKFILE)
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("graph update-lock . new_lock")

            client.run("graph build-order .")
            lock_fileaux = client.load(LOCKFILE)
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = client.load(LOCKFILE)
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        client.run("upload * --all --confirm")

        client.save({LOCKFILE: initial_lock_file})
        client.run("remove * -f")
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("remove * -f")
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

    def test_version_ranges(self):
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_mode")
        client.save({"conanfile.py": conanfile.format(requires=""),
                     "myfile.txt": "HelloA"})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
                     "myfile.txt": "HelloB"})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgB/[*]@user/channel"'),
                     "myfile.txt": "HelloC"})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.format(requires='requires="PkgC/[*]@user/channel"'),
                     "myfile.txt": "HelloD"})
        client.run("create . PkgD/0.1@user/channel")
        self.assertIn("PkgD/0.1@user/channel: SELF FILE: HelloD", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgC: HelloC", client.out)
        client.run("graph lock PkgD/0.1@user/channel")
        initial_lockfile = client.load("conan.lock")

        # Do a change in B
        clientb = TestClient(cache_folder=client.cache_folder)
        clientb.run("config set general.default_package_id_mode=full_package_mode")
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
                     "myfile.txt": "ByeB World!!"})
        clientb.run("create . PkgB/0.2@user/channel")

        # Go back to main orchestrator
        client.run("graph lock PkgD/0.1@user/channel --build=missing")
        client.run("graph build-order . --json=build_order.json")
        master_lockfile = client.load("conan.lock")

        json_file = client.load("build_order.json")
        to_build = json.loads(json_file)
        lock_fileaux = master_lockfile
        while to_build:
            for _, ref in to_build[0]:
                client_aux = TestClient(cache_folder=client.cache_folder)
                client_aux.run("config set general.default_package_id_mode=full_package_mode")
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile" % (ref, ref))
                lock_fileaux = client_aux.load(LOCKFILE)
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("graph update-lock . new_lock")

            client.run("graph build-order .")
            lock_fileaux = client.load(LOCKFILE)
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = client.load(LOCKFILE)
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

        client.save({LOCKFILE: initial_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

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

        client.run("graph lock PkgD/0.1@user/channel")
        lock_file = client.load(LOCKFILE)
        initial_lock_file = lock_file

        # Do a change in A
        clientb = TestClient(cache_folder=client.cache_folder)
        clientb.run("config set general.default_package_id_mode=full_package_mode")
        clientb.save({"conanfile.py": conanfile.format(requires=''),
                     "myfile.txt": "ByeA World!!"})
        clientb.run("create . PkgA/0.2@user/channel")

        client.run("graph lock PkgD/0.1@user/channel --build=missing")
        client.run("graph build-order . --json=build_order.json")
        master_lockfile = client.load("conan.lock")

        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = master_lockfile
        while to_build:
            _, ref = to_build[0].pop(0)
            client_aux = TestClient(cache_folder=client.cache_folder)
            client_aux.run("config set general.default_package_id_mode=full_package_mode")
            client_aux.save({LOCKFILE: lock_fileaux})
            client_aux.run("install %s --build=%s --lockfile" % (ref, ref))
            lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
            client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
            client.run("graph update-lock . new_lock")
            client.run("graph build-order .")
            lock_fileaux = client.load(LOCKFILE)
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = client.load(LOCKFILE)
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgB/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)

        client.save({LOCKFILE: initial_lock_file})
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgB/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: HelloA", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgB/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgA: ByeA World!!", client.out)

    def test_options(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
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
        client.run("graph lock PkgD/0.1@user/channel -pr=myprofile")
        lock_file = client.load(LOCKFILE)

        client2 = TestClient(cache_folder=client.cache_folder)
        client2.save({"conanfile.py": conanfile.format(requires=""), LOCKFILE: lock_file})
        client2.run("create . PkgA/0.1@user/channel --lockfile")
        self.assertIn("PkgA/0.1@user/channel: BUILDING WITH OPTION: 5!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

        client2.save({"conanfile.py": conanfile.format(
            requires='requires="PkgA/0.1@user/channel"')})
        client2.run("create . PkgB/0.1@user/channel --lockfile")
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: BUILDING WITH OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

        client2.save({"conanfile.py": conanfile.format(
            requires='requires="PkgB/0.1@user/channel"')})
        client2.run("create . PkgC/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: PACKAGE_INFO OPTION: 3!!", client2.out)
        self.assertIn("PkgC/0.1@user/channel: BUILDING WITH OPTION: 3!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)

        client2.save({"conanfile.py": conanfiled})
        client2.run("create . PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgD/0.1@user/channel: PACKAGE_INFO OPTION: 2!!", client2.out)
        self.assertIn("PkgD/0.1@user/channel: BUILDING WITH OPTION: 2!!", client2.out)
        self.assertIn("PkgC/0.1@user/channel: PACKAGE_INFO OPTION: 3!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)
