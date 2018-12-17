
class RestRoutes(object):

    def __init__(self, base_url):
        self.base_url = base_url

    @property
    def recipe(self):
        return '%s/{name}/{version}/{username}/{channel}' % self.base_url

    @property
    def recipe_files(self):
        return '%s/files' % self.recipe

    @property
    def recipe_revision(self):
        return '%s/revisions/{revision}' % self.recipe

    @property
    def recipe_revision_files(self):
        return '%s/files' % self.recipe_revision

    @property
    def recipe_revisions(self):
        return '%s/revisions' % self.recipe

    @property
    def recipe_file(self):
        return '%s/files/{path}' % self.recipe

    @property
    def recipe_revision_file(self):
        return '%s/files/{path}' % self.recipe_revision

    @property
    def packages(self):
        return '%s/packages' % self.recipe

    @property
    def packages_revision(self):
        return '%s/packages' % self.recipe_revision

    @property
    def package(self):
        return '%s/{package_id}' % self.packages

    @property
    def package_files(self):
        return '%s/files' % self.package

    @property
    def package_recipe_revision(self):
        """Route for a package specifying the recipe revision but not the package revision"""
        return '%s/{package_id}' % self.packages_revision

    @property
    def package_recipe_revision_files(self):
        return '%s/files' % self.package_recipe_revision

    @property
    def package_revisions(self):
        return '%s/revisions' % self.package_recipe_revision

    @property
    def package_revision(self):
        return '%s/{p_revision}' % self.package_revisions

    @property
    def package_revision_files(self):
        return '%s/files' % self.package_revision

    @property
    def package_file(self):
        return '%s/files/{path}' % self.package

    @property
    def package_revision_file(self):
        return '%s/files/{path}' % self.package_revision

    @property
    def package_recipe_revision_file(self):
        return '%s/files/{path}' % self.package_recipe_revision

    # ONLY V1
    @property
    def v1_recipe_digest(self):
        return "%s/digest" % self.recipe

    @property
    def v1_package_digest(self):
        return "%s/digest" % self.package

    @property
    def v1_recipe_download_urls(self):
        return "%s/download_urls" % self.recipe

    @property
    def v1_package_download_urls(self):
        return "%s/download_urls" % self.package

    @property
    def v1_recipe_upload_urls(self):
        return "%s/upload_urls" % self.recipe

    @property
    def v1_package_upload_urls(self):
        return "%s/upload_urls" % self.package

    @property
    def v1_remove_recipe_files(self):
        return "%s/remove_files" % self.recipe

    @property
    def v1_remove_packages(self):
        return "%s/packages/delete" % self.recipe

    # COMMON URLS
    @property
    def ping(self):
        return "%s/ping" % self.base_url

    @property
    def common_search(self):
        return "%s/search" % self.base_url

    @property
    def common_search_packages(self):
        return "%s/search" % self.recipe

    @property
    def common_search_packages_revision(self):
        return "%s/search" % self.recipe_revision

    @property
    def common_authenticate(self):
        return "%s/authenticate" % self.base_url

    @property
    def common_check_credentials(self):
        return "%s/check_credentials" % self.base_url
