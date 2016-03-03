import unittest
from conans.test.tools import TestClient, TestBufferConanOutput, TestServer
from conans.paths import PACKAGES_FOLDER, EXPORT_FOLDER, BUILD_FOLDER, SRC_FOLDER
import os
from mock import Mock
from conans.client.userio import UserIO
from conans.test.utils.test_files import temp_folder


class RemoveTest(unittest.TestCase):

    def setUp(self):
        self.server_folder = temp_folder()
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"fenix": "mypass"},
                                 base_path=self.server_folder)  # exported users and passwords
        self.server = test_server
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default":[("fenix", "mypass")]})

        # Conans with and without packages created
        self.root_folder = {"H1": 'Hello/1.4.10/fenix/testing',
                            "H2": 'Hello/2.4.11/fenix/testing',
                            "B": 'Bye/0.14/fenix/testing',
                            "O": 'Other/1.2/fenix/testing'}

        files = {}
        for key, folder in self.root_folder.iteritems():
            files["%s/%s/conanfile.py" % (folder, EXPORT_FOLDER)] = ""
            files["%s/%s/conanmanifest.txt" % (folder, EXPORT_FOLDER)] = ""
            files["%s/%s/conans.txt" % (folder, SRC_FOLDER)] = ""
            for pack_id in (1, 2):
                pack_id = "%s_%s" % (pack_id, key)
                files["%s/%s/%s/conans.txt" % (folder, BUILD_FOLDER, pack_id)] = ""
                files["%s/%s/%s/conans.txt" % (folder, PACKAGES_FOLDER, pack_id)] = ""

        client.save(files, client.paths.store)
        self.client = client

        for folder in self.root_folder.itervalues():
            client.run("upload %s --all" % folder.replace("/fenix", "@fenix"))

        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def assert_folders(self, local_folders, remote_folders, build_folders, src_folders):
        for base_path, folders in [(self.client.paths, local_folders),
                                   (self.server.paths, remote_folders)]:
            root_folder = base_path.store
            for k, shas in folders.iteritems():
                folder = os.path.join(root_folder, self.root_folder[k])
                if shas is None:
                    self.assertFalse(os.path.exists(folder))
                else:
                    for value in (1, 2):
                        sha = "%s_%s" % (value, k)
                        package_folder = os.path.join(folder, "package", sha)
                        if value in shas:
                            self.assertTrue(os.path.exists(package_folder))
                        else:
                            self.assertFalse(os.path.exists(package_folder))

        root_folder = self.client.paths.store
        for k, shas in build_folders.iteritems():
            folder = os.path.join(root_folder, self.root_folder[k])
            if shas is None:
                self.assertFalse(os.path.exists(folder))
            else:
                for value in (1, 2):
                    sha = "%s_%s" % (value, k)
                    build_folder = os.path.join(folder, "build", sha)
                    if value in shas:
                        self.assertTrue(os.path.exists(build_folder))
                    else:
                        self.assertFalse(os.path.exists(build_folder))
        for k, value in src_folders.iteritems():
            folder = os.path.join(root_folder, self.root_folder[k], "source")
            if value:
                self.assertTrue(os.path.exists(folder))
            else:
                self.assertFalse(os.path.exists(folder))

    def basic_test(self):
        self.client.run("remove hello/* -f")
        self.assert_folders({"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            {"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertItemsEqual(["Other", "Bye"], folders)

    def basic_mocked_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=True)
        self.client.run("remove hello/*", user_io=mocked_user_io)
        self.assert_folders({"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            {"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertItemsEqual(["Other", "Bye"], folders)

    def basic_packages_test(self):
        self.client.run("remove hello/* -p -f")
        self.assert_folders({"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertItemsEqual(["Hello", "Other", "Bye"], folders)
        self.assertItemsEqual(["build", "source", "export"],
                              os.listdir(os.path.join(self.client.storage_folder,
                                                      "Hello/1.4.10/fenix/testing")))
        self.assertItemsEqual(["build", "source", "export"],
                              os.listdir(os.path.join(self.client.storage_folder,
                                                      "Hello/2.4.11/fenix/testing")))

    def builds_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=True)
        self.client.run("remove hello/* -b", user_io=mocked_user_io)
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertItemsEqual(["Hello", "Other", "Bye"], folders)
        self.assertItemsEqual(["package", "source", "export"],
                              os.listdir(os.path.join(self.client.storage_folder,
                                                      "Hello/1.4.10/fenix/testing")))
        self.assertItemsEqual(["package", "source", "export"],
                              os.listdir(os.path.join(self.client.storage_folder,
                                                      "Hello/2.4.11/fenix/testing")))

    def src_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=True)
        self.client.run("remove hello/* -s", user_io=mocked_user_io)
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": False, "H2": False, "B": True, "O": True})
        folders = os.listdir(self.client.storage_folder)
        self.assertItemsEqual(["Hello", "Other", "Bye"], folders)
        self.assertItemsEqual(["package", "build", "export"],
                              os.listdir(os.path.join(self.client.storage_folder,
                                                      "Hello/1.4.10/fenix/testing")))
        self.assertItemsEqual(["package", "build", "export"],
                              os.listdir(os.path.join(self.client.storage_folder,
                                                      "Hello/2.4.11/fenix/testing")))

    def reject_removal_test(self):
        mocked_user_io = UserIO(out=TestBufferConanOutput())
        mocked_user_io.request_boolean = Mock(return_value=False)
        self.client.run("remove hello/* -s -b -p", user_io=mocked_user_io)
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remote_build_error_test(self):
        self.client.run("remove hello/* -b -r=default", ignore_error=True)
        self.assertIn("Remotes don't have 'build' or 'src' folder", self.client.user_io.out)
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remote_packages_test(self):
        self.client.run("remove hello/* -p -r=default -f")
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [], "H2": [], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remote_conans_test(self):
        self.client.run("remove hello/* -r=default -f")
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": None, "H2": None, "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})
        remote_folder = os.path.join(self.server_folder, ".conan_server/data") 
        folders = os.listdir(remote_folder)
        self.assertItemsEqual(["Other", "Bye"], folders)

    def remove_specific_package_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -f")
        self.assert_folders({"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remove_specific_packages_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1,2_H1 -f")
        self.assert_folders({"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remove_specific_build_test(self):
        self.client.run("remove hello/1.4.10* -b=1_H1 -f")
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remove_specific_builds_test(self):
        self.client.run("remove hello/1.4.10* -b=1_H1,2_H1 -f")
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remove_remote_specific_package_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1 -f -r=default")
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})

    def remove_remote_specific_packages_test(self):
        self.client.run("remove hello/1.4.10* -p=1_H1,2_H1 -f -r=default")
        self.assert_folders({"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": [1, 2], "H2": [1, 2], "B": [1, 2], "O": [1, 2]},
                            {"H1": True, "H2": True, "B": True, "O": True})
