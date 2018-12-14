from six.moves.urllib.parse import urlencode

from conans.model.ref import ConanFileReference
from conans.model.rest_routes import RestRouteBuilder
from conans.paths import CONAN_MANIFEST, CONANINFO


class _ClientRouterBuilder(RestRouteBuilder):

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
            tmp = super(_ClientRouterBuilder, self).recipe
        else:
            tmp = super(_ClientRouterBuilder, self).recipe_revision
        return self.format_ref(tmp, ref)

    def for_packages(self, ref):
        """url for a recipe with or without revisions"""
        if not ref.revision:
            tmp = super(_ClientRouterBuilder, self).packages
        else:
            tmp = super(_ClientRouterBuilder, self).packages_revision
        return self.format_ref(tmp, ref)

    def for_recipe_file(self, ref, path):
        """url for a recipe file, with or without revisions"""
        if not ref.revision:
            tmp = super(_ClientRouterBuilder, self).recipe_file
        else:
            tmp = super(_ClientRouterBuilder, self).recipe_revision_file
        return self.format_ref_path(tmp, ref, path)

    def for_recipe_files(self, ref):
        """url for getting the recipe list"""
        if not ref.revision:
            tmp = super(_ClientRouterBuilder, self).recipe_files
        else:
            tmp = super(_ClientRouterBuilder, self).recipe_revision_files
        return self.format_ref(tmp, ref)

    def for_package(self, pref):
        """url for the package with or without revisions"""
        if not pref.conan.revision:
            tmp = super(_ClientRouterBuilder, self).package
        elif not pref.revision:
            tmp = super(_ClientRouterBuilder, self).package_recipe_revision
        else:
            tmp = super(_ClientRouterBuilder, self).package_revision

        return self.format_pref(tmp, pref)

    def for_package_file(self, pref, path):
        """url for getting a file from a package, with or without revisions"""
        if not pref.conan.revision:
            tmp = super(_ClientRouterBuilder, self).package_file
        elif not pref.revision:
            tmp = super(_ClientRouterBuilder, self).package_recipe_revision_file
        else:
            tmp = super(_ClientRouterBuilder, self).package_revision_file

        return self.format_pref_path(tmp, pref, path)

    def for_package_files(self, pref):
        """url for getting the recipe list"""
        if not pref.conan.revision:
            tmp = super(_ClientRouterBuilder, self).package_files
        elif not pref.revision:
            tmp = super(_ClientRouterBuilder, self).package_recipe_revision_files
        else:
            tmp = super(_ClientRouterBuilder, self).package_revision_files

        return self.format_pref(tmp, pref)


class ClientBaseRouterBuilder(_ClientRouterBuilder):
    """Base urls, e.j:  /ping"""
    pass


class ClientSearchRouterBuilder(ClientBaseRouterBuilder):
    """Search urls shared between v1 and v2"""

    def __init__(self, base_url):
        self.base_url = base_url + "/conans"

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
        return "%s%s" % (self.common_search, query)

    def search_packages(self, ref, query=None):
        """URL search packages for a recipe"""
        url = self.format_ref(self.common_search_packages, ref.copy_clear_rev())
        if query:
            url += "?%s" % urlencode({"q": query})
        return url


class ClientUsersRouterBuilder(ClientBaseRouterBuilder):
    """Builds urls for users endpoint (shared v1 and v2)"""
    def __init__(self, base_url):
        self.base_url = base_url + "/users"


class ClientV1ConanRouterBuilder(ClientBaseRouterBuilder):
    """Builds urls for v1"""

    def __init__(self, base_url):
        self.base_url = base_url + "/conans"

    def remove_recipe(self, ref):
        """Remove recipe"""
        return self.for_recipe(ref.copy_clear_rev())

    def remove_recipe_files(self, ref):
        """Removes files from the recipe"""
        return self.format_ref(self.v1_remove_recipe_files, ref.copy_clear_rev())

    def remove_packages(self, ref):
        """Remove files from a package"""
        return self.format_ref(self.v1_remove_packages, ref.copy_clear_rev())

    def recipe_snapshot(self, ref):
        """get recipe manifest url"""
        return self.for_recipe(ref.copy_clear_rev())

    def package_snapshot(self, pref):
        """get recipe manifest url"""
        return self.for_package(pref.copy_clear_rev())

    def recipe_manifest(self, ref):
        """get recipe manifest url"""
        return self.format_ref(self.v1_recipe_digest, ref.copy_clear_rev())

    def package_manifest(self, pref):
        """get manifest url"""
        return self.format_ref(self.v1_package_digest, pref.copy_clear_rev())

    def recipe_download_urls(self, ref):
        """ urls to download the recipe"""
        return self.format_ref(self.v1_recipe_download_urls, ref.copy_clear_rev())

    def package_download_urls(self, pref):
        """ urls to download the package"""
        return self.format_pref(self.v1_package_download_urls, pref.copy_clear_rev())

    def recipe_upload_urls(self, ref):
        """ urls to upload the recipe"""
        return self.format_ref(self.v1_recipe_upload_urls, ref.copy_clear_rev())

    def package_upload_urls(self, pref):
        """ urls to upload the package"""
        return self.format_pref(self.v1_package_upload_urls, pref.copy_clear_rev())


class ClientV2ConanRouterBuilder(ClientBaseRouterBuilder):
    """Builds urls for v2"""

    def __init__(self, base_url):
        self.base_url = base_url + "/conans"

    def recipe_file(self, ref, path):
        """Recipe file url"""
        return self.for_recipe_file(ref, path)

    def package_file(self, pref, path):
        """Package file url"""
        return self.for_package_file(pref, path)

    def remove_recipe(self, ref):
        """Remove recipe url"""
        return self.for_recipe(ref.copy_clear_rev())

    def remove_package(self, pref):
        """Remove package url"""
        return self.for_package(pref.copy_clear_rev())

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
        return self.for_recipe_files(ref.copy_clear_rev())

    def package_snapshot(self, pref):
        """get recipe manifest url"""
        return self.for_package_files(pref.copy_clear_rev())
