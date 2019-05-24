import os
import unittest

from conans.model.graph_lock import LOCKFILE
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.tools import TestClient
from conans.util.files import load


class GraphLockCITest(unittest.TestCase):

    def test(self):
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": str(TestConanFile("PkgB", "0.1",
                                                       requires=['PkgA/0.1@user/channel']))})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py": str(TestConanFile("PkgC", "0.1",
                                                       requires=['PkgB/0.1@user/channel']))})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": str(TestConanFile("PkgD", "0.1",
                                                       requires=['PkgC/0.1@user/channel']))})

        # FIXME: We need to do this with info, to avoid installing the binaries when we want info
        client.run("install .")
        lock_file = load(os.path.join(client.current_folder, LOCKFILE))
        self.assertIn("PkgB/0.1@user/channel#61112933024b5af11c457c15b798197d:"
                      "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5#be4fb19db04b8500097d3ed04c0cd08f",
                      lock_file)
        self.assertIn("PkgA/0.1@user/channel#b55538d56afb03f068a054f11310ce5a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#6d56ca1040e37a13b75bc286f3e1a5ad",
                      lock_file)
        self.assertIn("PkgC/0.1@user/channel#50343cbfb4ff3d4b983754db73270393:"
                      "8f97510bcea8206c1c046cc8d71cc395d4146547#95d70be108a41634e441365746b7af85",
                      lock_file)

        # Do a change in B
        clientb = TestClient(base_folder=client.base_folder)
        clientb.save({"conanfile.py": str(TestConanFile("PkgB", "0.1",
                                                        requires=['PkgA/0.1@user/channel'],
                                                        info=True)),
                      LOCKFILE: lock_file})
        clientb.run("create . PkgB/0.1@user/channel --install-folder=.")
        lock_fileb = load(os.path.join(clientb.current_folder, LOCKFILE))
        self.assertIn("PkgB/0.1@user/channel#360565ec9c69359f1ea65c270e97acb7:"
                      "5bf1ba84b5ec8663764a406f08a7f9ae5d3d5fb5#7b581251035fc05a4db847f9b7e80d40",
                      lock_fileb)
        self.assertIn("PkgA/0.1@user/channel#b55538d56afb03f068a054f11310ce5a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#6d56ca1040e37a13b75bc286f3e1a5ad",
                      lock_fileb)
        self.assertIn("PkgC/0.1@user/channel#50343cbfb4ff3d4b983754db73270393:"
                      "8f97510bcea8206c1c046cc8d71cc395d4146547#95d70be108a41634e441365746b7af85",
                      lock_fileb)

        # Go back to main orchestrator
        client.save({LOCKFILE: lock_fileb})
        client.run("info . --lock")
