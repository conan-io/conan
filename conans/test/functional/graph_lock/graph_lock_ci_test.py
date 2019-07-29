import json
import os
import textwrap
import unittest

from conans.client.graph.graph import BINARY_BUILD
from conans.model.graph_lock import LOCKFILE
from conans.model.ref import PackageReference
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


class GraphLockCITest(unittest.TestCase):

    def test(self):
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
        test_server = TestServer(users={"user": "mypass"})
        client = TestClient(servers={"default": test_server},
                            users={"default": [("user", "mypass")]})
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

        client.run("config set general.revisions_enabled=True")
        client.run("upload * --all --confirm")

        # FIXME: We need to do this with info, to avoid installing the binaries when we want info
        client.run("graph lock PkgD/0.1@user/channel")
        lock_file = load(os.path.join(client.current_folder, LOCKFILE))
        initial_lock_file = lock_file
        self.assertIn("PkgB/0.1@user/channel#c51f99a8622d6c837cd9dcd2595e43e4:"
                      "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5#e7f906f2f693abccb3dc3419c4270413",
                      lock_file)
        self.assertIn("PkgA/0.1@user/channel#189390ce059842ce984e0502c52cf736:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#5ba7f606729949527141beef73c72bc8",
                      lock_file)
        self.assertIn("PkgC/0.1@user/channel#1c63e932e9392857cdada81f34bf4690:"
                      "8f97510bcea8206c1c046cc8d71cc395d4146547#7ae97bd9488da55592ab7d94a1885282",
                      lock_file)
        self.assertIn("PkgD/0.1@user/channel#d3d184611fb757faa65e4d4203198579:"
                      "7e4312d9a6d3726436d62a6b508f361d13e65354#55f822331b182e54b5144e578ba9135b",
                      lock_file)

        # Do a change in B
        clientb = TestClient(cache_folder=client.cache_folder, servers={"default": test_server})
        clientb.run("config set general.revisions_enabled=True")
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"'),
                     "myfile.txt": "ByeB World!!",
                      LOCKFILE: lock_file})
        clientb.run("create . PkgB/0.1@user/channel --lockfile")
        lock_fileb = load(os.path.join(clientb.current_folder, LOCKFILE))
        self.assertIn("PkgB/0.1@user/channel#569839e7b741ee474406de1db69d19c2:"
                      "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5#d1974c85c53dfaa549478a9ead361fe2",
                      lock_fileb)
        self.assertIn("PkgA/0.1@user/channel#189390ce059842ce984e0502c52cf736:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#5ba7f606729949527141beef73c72bc8",
                      lock_fileb)
        self.assertIn("PkgC/0.1@user/channel#1c63e932e9392857cdada81f34bf4690:"
                      "8f97510bcea8206c1c046cc8d71cc395d4146547#7ae97bd9488da55592ab7d94a1885282",
                      lock_fileb)
        self.assertIn("PkgD/0.1@user/channel#d3d184611fb757faa65e4d4203198579:"
                      "7e4312d9a6d3726436d62a6b508f361d13e65354#55f822331b182e54b5144e578ba9135b",
                      lock_fileb)
        self.assertIn('"modified": "%s"' % BINARY_BUILD, lock_fileb)
        # Go back to main orchestrator
        client.save({"new_lock/%s" % LOCKFILE: lock_fileb})
        client.run("graph update-lock . new_lock")
        client.run("graph build-order . --json=build_order.json --build=cascade")
        lock_file_order = load(os.path.join(clientb.current_folder, LOCKFILE))
        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = lock_file_order
        while to_build:
            for _, pkg_ref in to_build[0]:
                pkg_ref = PackageReference.loads(pkg_ref)
                client_aux = TestClient(cache_folder=client.cache_folder,
                                        servers={"default": test_server})
                client_aux.run("config set general.revisions_enabled=True")
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile"
                               % (pkg_ref.ref, pkg_ref.ref.name))
                lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("graph update-lock . new_lock")

            client.run("graph build-order . --build=cascade")
            lock_fileaux = load(os.path.join(client.current_folder, LOCKFILE))
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = load(os.path.join(client.current_folder, LOCKFILE))
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

    def test_package_revision_mode(self):
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
        test_server = TestServer(users={"user": "mypass"})
        client = TestClient(servers={"default": test_server},
                            users={"default": [("user", "mypass")]})
        client.run("config set general.default_package_id_mode=package_revision_mode")
        client.run("config set general.revisions_enabled=True")
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
        lock_file = load(os.path.join(client.current_folder, LOCKFILE))
        initial_lock_file = lock_file
        self.assertIn("PkgB/0.1@user/channel#c51f99a8622d6c837cd9dcd2595e43e4:"
                      "6e9742c2106791c1c777da8ccfb12a1408385d8d#f25c123185dcbd2fe326cecb0d73edaa",
                      lock_file)
        self.assertIn("PkgA/0.1@user/channel#189390ce059842ce984e0502c52cf736:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#5ba7f606729949527141beef73c72bc8",
                      lock_file)
        self.assertIn("PkgC/0.1@user/channel#1c63e932e9392857cdada81f34bf4690:"
                      "d27e81082fa545d364f19bd07bdf7975acd9e1ac#667a94f8b740b0f35519116997eabeff",
                      lock_file)
        self.assertIn("PkgD/0.1@user/channel#d3d184611fb757faa65e4d4203198579:"
                      "d80dd9662f447164906643ab88a1ed4e7b12925b#50246cbe82411551e5ebc5bcc75f1a9a",
                      lock_file)

        # Do a change in B
        clientb = TestClient(cache_folder=client.cache_folder, servers={"default": test_server})
        clientb.run("config set general.revisions_enabled=True")
        clientb.run("config set general.default_package_id_mode=package_revision_mode")
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/0.1@user/channel"'),
                     "myfile.txt": "ByeB World!!",
                      LOCKFILE: lock_file})
        clientb.run("create . PkgB/0.1@user/channel --lockfile")
        lock_fileb = load(os.path.join(clientb.current_folder, LOCKFILE))
        self.assertIn("PkgB/0.1@user/channel#569839e7b741ee474406de1db69d19c2:"
                      "6e9742c2106791c1c777da8ccfb12a1408385d8d#2711a0a3b580e72544af8f36d0a87424",
                      lock_fileb)
        self.assertIn("PkgA/0.1@user/channel#189390ce059842ce984e0502c52cf736:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#5ba7f606729949527141beef73c72bc8",
                      lock_fileb)
        self.assertIn("PkgC/0.1@user/channel#1c63e932e9392857cdada81f34bf4690:"
                      "d27e81082fa545d364f19bd07bdf7975acd9e1ac#667a94f8b740b0f35519116997eabeff",
                      lock_fileb)
        self.assertIn("PkgD/0.1@user/channel#d3d184611fb757faa65e4d4203198579:"
                      "d80dd9662f447164906643ab88a1ed4e7b12925b#50246cbe82411551e5ebc5bcc75f1a9a",
                      lock_fileb)
        self.assertIn('"modified": "%s"' % BINARY_BUILD, lock_fileb)
        # Go back to main orchestrator
        client.save({"new_lock/%s" % LOCKFILE: lock_fileb})
        client.run("graph update-lock . new_lock")
        client.run("graph build-order . --json=build_order.json --build=cascade")
        lock_file_order = load(os.path.join(clientb.current_folder, LOCKFILE))
        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = lock_file_order
        while to_build:
            for _, pkg_ref in to_build[0]:
                pkg_ref = PackageReference.loads(pkg_ref)
                client_aux = TestClient(cache_folder=client.cache_folder,
                                        servers={"default": test_server})
                client_aux.run("config set general.revisions_enabled=True")
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile"
                               % (pkg_ref.ref, pkg_ref.ref.name))
                lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("graph update-lock . new_lock")

            client.run("graph build-order . --build=cascade")
            lock_fileaux = load(os.path.join(client.current_folder, LOCKFILE))
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = load(os.path.join(client.current_folder, LOCKFILE))
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
        lock_file = load(os.path.join(client.current_folder, LOCKFILE))
        initial_lock_file = lock_file
        self.assertIn("PkgB/0.1@user/channel", lock_file)
        self.assertIn("PkgA/0.1@user/channel", lock_file)
        self.assertIn("PkgC/0.1@user/channel", lock_file)
        self.assertIn("PkgD/0.1@user/channel", lock_file)

        # Do a change in B
        clientb = TestClient(cache_folder=client.cache_folder)
        clientb.run("config set general.default_package_id_mode=full_package_mode")
        clientb.save({"conanfile.py": conanfile.format(requires='requires="PkgA/[*]@user/channel"'),
                     "myfile.txt": "ByeB World!!",
                      LOCKFILE: lock_file})
        clientb.run("create . PkgB/0.2@user/channel --lockfile")
        lock_fileb = load(os.path.join(clientb.current_folder, LOCKFILE))
        self.assertIn("PkgB/0.2@user/channel", lock_fileb)
        self.assertIn("PkgA/0.1@user/channel", lock_fileb)
        self.assertIn("PkgC/0.1@user/channel", lock_fileb)
        self.assertIn("PkgD/0.1@user/channel", lock_fileb)

        # Go back to main orchestrator
        client.save({"new_lock/%s" % LOCKFILE: lock_fileb})
        client.run("graph update-lock . new_lock")
        client.run("graph build-order . --json=build_order.json --build=missing")
        lock_fileb = load(os.path.join(client.current_folder, LOCKFILE))
        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = lock_fileb
        while to_build:
            for _, pkg_ref in to_build[0]:
                pkg_ref = PackageReference.loads(pkg_ref)
                client_aux = TestClient(cache_folder=client.cache_folder)
                client_aux.run("config set general.default_package_id_mode=full_package_mode")
                client_aux.save({LOCKFILE: lock_fileaux})
                client_aux.run("install %s --build=%s --lockfile"
                               % (pkg_ref.ref, pkg_ref.ref.name))
                lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
                client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
                client.run("graph update-lock . new_lock")

            client.run("graph build-order . --build=missing")
            lock_fileaux = load(os.path.join(client.current_folder, LOCKFILE))
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = load(os.path.join(client.current_folder, LOCKFILE))
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

        client.save({LOCKFILE: initial_lock_file})
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: HelloB", client.out)

        client.save({LOCKFILE: new_lockfile})
        client.run("install PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgC/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)
        self.assertIn("PkgD/0.1@user/channel: DEP FILE PkgB: ByeB World!!", client.out)

    def test_version_ranges_diamond(self):
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
        lock_file = load(os.path.join(client.current_folder, LOCKFILE))
        initial_lock_file = lock_file
        self.assertIn("PkgB/0.1@user/channel", lock_file)
        self.assertIn("PkgA/0.1@user/channel", lock_file)
        self.assertIn("PkgC/0.1@user/channel", lock_file)
        self.assertIn("PkgD/0.1@user/channel", lock_file)

        # Do a change in A
        clientb = TestClient(cache_folder=client.cache_folder)
        clientb.run("config set general.default_package_id_mode=full_package_mode")
        clientb.save({"conanfile.py": conanfile.format(requires=''),
                     "myfile.txt": "ByeA World!!",
                      LOCKFILE: lock_file})
        clientb.run("create . PkgA/0.2@user/channel --lockfile")
        lock_fileb = load(os.path.join(clientb.current_folder, LOCKFILE))
        self.assertIn("PkgB/0.1@user/channel", lock_fileb)
        self.assertIn("PkgA/0.2@user/channel", lock_fileb)
        self.assertIn("PkgC/0.1@user/channel", lock_fileb)
        self.assertIn("PkgD/0.1@user/channel", lock_fileb)

        # Go back to main orchestrator
        client.save({"new_lock/%s" % LOCKFILE: lock_fileb})
        client.run("graph update-lock . new_lock")
        client.run("graph build-order . --json=build_order.json --build=missing")
        lock_fileb = load(os.path.join(client.current_folder, LOCKFILE))
        json_file = os.path.join(client.current_folder, "build_order.json")
        to_build = json.loads(load(json_file))
        lock_fileaux = lock_fileb
        while to_build:
            _, pkg_ref = to_build[0].pop(0)
            pkg_ref = PackageReference.loads(pkg_ref)
            client_aux = TestClient(cache_folder=client.cache_folder)
            client_aux.run("config set general.default_package_id_mode=full_package_mode")
            client_aux.save({LOCKFILE: lock_fileaux})
            client_aux.run("install %s --build=%s --lockfile"
                           % (pkg_ref.ref, pkg_ref.ref.name))
            lock_fileaux = load(os.path.join(client_aux.current_folder, LOCKFILE))
            client.save({"new_lock/%s" % LOCKFILE: lock_fileaux})
            client.run("graph update-lock . new_lock")

            client.run("graph build-order . --build=missing")
            lock_fileaux = load(os.path.join(client.current_folder, LOCKFILE))
            output = str(client.out).splitlines()[-1]
            to_build = eval(output)

        new_lockfile = load(os.path.join(client.current_folder, LOCKFILE))
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
        conanfileD = conanfile.format(requires='requires="PkgC/0.1@user/channel"')
        conanfileD = conanfileD.replace('default_options = {"myoption": 1}',
                                        'default_options = {"myoption": 2, "PkgC:myoption": 3,'
                                        '"PkgB:myoption": 4, "PkgA:myoption": 5}')
        client.save({"conanfile.py": conanfileD})
        client.run("export . PkgD/0.1@user/channel")

        # FIXME: We need to do this with info, to avoid installing the binaries when we want info
        client.run("profile new myprofile")
        # To make sure we can provide a profile as input
        client.run("graph lock PkgD/0.1@user/channel -pr=myprofile")
        lock_file = load(os.path.join(client.current_folder, LOCKFILE))

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

        client2.save({"conanfile.py": conanfile.format(
            requires='requires="PkgC/0.1@user/channel"')})
        client2.run("create . PkgD/0.1@user/channel --lockfile")
        self.assertIn("PkgD/0.1@user/channel: PACKAGE_INFO OPTION: 2!!", client2.out)
        self.assertIn("PkgD/0.1@user/channel: BUILDING WITH OPTION: 2!!", client2.out)
        self.assertIn("PkgC/0.1@user/channel: PACKAGE_INFO OPTION: 3!!", client2.out)
        self.assertIn("PkgB/0.1@user/channel: PACKAGE_INFO OPTION: 4!!", client2.out)
        self.assertIn("PkgA/0.1@user/channel: PACKAGE_INFO OPTION: 5!!", client2.out)
