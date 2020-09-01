from conans.model import Generator


class ShimGenerator(Generator):
    @property
    def filename(self):
        return None

    @property
    def content(self):
        ret = {}
        print("*"*20)
        print("SHIM GENERATOR for {}".format(self.conanfile))
        print("*" * 20)
        return ret
