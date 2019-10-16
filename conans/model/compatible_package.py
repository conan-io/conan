from conans.model.info import ConanInfo


class CompatiblePackage(object):

    def __init__(self, conanfile):
        self.settings = conanfile.settings.copy()
        # self.options = conanfile.options.copy()  # FIXME: doesn't work
        self.info = conanfile.info.copy()

    def package_id(self, default_package_id_mode):
        self.info.settings = self.settings.values
        return self.info.package_id()
