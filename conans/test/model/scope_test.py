import unittest
from conans.model.scope import Scopes


class ScopeTest(unittest.TestCase):

    def from_list_test(self):
        scope = Scopes.from_list(["theroot:thescope=http://conan.io"])
        self.assertEquals(scope["theroot"]["thescope"], "http://conan.io")
        self.assertEquals(scope.package_scope("theroot")["thescope"], "http://conan.io")

        scope = Scopes.from_list(["thescope=http://conan.io"])
        self.assertEquals(scope["0CONAN_ROOT*"]["thescope"], "http://conan.io")

        scope = Scopes.from_list(["theroot:thescope=TRUE"])
        self.assertTrue(scope["theroot"]["thescope"])

        scope = Scopes.from_list(["theroot:thescope=true"])
        self.assertTrue(scope["theroot"]["thescope"])

        scope = Scopes.from_list(["theroot:thescope=FALSE"])
        self.assertFalse(scope["theroot"]["thescope"])

        scope = Scopes.from_list(["theroot:thescope=false"])
        self.assertFalse(scope["theroot"]["thescope"])
