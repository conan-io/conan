LOCAL_RECIPES_INDEX = "local-recipes-index"


class Remote:
    """
    The ``Remote`` class represents a remote registry of packages.
    """
    def __init__(self, name, url, verify_ssl=True, disabled=False, allowed_packages=None,
                 remote_type=None, recipes_only=False, force_auth=False):
        """ A Remote object can be constructed to be passed as an argument to
        RemotesAPI methods. When possible, it is better to use Remote objects returned by the API,
        but for the ``RemotesAPI.add()`` method, for which a new constructed object is necessary.
        It is recommended to use named arguments like ``Remote(..., verify_ssl=False)`` in
        the constructor.

        :param name: The name of the remote.
        :param url: The URL of the remote repository (or local folder for "local-recipes-index").
        :param verify_ssl: Enable SSL Certificate validation.
        :param disabled: Disable the remote repository.
        :param allowed_packages: List of patterns of allowed packages from this remote
        :param remote_type: Type of the remote repository, use "local-recipes-index" or ``None``
        :param recipes_only: If True, binaries form this remote will be ignored and never used
        :param force_auth: If True, Conan will not attempt anonymous access to this remote,
            going directly for the authenticated credentials instead.
        """
        self.name = name  # Read only, is the key
        self.url = url
        self.verify_ssl = verify_ssl
        self.disabled = disabled
        self.allowed_packages = allowed_packages
        self.recipes_only = recipes_only
        self.remote_type = remote_type
        self.force_auth = force_auth
        self._caching = {}

    def __eq__(self, other):
        if other is None:
            return False
        return (self.name == other.name and self.url == other.url and
                self.verify_ssl == other.verify_ssl and self.disabled == other.disabled)

    def __str__(self):
        allowed_msg = ""
        if self.allowed_packages:
            allowed_msg = ", Allowed packages: {}".format(", ".join(self.allowed_packages))
        if self.recipes_only:
            allowed_msg += ", Recipes only"
        if self.force_auth:
            allowed_msg += ", Forced authentication"
        if self.remote_type == LOCAL_RECIPES_INDEX:
            return "{}: {} [{}, Enabled: {}{}]".format(self.name, self.url, LOCAL_RECIPES_INDEX,
                                                       not self.disabled, allowed_msg)
        return "{}: {} [Verify SSL: {}, Enabled: {}{}]".format(self.name, self.url, self.verify_ssl,
                                                               not self.disabled, allowed_msg)

    def __repr__(self):
        return str(self)

    def invalidate_cache(self):
        """ If external operations might have modified the remote since it was instantiated,
        this method can be called to invalidate the cache.
        Note that this is done automatically when the remote is used in any operation by Conan,
        such as uploading packages, so this method is not usually needed when only interacting
        with the Conan API"""
        self._caching = {}


def _is_package_allowed(remote, reference):
    """ Returns True if the package reference is allowed to be used from this remote,
    based on the allowed_packages patterns.

    Patterns starting with ``!`` (or ``~``) are exclusions that always win. A reference
    is allowed if no exclusion matches it and, when there are non-negated patterns, at
    least one of them matches. If no patterns are defined, all packages are allowed.
    """
    if not remote.allowed_packages:
        return True
    excluded = [p[1:] for p in remote.allowed_packages if p.startswith(("!", "~"))]
    included = [p for p in remote.allowed_packages if not p.startswith(("!", "~"))]
    if any(reference.matches(p, is_consumer=False) for p in excluded):
        return False
    return not included or any(reference.matches(p, is_consumer=False) for p in included)
