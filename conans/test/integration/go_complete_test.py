import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.context_manager import CustomEnvPath
import platform
from conans.test.utils.test_files import scan_folder
from conans.test.utils.test_files import uncompress_packaged_files
from nose.plugins.attrib import attr

stringutil_conanfile = '''
from conans import ConanFile

class Stringutil(ConanFile):
    name = "stringutil"
    version = "0.1"
    exports = '*'
    def package(self):
        self.copy("*")
'''

reverse = '''// Package stringutil contains utility functions for working with strings.
package stringutil

// Reverse returns its argument string reversed rune-wise left to right.
func Reverse(s string) string {
    r := []rune(s)
    for i, j := 0, len(r)-1; i < len(r)/2; i, j = i+1, j-1 {
        r[i], r[j] = r[j], r[i]
    }
    return string(r)
}
'''

reverse_test = '''package stringutil

import "testing"

func TestReverse(t *testing.T) {
    cases := []struct {
        in, want string
    }{
        {"Hello, world", "dlrow ,olleH"},
        {"", ""},
    }
    for _, c := range cases {
        got := Reverse(c.in)
        if got != c.want {
            t.Errorf("Reverse(%q) == %q, want %q", c.in, got, c.want)
        }
    }
}
'''

reuse_conanfile = '''
from conans import ConanFile

class Hello(ConanFile):
    name = "default"
    version = "0.1"
    exports = '*'
    requires = "stringutil/0.1@lasote/stable"
    def imports(self):
        self.copy("*.go", "./src/stringutil", "", "stringutil")
'''

main = '''package main

import (
    "fmt"
    "stringutil"
)

func main() {
    fmt.Printf(stringutil.Reverse("!oG ,olleH"))
}
'''


@attr('golang')
class GoCompleteTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def reuse_test(self):
        conan_reference = ConanFileReference.loads("stringutil/0.1@lasote/stable")
        files = {'conanfile.py': stringutil_conanfile,
                 'reverse.go': reverse,
                 'reverse_test.go': reverse_test,
                 'reverse.txt': reverse,
                 'hello/helloreverse.txt': reverse}
        files_without_conanfile = set(files.keys()) - set(["conanfile.py"])
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install %s --build missing" % str(conan_reference))
        # Check compilation ok
        package_ids = self.client.paths.conan_packages(conan_reference)
        self.assertEquals(len(package_ids), 1)
        package_ref = PackageReference(conan_reference, package_ids[0])
        self._assert_package_exists(package_ref, self.client.paths, files_without_conanfile)

        # Upload conans
        self.client.run("upload %s" % str(conan_reference))

        # Check that conans exists on server
        server_paths = self.servers["default"].paths
        conan_path = server_paths.export(conan_reference)
        self.assertTrue(os.path.exists(conan_path))

        # Upload package
        self.client.run("upload %s -p %s" % (str(conan_reference), str(package_ids[0])))

        # Check library on server
        self._assert_package_exists_in_server(package_ref, server_paths, files_without_conanfile)

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_conan.run("install %s --build missing" % str(conan_reference))
        # Build should be empty
        build_path = other_conan.paths.build(package_ref)
        self.assertFalse(os.path.exists(build_path))
        # Lib should exist
        self._assert_package_exists(package_ref, other_conan.paths, files_without_conanfile)

        reuse_conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = {'conanfile.py': reuse_conanfile,
                 'src/hello/main.go': main}
        reuse_conan.save(files)
        reuse_conan.run("install . --build missing")

        with CustomEnvPath(paths_to_add=['$GOPATH/bin'],
                           var_to_add=[('GOPATH', reuse_conan.current_folder), ]):

            if platform.system() == "Windows":
                command = "hello"
            else:
                command = './hello'
            reuse_conan.runner('go install hello', cwd=reuse_conan.current_folder)
            reuse_conan.runner(command, cwd=os.path.join(reuse_conan.current_folder, 'bin'))
        self.assertIn("Hello, Go!", reuse_conan.user_io.out)

    def _assert_package_exists(self, package_ref, paths, files):
        package_path = paths.package(package_ref)
        self.assertTrue(os.path.exists(os.path.join(package_path)))
        real_files = scan_folder(package_path)
        for f in files:
            self.assertIn(f, real_files)

    def _assert_package_exists_in_server(self, package_ref, paths, files):
        folder = uncompress_packaged_files(paths, package_ref)
        real_files = scan_folder(folder)
        for f in files:
            self.assertIn(f, real_files)
