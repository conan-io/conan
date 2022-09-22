'''

This module handles user authentication and permissions
for read or write a conans or package.

This only reads from file the users and permissions.

Replace this module with other that keeps the interface or super class.

'''

from abc import ABCMeta, abstractmethod

import six

from conans.errors import AuthenticationException, ForbiddenException, InternalErrorException
from conans.model.ref import ConanFileReference


#  ############################################
#  ############ ABSTRACT CLASSES ##############
#  ############################################

@six.add_metaclass(ABCMeta)
class Authorizer(object):
    """
    Handles the access permissions to conans and packages
    """

    @abstractmethod
    def check_read_conan(self, username, ref):
        """
        username: User that request to read the conans
        ref: ConanFileReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_write_conan(self, username, ref):
        """
        username: User that request to write the conans
        ref: ConanFileReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_delete_conan(self, username, ref):
        """
        username: User requesting a recipe's deletion
        ref: ConanFileReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_read_package(self, username, pref):
        """
        username: User that request to read the package
        pref: PackageReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_write_package(self, username, pref):
        """
        username: User that request to write the package
        pref: PackageReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_delete_package(self, username, pref):
        """
        username: User requesting a package's deletion
        pref: PackageReference
        """
        raise NotImplemented()


@six.add_metaclass(ABCMeta)
class Authenticator(object):
    """
    Handles the user authentication
    """
    @abstractmethod
    def valid_user(self, username, plain_password):
        """
        username: User that request to read the conans
        plain_password:
        """
        raise NotImplemented()

#  ########################################################
#  ############ BASIC IMPLEMENTATION CLASSES ##############
#  ########################################################


class BasicAuthenticator(Authenticator):
    """
    Handles the user authentication from a dict of plain users and passwords.
    users is {username: plain-text-passwd}
    """

    def __init__(self, users):
        self.users = users

    def valid_user(self, username, plain_password):
        """
        username: User that request to read the conans
        plain_password:
        return: True if match False if don't
        """
        return username in self.users and self.users[username] == plain_password


class BasicAuthorizer(Authorizer):
    """
    Reads permissions from the config file (server.cfg)
    """

    def __init__(self, read_permissions, write_permissions):
        """List of tuples with refs and users:

        [(ref, "user, user, user"),
         (ref, "user3, user, user")] """

        self.read_permissions = read_permissions
        self.write_permissions = write_permissions

    def check_read_conan(self, username, ref):
        """
        username: User that request to read the conans
        ref: ConanFileReference
        """
        if ref.user == username:
            return

        self._check_any_rule_ok(username, self.read_permissions, ref)

    def check_write_conan(self, username, ref):
        """
        username: User that request to write the conans
        ref: ConanFileReference
        """
        if ref.user == username:
            return True

        self._check_any_rule_ok(username, self.write_permissions, ref)

    def check_delete_conan(self, username, ref):
        """
        username: User that request to write the conans
        ref: ConanFileReference
        """
        self.check_write_conan(username, ref)

    def check_read_package(self, username, pref):
        """
        username: User that request to read the package
        pref: PackageReference
        """
        self.check_read_conan(username, pref.ref)

    def check_write_package(self, username, pref):
        """
        username: User that request to write the package
        pref: PackageReference
        """
        self.check_write_conan(username, pref.ref)

    def check_delete_package(self, username, pref):
        """
        username: User that request to write the package
        pref: PackageReference
        """
        self.check_write_package(username, pref)

    def _check_any_rule_ok(self, username, rules, *args, **kwargs):
        for rule in rules:
            # raises if don't
            ret = self._check_rule_ok(username, rule, *args, **kwargs)
            if ret:  # A rule is applied ok, if not apply keep looking
                return True
        if username:
            raise ForbiddenException("Permission denied")
        else:
            raise AuthenticationException()

    def _check_rule_ok(self, username, rule, ref):
        """Checks if a rule specified in config file applies to current conans
        reference and current user"""
        try:
            rule_ref = ConanFileReference.loads(rule[0])
        except Exception:
            # TODO: Log error
            raise InternalErrorException("Invalid server configuration. "
                                         "Contact the administrator.")
        authorized_users = [_.strip() for _ in rule[1].split(",")]
        if len(authorized_users) < 1:
            raise InternalErrorException("Invalid server configuration. "
                                         "Contact the administrator.")

        # Check if rule apply ref
        if self._check_ref_apply_for_rule(rule_ref, ref):
            if authorized_users[0] == "*" or username in authorized_users:
                return True  # Ok, applies and match username
            else:
                if username:
                    if authorized_users[0] == "?":
                        return True  # Ok, applies and match any authenticated username
                    else:
                        raise ForbiddenException("Permission denied")
                else:
                    raise AuthenticationException()

        return False

    def _check_ref_apply_for_rule(self, rule_ref, ref):
        """Checks if a conans reference specified in config file applies to current conans
        reference"""
        name, version, user, channel, _ = rule_ref
        return not((name != "*" and name != ref.name) or
                   (version != "*" and version != ref.version) or
                   (user != "*" and user != ref.user) or
                   (channel != "*" and channel != ref.channel))
