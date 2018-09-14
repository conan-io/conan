

class Router(object):

    def __init__(self, base_url):
        self.base_url = base_url

    @property
    def recipe(self):
        return '%s/<name>/<version>/<username>/<channel>' % self.base_url

    @property
    def recipe_revision(self):
        return '%s/revisions/<revision>' % self.recipe

    @property
    def recipe_file(self):
        return '%s/<the_path:path>' % self.recipe

    @property
    def recipe_revision_file(self):
        return '%s/<the_path:path>' % self.recipe_revision

    @property
    def packages(self):
        return '%s/packages' % self.recipe

    @property
    def packages_revision(self):
        return '%s/packages' % self.recipe_revision

    @property
    def package(self):
        return '%s/<package_id>' % self.packages

    @property
    def package_recipe_revision(self):
        """Route for a package specifying the recipe revision but not the package revision"""
        return '%s/<package_id>' % self.packages_revision

    @property
    def package_revision(self):
        return '%s/<package_id>/revisions/<p_revision>' % self.packages_revision

    @property
    def package_file(self):
        return '%s/<the_path:path>' % self.package


    'lib/1.0/lasote/testing/packages/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/revisions/7200b02593a12d8cf214c92ddf805ea9'

    @property
    def package_revision_file(self):
        return '%s/<the_path:path>' % self.package_revision

    @property
    def package_recipe_revision_file(self):
        return '%s/<the_path:path>' % self.package_recipe_revision
