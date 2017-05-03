import unittest
from conans.server.service.authorize import BasicAuthorizer
from conans.errors import ForbiddenException, InternalErrorException
from conans.model.ref import ConanFileReference, PackageReference


class AuthorizerTest(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.openssl_ref = ConanFileReference.loads("openssl/2.0.1@lasote/testing")
        self.package_reference = PackageReference(self.openssl_ref, "123123123")
        self.openssl_ref2 = ConanFileReference.loads("openssl/2.0.2@lasote/testing")
        self.package_reference2 = PackageReference(self.openssl_ref2, "123123123")

    def invalid_rule_test(self):
        """Invalid rule input"""
        read_perms = ["invalid_reference", "lasote", ("*/*@*/*", "")]
        write_perms = []

        authorizer = BasicAuthorizer(read_perms, write_perms)
        self.assertRaises(InternalErrorException,
                          authorizer.check_read_conan, "pepe", self.openssl_ref)

    def check_wildcards_test(self):
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
        tmp_ref = ConanFileReference.loads("openssl/2.0.1@alfred/testing")
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
        tmp_ref = ConanFileReference.loads("openssl/2.0.1@alfred/testing")
        self.assertRaises(ForbiddenException,
                          authorizer.check_read_conan, "pepe", tmp_ref)

        tmp_ref = ConanFileReference.loads("openssl/2.0.1@lasote/otherchannel")
        authorizer.check_read_conan("pepe", tmp_ref)

    def permissions_test(self):
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
                          authorizer.check_read_package, "pepe", self.package_reference)

        # Owner can read package
        authorizer.check_read_package("lasote", self.package_reference)

        # Pepe can read other package
        authorizer.check_read_package("pepe", self.package_reference2)

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
        authorizer.check_write_package("lasote", self.package_reference)

        # Pepe can write package
        authorizer.check_write_package("pepe", self.package_reference)

        # Pepe can't write other package
        self.assertRaises(ForbiddenException,
                          authorizer.check_write_package, "pepe", self.package_reference2)

    def users_test(self):
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

