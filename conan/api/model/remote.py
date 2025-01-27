LOCAL_RECIPES_INDEX = "local-recipes-index"


class Remote:
    """
    The Remote class represents a remote registry of packages. It's a read-only opaque object that
    should not be created directly, but obtained from the relevant ``RemotesAPI`` subapi methods.
    """
    def __init__(self, name, url, verify_ssl=True, disabled=False, allowed_packages=None,
                 remote_type=None):
        self.name = name  # Read only, is the key
        """User-facing remote name"""
        self.url = url
        """URL endpoint of the Conan remote"""
        self.verify_ssl = verify_ssl
        #"""Whether to verify SSL certificates"""
        self.disabled = disabled
        #"""If this remote is disabled, it won't be taken into account for Conan operations"""
        self.allowed_packages = allowed_packages
        #"""Which packages this remote is allowed to fetch, or None if all packages are allowed"""
        self.remote_type = remote_type
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
        if self.remote_type == LOCAL_RECIPES_INDEX:
            return "{}: {} [{}, Enabled: {}{}]".format(self.name, self.url, LOCAL_RECIPES_INDEX,
                                                       not self.disabled, allowed_msg)
        return "{}: {} [Verify SSL: {}, Enabled: {}{}]".format(self.name, self.url, self.verify_ssl,
                                                               not self.disabled, allowed_msg)

    def __repr__(self):
        return str(self)

    def invalidate_cache(self):
        """
        Clears the package existence cache for this remote
        """
        self._caching = {}
