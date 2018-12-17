from six.moves.urllib.parse import urlencode

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.rest_routes import RestRoutes
from conans.paths import CONAN_MANIFEST, CONANINFO


class ClientBaseRouterBuilder(object):
    bad_package_revision = "It is needed to specify the recipe revision if you " \
                           "specify a package revision"

    def __init__(self, base_url):
        self.routes = RestRoutes(base_url)

    def ping(self):
        return self.routes.ping

    @staticmethod
    def format_ref(url, ref):
        url = url.format(name=ref.name, version=ref.version, username=ref.user,
                         channel=ref.channel, revision=ref.revision)
        return url

    @staticmethod
    def format_ref_path(url, ref, path):
        url = url.format(name=ref.name, version=ref.version, username=ref.user,
                         channel=ref.channel, revision=ref.revision, path=path)
        return url

    @staticmethod
    def format_pref(url, pref):
        ref = pref.conan
        url = url.format(name=ref.name, version=ref.version, username=ref.user,
                         channel=ref.channel, revision=ref.revision, package_id=pref.package_id,
                         p_revision=pref.revision)
        return url

    @staticmethod
    def format_pref_path(url, pref, path):
        ref = pref.conan
        url = url.format(name=ref.name, version=ref.version, username=ref.user,
                         channel=ref.channel, revision=ref.revision, package_id=pref.package_id,
                         p_revision=pref.revision, path=path)
        return url

    def for_recipe(self, ref):
        """url for a recipe with or without revisions"""
        if not ref.revision:
            tmp = self.routes.recipe
        else:
            tmp = self.routes.recipe_revision
        return self.format_ref(tmp, ref)

    def for_packages(self, ref):
        """url for a recipe with or without revisions"""
        if not ref.revision:
            tmp = self.routes.packages
        else:
            tmp = self.routes.packages_revision
        return self.format_ref(tmp, ref)

    def for_recipe_file(self, ref, path):
        """url for a recipe file, with or without revisions"""
        if not ref.revision:
            tmp = self.routes.recipe_file
        else:
            tmp = self.routes.recipe_revision_file
        return self.format_ref_path(tmp, ref, path)

    def for_recipe_files(self, ref):
        """url for getting the recipe list"""
        if not ref.revision:
            tmp = self.routes.recipe_files
        else:
            tmp = self.routes.recipe_revision_files
        return self.format_ref(tmp, ref)

    def for_package(self, pref):
        """url for the package with or without revisions"""
        if not pref.conan.revision:
            if pref.revision:
                raise ConanException(self.bad_package_revision)
            tmp = self.routes.package
        elif not pref.revision:
            tmp = self.routes.package_recipe_revision
        else:
            tmp = self.routes.package_revision

        return self.format_pref(tmp, pref)

    def for_package_file(self, pref, path):
        """url for getting a file from a package, with or without revisions"""
        if not pref.conan.revision:
            if pref.revision:
                raise ConanException(self.bad_package_revision)
            tmp = self.routes.package_file
        elif not pref.revision:
            tmp = self.routes.package_recipe_revision_file
        else:
            tmp = self.routes.package_revision_file

        return self.format_pref_path(tmp, pref, path)

    def for_package_files(self, pref):
        """url for getting the recipe list"""
        if not pref.conan.revision:
            if pref.revision:
                raise ConanException(self.bad_package_revision)
            tmp = self.routes.package_files
        elif not pref.revision:
            tmp = self.routes.package_recipe_revision_files
        else:
            tmp = self.routes.package_revision_files

        return self.format_pref(tmp, pref)


class ClientSearchRouterBuilder(ClientBaseRouterBuilder):
    """Search urls shared between v1 and v2"""

    def __init__(self, base_url):
        super(ClientSearchRouterBuilder, self).__init__(base_url + "/conans")

    def search(self, pattern, ignorecase):
        """URL search recipes"""
        query = ''
        if pattern:
            if isinstance(pattern, ConanFileReference):
                pattern = pattern.full_repr()
            params = {"q": pattern}
            if not ignorecase:
                params["ignorecase"] = "False"
            query = "?%s" % urlencode(params)
        return "%s%s" % (self.routes.common_search, query)

    def search_packages(self, ref, query=None):
        """URL search packages for a recipe"""
        route = self.routes.common_search_packages_revision \
            if ref.revision else self.routes.common_search_packages
        url = self.format_ref(route, ref)
        if query:
            url += "?%s" % urlencode({"q": query})
        return url


class ClientUsersRouterBuilder(ClientBaseRouterBuilder):
    """Builds urls for users endpoint (shared v1 and v2)"""
    def __init__(self, base_url):
        super(ClientUsersRouterBuilder, self).__init__(base_url + "/users")

    def common_authenticate(self):
        return self.routes.common_authenticate

    def common_check_credentials(self):
        return self.routes.common_check_credentials


class ClientV1ConanRouterBuilder(ClientBaseRouterBuilder):
    """Builds urls for v1"""

    def __init__(self, base_url):
        super(ClientV1ConanRouterBuilder, self).__init__(base_url + "/conans")

    def remove_recipe(self, ref):
        """Remove recipe"""
        return self.for_recipe(ref.copy_clear_rev())

    def remove_recipe_files(self, ref):
        """Removes files from the recipe"""
        return self.format_ref(self.routes.v1_remove_recipe_files, ref.copy_clear_rev())

    def remove_packages(self, ref):
        """Remove files from a package"""
        return self.format_ref(self.routes.v1_remove_packages, ref.copy_clear_rev())

    def recipe_snapshot(self, ref):
        """get recipe manifest url"""
        return self.for_recipe(ref.copy_clear_rev())

    def package_snapshot(self, pref):
        """get recipe manifest url"""
        return self.for_package(pref.copy_clear_rev())

    def recipe_manifest(self, ref):
        """get recipe manifest url"""
        return self.format_ref(self.routes.v1_recipe_digest, ref.copy_clear_rev())

    def package_manifest(self, pref):
        """get manifest url"""
        return self.format_pref(self.routes.v1_package_digest, pref.copy_clear_rev())

    def recipe_download_urls(self, ref):
        """ urls to download the recipe"""
        return self.format_ref(self.routes.v1_recipe_download_urls, ref.copy_clear_rev())

    def package_download_urls(self, pref):
        """ urls to download the package"""
        return self.format_pref(self.routes.v1_package_download_urls, pref.copy_clear_rev())

    def recipe_upload_urls(self, ref):
        """ urls to upload the recipe"""
        return self.format_ref(self.routes.v1_recipe_upload_urls, ref.copy_clear_rev())

    def package_upload_urls(self, pref):
        """ urls to upload the package"""
        return self.format_pref(self.routes.v1_package_upload_urls, pref.copy_clear_rev())


class ClientV2ConanRouterBuilder(ClientBaseRouterBuilder):
    """Builds urls for v2"""

    def __init__(self, base_url):
        super(ClientV2ConanRouterBuilder, self).__init__(base_url + "/conans")

    def recipe_file(self, ref, path):
        """Recipe file url"""
        return self.for_recipe_file(ref, path)

    def package_file(self, pref, path):
        """Package file url"""
        return self.for_package_file(pref, path)

    def remove_recipe(self, ref):
        """Remove recipe url"""
        return self.for_recipe(ref)

    def remove_package(self, pref):
        """Remove package url"""
        return self.for_package(pref)

    def remove_all_packages(self, ref):
        """Remove package url"""
        return self.for_packages(ref)

    def recipe_manifest(self, ref):
        """Get the url for getting a conanmanifest.txt from a recipe"""
        return self.for_recipe_file(ref, CONAN_MANIFEST)

    def package_manifest(self, pref):
        """Get the url for getting a conanmanifest.txt from a package"""
        return self.for_package_file(pref, CONAN_MANIFEST)

    def package_info(self, pref):
        """Get the url for getting a conaninfo.txt from a package"""
        return self.for_package_file(pref, CONANINFO)

    def recipe_snapshot(self, ref):
        """get recipe manifest url"""
        return self.for_recipe_files(ref)

    def package_snapshot(self, pref):
        """get recipe manifest url"""
        return self.for_package_files(pref)
