'''

This module handles user authentication and permissions
for read or write a conans or package.

This only reads from file the users and permissions.

Replace this module with other that keeps the interface or super class.

'''


from abc import ABCMeta, abstractmethod
from conans.errors import ForbiddenException, InternalErrorException,\
    AuthenticationException, ConanException
from conans.model.ref import ConanFileReference
from passlib.apache import HtpasswdFile
from conans.util.log import logger
import os

#  ############################################
#  ############ ABSTRACT CLASSES ##############
#  ############################################


class Authorizer(object):
    """
    Handles the access permissions to conans and packages
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def check_read_conan(self, username, conan_reference):
        """
        username: User that request to read the conans
        conan_reference: ConanFileReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_write_conan(self, username, conan_reference):
        """
        username: User that request to write the conans
        conan_reference: ConanFileReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_read_package(self, username, package_reference):
        """
        username: User that request to read the package
        package_reference: PackageReference
        """
        raise NotImplemented()

    @abstractmethod
    def check_write_package(self, username, package_reference):
        """
        username: User that request to write the package
        package_reference: PackageReference
        """
        raise NotImplemented()


class Authenticator(object):
    """
    Handles the user authentication
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def valid_user(self, username, plain_password):
        """
        username: User that request to read the conans
        conan_reference: ConanFileReference
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

    def __init__(self, _, server_config):
        # server_config: the server config object
        self.users = dict(server_config.users)

    def valid_user(self, username, plain_password):
        """
        username: Username to be authenticated
        plain_password: The password to authenticate with
        return: True if match False if don't
        """
        return username in self.users and self.users[username] == plain_password

class HTPasswdAuthenticator(Authenticator):
    """
    Handles the user authentication for htpasswd files
    htpasswd is the location of the htpasswd to use
    """
    def __init__(self, htfile, server_config):
        # server_config: the server config object
        if not os.path.isabs(htfile):
            htfile = os.path.join(server_config.conan_folder, htfile)
        self.htpasswd = HtpasswdFile(htfile)

    
    def valid_user(self, username, plain_password):
        """
        username: Username to be authenticated
        plain_password: The password to authenticate with
        return: True if match False if don't
        """
        # Update
        self.htpasswd.load_if_changed()
        # Verify
        return username in self.htpasswd.users() and self.htpasswd.check_password(username, plain_password)

class AuthorizeManager(Authenticator):
    """
    Manager for multiple authenticators
    """
    known_authenticators = {
        "basic" : BasicAuthenticator,
        "htpasswd" : HTPasswdAuthenticator
    }

    def __init__(self, server_config):
        # Uses the server config to generate all needed authenticators
        self.auths = []
        authentication = server_config.authentication
        logger.debug("Initialize default authentication: %s" % authentication)
        for auth in authentication:
            logger.debug("Creating entry %s" % auth)
            if auth not in self.known_authenticators:
                raise ConanException("Unknown authenticator provided: %s" % auth)
            self.auths.append(self.known_authenticators[auth](authentication[auth], server_config))
    
    def valid_user(self, username, plain_password):
        for m in self.auths:
            if m.valid_user(username, plain_password):
                return True
        return False

class BasicAuthorizer(Authorizer):
    """
    Reads permissions from the config file (server.cfg)
    """

    def __init__(self, read_permissions, write_permissions):
        """List of tuples with conanrefernce and users:

        [(conan_reference, "user, user, user"),
         (conan_reference2, "user3, user, user")] """

        self.read_permissions = read_permissions
        self.write_permissions = write_permissions

    def check_read_conan(self, username, conan_reference):
        """
        username: User that request to read the conans
        conan_reference: ConanFileReference
        """
        if conan_reference.user == username:
            return

        self._check_any_rule_ok(username, self.read_permissions, conan_reference)

    def check_write_conan(self, username, conan_reference):
        """
        username: User that request to write the conans
        conan_reference: ConanFileReference
        """
        if conan_reference.user == username:
            return True

        self._check_any_rule_ok(username, self.write_permissions, conan_reference)

    def check_delete_conan(self, username, conan_reference):
        """
        username: User that request to write the conans
        conan_reference: ConanFileReference
        """
        self.check_write_conan(username, conan_reference)

    def check_read_package(self, username, package_reference):
        """
        username: User that request to read the package
        package_reference: PackageReference
        """
        self.check_read_conan(username, package_reference.conan)

    def check_write_package(self, username, package_reference):
        """
        username: User that request to write the package
        package_reference: PackageReference
        """
        self.check_write_conan(username, package_reference.conan)

    def check_delete_package(self, username, package_reference):
        """
        username: User that request to write the package
        package_reference: PackageReference
        """
        self.check_write_package(username, package_reference)

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

    def _check_rule_ok(self, username, rule, conan_reference):
        """Checks if a rule specified in config file applies to current conans
        reference and current user"""
        try:
            rule_ref = ConanFileReference.loads(rule[0])
        except Exception:
            # TODO: Log error
            raise InternalErrorException("Invalid server configuration. "
                                         "Contact the administrator.")
        authorized_users = rule[1].split(",")
        if len(authorized_users) < 1:
            raise InternalErrorException("Invalid server configuration. "
                                         "Contact the administrator.")

        # Check if rule apply conan_reference
        if self._check_ref_apply_for_rule(rule_ref, conan_reference):
            if authorized_users[0] == "*" or username in authorized_users:
                return True  # Ok, applies and match username
            else:
                if username:
                    raise ForbiddenException("Permission denied")
                else:
                    raise AuthenticationException()

        return False

    def _check_ref_apply_for_rule(self, rule_ref, conan_reference):
        """Checks if a conans reference specified in config file applies to current conans
        reference"""
        name, version, user, channel = rule_ref
        return not((name != "*" and name != conan_reference.name) or
                   (version != "*" and version != conan_reference.version) or
                   (user != "*" and user != conan_reference.user) or
                   (channel != "*" and channel != conan_reference.channel))
