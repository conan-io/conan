class RestRoutes(object):
    ping = "ping"
    common_search = "conans/search"
    common_authenticate = "users/authenticate"
    oauth_authenticate = "users/token"
    common_check_credentials = "users/check_credentials"

    def __init__(self, matrix_params=False):
        if matrix_params:
            self.base = 'conans{matrix_params}'
            self.files_base = 'files{matrix_params}'
        else:
            self.base = 'conans'
            self.files_base = 'files'

    @property
    def recipe(self):
        return self.base + '/{name}/{version}/{username}/{channel}'

    @property
    def recipe_latest(self):
        return '%s/latest' % self.recipe

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
    def package_revisions(self):
        return '%s/revisions' % self.package_recipe_revision

    @property
    def package_revision(self):
        return '%s/{p_revision}' % self.package_revisions

    @property
    def package_revision_files(self):
        return '%s/files' % self.package_revision

    @property
    def package_revision_latest(self):
        return '%s/latest' % self.package_recipe_revision

    @property
    def package_revision_file(self):
        return '%s/files/{path}' % self.package_revision

    # ONLY V1
    @property
    def v1_updown_file(self):
        return "%s/{path}" % self.files_base

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

    @property
    def common_search_packages(self):
        return "%s/search" % self.recipe

    @property
    def common_search_packages_revision(self):
        return "%s/search" % self.recipe_revision
