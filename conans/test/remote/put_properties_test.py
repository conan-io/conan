import os
import unittest
from conans.test.utils.tools import TestClient, TestRequester, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save


class PutPropertiesTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def create_empty_property_file_test(self):

        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client.save(files)
        client.run("export lasote/stable")
        props_file = client.client_cache.put_headers_path
        self.assertTrue(os.path.exists(props_file))

    def put_properties_test(self):
        wanted_vars = {"MyHeader1": "MyHeaderValue1;MyHeaderValue2", "Other": "Value"}

        class RequesterCheckHeaders(TestRequester):
            def put(self, url, data, headers=None, verify=None, auth=None):
                for name, value in wanted_vars.items():
                    value1 = headers[name]
                    if value1 != value:
                        raise Exception()
                return super(RequesterCheckHeaders, self).put(url, data, headers, verify, auth)

        self.client = TestClient(requester_class=RequesterCheckHeaders, servers=self.servers,
                                 users={"default": [("lasote", "mypass")]})
        _create_property_files(self.client, wanted_vars)

        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("upload Hello0/0.1@lasote/stable -c")


def _create_property_files(client, values):
    lines = ["#Some comment", " #Some comments"]
    for name, value in values.items():
        lines.append("%s=%s" % (name, value))
    save(client.client_cache.put_headers_path, "\n".join(lines))
