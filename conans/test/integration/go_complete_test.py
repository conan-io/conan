import os
import platform
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import scan_folder, uncompress_packaged_files
from conans.test.utils.tools import TestClient, TestServer
from conans.client.tools.env import environment_append

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

client_reusefile = '''
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
        ref = ConanFileReference.loads("stringutil/0.1@lasote/stable")
        files = {'conanfile.py': stringutil_conanfile,
                 'reverse.go': reverse,
                 'reverse_test.go': reverse_test,
                 'reverse.txt': reverse,
                 'hello/helloreverse.txt': reverse}
        files_without_conanfile = set(files.keys()) - set(["conanfile.py"])
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install %s --build missing" % str(ref))
        # Check compilation ok
        package_ids = self.client.cache.package_layout(ref).conan_packages()
        self.assertEqual(len(package_ids), 1)
        pref = PackageReference(ref, package_ids[0])
        self._assert_package_exists(pref, self.client.cache, files_without_conanfile)

        # Upload conans
        self.client.run("upload %s" % str(ref))

        # Check that conans exists on server
        server_paths = self.servers["default"].server_store
        rev = server_paths.get_last_revision(ref).revision
        conan_path = server_paths.export(ref.copy_with_rev(rev))
        self.assertTrue(os.path.exists(conan_path))

        # Upload package
        self.client.run("upload %s -p %s" % (str(ref), str(package_ids[0])))

        # Check library on server
        self._assert_package_exists_in_server(pref, server_paths, files_without_conanfile)

        # Now from other "computer" install the uploaded conans with same options (nothing)
        other_conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        other_conan.run("install %s --build missing" % str(ref))
        # Build should be empty
        build_path = other_conan.cache.package_layout(pref.ref).build(pref)
        self.assertFalse(os.path.exists(build_path))
        # Lib should exist
        self._assert_package_exists(pref, other_conan.cache, files_without_conanfile)

        client_reuse = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = {'conanfile.py': client_reusefile,
                 'src/hello/main.go': main}
        client_reuse.save(files)
        client_reuse.run("install . --build missing")

        with environment_append({"PATH": ['$GOPATH/bin'], 'GOPATH': client_reuse.current_folder}):
            if platform.system() == "Windows":
                command = "hello"
            else:
                command = './hello'
            client_reuse.run_command('go install hello')
            with client_reuse.chdir("bin"):
                client_reuse.run_command(command)
        self.assertIn("Hello, Go!", client_reuse.out)

    def _assert_package_exists(self, pref, paths, files):
        package_path = paths.package_layout(pref.ref).package(pref)
        self.assertTrue(os.path.exists(os.path.join(package_path)))
        real_files = scan_folder(package_path)
        for f in files:
            self.assertIn(f, real_files)

    def _assert_package_exists_in_server(self, pref, paths, files):
        folder = uncompress_packaged_files(paths, pref)
        real_files = scan_folder(folder)
        for f in files:
            self.assertIn(f, real_files)
