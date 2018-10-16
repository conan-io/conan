import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load
import json
from conans.model.ref import ConanFileReference


class CIGraphLockTest(unittest.TestCase):

    def graph_lock_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"custom_option": [1, 2, 3, 4, 5]}
    default_options = "custom_option=1"
    %s
"""
        client.save({"conanfile.py": conanfile % ""})
        client.run("export . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile % "requires = 'PkgA/0.1@user/channel'"})
        client.run("export . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile % "requires = 'PkgB/0.1@user/channel'"})
        client.run("export . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile % "requires = 'PkgC/0.1@user/channel'"})
        client.run("export . PkgD/0.1@user/channel")

        client.run("lock PkgD/0.1@user/channel -o PkgA:custom_option=2 "
                   "-o PkgB:custom_option=3 -o PkgC:custom_option=4 -o PkgD:custom_option=5")

        lock_file = os.path.join(client.current_folder, "serial_graph.json")
        print "PATH: ", lock_file
        content = load(lock_file)
        print "LCOK FILE!!!!!\n", str(content)
        build_order_file = os.path.join(client.current_folder, "build_order.json")
        print "PATH: ", build_order_file
        content = load(build_order_file)
        print "LCOK FILE!!!!!\n", str(content)
        build_order = json.loads(content)

        for level in build_order:
            for node in level:
                print "PROCESSING ", node
                client.run("lock serial_graph.json --lock-id=%s" % (node))
                print client.out
