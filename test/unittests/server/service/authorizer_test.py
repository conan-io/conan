import unittest

from conans.errors import AuthenticationException, ForbiddenException, InternalErrorException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.server.service.authorize import BasicAuthorizer


class AuthorizerTest(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.openssl_ref = RecipeReference.loads("openssl/2.0.1@lasote/testing")
        self.openssl_pref = PkgReference(self.openssl_ref, "123123123")
        self.openssl_ref2 = RecipeReference.loads("openssl/2.0.2@lasote/testing")
        self.openssl_pref2 = PkgReference(self.openssl_ref2, "123123123")

    def test_invalid_rule(self):
        """Invalid rule input"""
        read_perms = ["invalid_reference", "lasote", ("*/*@*/*", "")]
        write_perms = []

        authorizer = BasicAuthorizer(read_perms, write_perms)
        self.assertRaises(InternalErrorException,
                          authorizer.check_read_conan, "pepe", self.openssl_ref)

    def test_check_wildcards(self):
        # Only pepe can read openssl versions
        read_perms = [("openssl/*@lasote/testing", "pepe"), ("*/*@*/*", "*")]
        # Only pepe (and lasote because its owner) can write it and no more users can write
        write_perms = [(str(self.openssl_ref), "pepe")]

        authorizer = BasicAuthorizer(read_perms, write_perms)
        # Pepe can read all openssl versions
        authorizer.check_read_conan("pepe", self.openssl_ref)
        authorizer.check_read_conan("pepe", self.openssl_ref2)
        # Other user can't
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "juan", self.openssl_ref)
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "juan", self.openssl_ref2)

        # Only pepe can read versions 2.0.1 of lasote/testing
        read_perms = [("*/2.0.2@lasote/testing", "pepe"), ("*/*@*/*", "*")]
        authorizer = BasicAuthorizer(read_perms, write_perms)
        # Pepe can read openssl 2.0.1 version and 2.0.2 (only matches 2.0.2, so other is allowed)
        authorizer.check_read_conan("pepe", self.openssl_ref2)
        authorizer.check_read_conan("pepe", self.openssl_ref2)
        # Other user can't read 2.0.2
        authorizer.check_read_conan("juan", self.openssl_ref)
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "juan", self.openssl_ref2)

        # Only pepe can read openssl version 2.0.1 from any owner
        read_perms = [("openssl/2.0.1@*/testing", "pepe")]
        # Only pepe (and lasote because its owner) can write it and no more users can write
        write_perms = [(str(self.openssl_ref), "pepe")]

        authorizer = BasicAuthorizer(read_perms, write_perms)
        # Pepe can read any openssl/2.0.1
        authorizer.check_read_conan("pepe", self.openssl_ref)
        tmp_ref = RecipeReference.loads("openssl/2.0.1@alfred/testing")
        authorizer.check_read_conan("pepe", tmp_ref)
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "juan", self.openssl_ref)
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "juan", tmp_ref)

        # Only pepe can read openssl version 2.0.1 from lasote/any channel
        read_perms = [("openssl/2.0.1@lasote/*", "pepe")]
        # Only pepe (and lasote because its owner) can write it and no more users can write
        write_perms = [(str(self.openssl_ref), "pepe")]

        authorizer = BasicAuthorizer(read_perms, write_perms)
        # Pepe can read openssl/2.0.1 from any channel but only from lasote
        authorizer.check_read_conan("pepe", self.openssl_ref)
        tmp_ref = RecipeReference.loads("openssl/2.0.1@alfred/testing")
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "pepe", tmp_ref)

        tmp_ref = RecipeReference.loads("openssl/2.0.1@lasote/otherchannel")
        authorizer.check_read_conan("pepe", tmp_ref)

    def test_permissions(self):
        """Check that permissions logic is ok"""
        # Only lasote can read it but other conans can be readed
        read_perms = [(str(self.openssl_ref), "lasote"), ("*/*@*/*", "*")]
        # Only pepe (and lasote because its owner) can write it and no more users can write
        write_perms = [(str(self.openssl_ref), "pepe")]

        authorizer = BasicAuthorizer(read_perms, write_perms)

        # READ PERMISSIONS

        # Pepe can't read conans
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "pepe", self.openssl_ref)

        # Owner can read conans
        authorizer.check_read_conan("lasote", self.openssl_ref)

        # Pepe can read other conans
        authorizer.check_read_conan("pepe", self.openssl_ref2)

        # Pepe can't read package
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_package, "pepe", self.openssl_pref)

        # Owner can read package
        authorizer.check_read_package("lasote", self.openssl_pref)

        # Pepe can read other package
        authorizer.check_read_package("pepe", self.openssl_pref2)

        # WRITE PERMISSIONS

        # Pepe can write conans
        authorizer.check_write_conan("pepe", self.openssl_ref)

        # Juan can't write conans
        self.assertRaises(ForbiddenException,
                          authorizer.check_write_conan, "juan", self.openssl_ref)

        # Owner can write conans
        authorizer.check_write_conan("lasote", self.openssl_ref)

        # Pepe can't write other conans
        self.assertRaises(ForbiddenException,
                          authorizer.check_write_conan, "pepe", self.openssl_ref2)

        # Owner can write package
        authorizer.check_write_package("lasote", self.openssl_pref)

        # Pepe can write package
        authorizer.check_write_package("pepe", self.openssl_pref)

        # Pepe can't write other package
        self.assertRaises(ForbiddenException,
                          authorizer.check_write_package, "pepe", self.openssl_pref2)

    def test_authenticated_user_wildcard_permissions(self):
        """Check that authenciated user wildcard permissions logic is ok"""
        # Only authenticated users can read openssl
        read_perms = [(str(self.openssl_ref), "?"), ("*/*@*/*", "*")]
        # Authenticated users can write any
        write_perms = [("*/*@*/*", "?")]

        authorizer = BasicAuthorizer(read_perms, write_perms)

        # READ PERMISSIONS

        # Authenticated user can read conan
        authorizer.check_read_conan("pepe", self.openssl_ref)

        # Authenticated user can read package
        authorizer.check_read_package("pepe", self.openssl_pref)

        # Anonymous user can not read conan, they must authenticate
        self.assertRaises(AuthenticationException,
                          authorizer.check_read_conan, None, self.openssl_ref)

        # Anonymous user can not read package, they must authenticate
        self.assertRaises(AuthenticationException,
                          authorizer.check_read_package, None, self.openssl_pref)

        # WRITE PERMISSIONS

        # Authenticated user can write conan
        authorizer.check_write_conan("pepe", self.openssl_ref)

        # Authenticated user can write package
        authorizer.check_write_package("pepe", self.openssl_pref)

        # Anonymous user can not write conan, they must authenticate
        self.assertRaises(AuthenticationException,
                          authorizer.check_write_conan, None, self.openssl_ref)

        # Anonymous user can not write package, they must authenticate
        self.assertRaises(AuthenticationException,
                          authorizer.check_write_package, None, self.openssl_pref)

    def test_users(self):
        """Check that lists of user names are parsed correctly"""

        # Simple user list
        read_perms = [("openssl/*@lasote/testing", "user1,user2,user3")]
        authorizer = BasicAuthorizer(read_perms, [])
        for u in ['user1','user2','user3']:
            authorizer.check_read_conan(u, self.openssl_ref)

        # Spaces bewteen user names should be ignored
        read_perms = [("openssl/*@lasote/testing", "user1 , user2,\tuser3")]
        authorizer = BasicAuthorizer(read_perms, [])
        for u in ['user1','user2','user3']:
            authorizer.check_read_conan(u, self.openssl_ref)

