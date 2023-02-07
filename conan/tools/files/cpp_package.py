import json
from conans.util.files import load, save


class CppPackage(object):
    """
    models conan_package.json, serializable object
    """

    DEFAULT_FILENAME = "cpp_package.json"

    def __init__(self):
        self.components = dict()

    @classmethod
    def load(cls, filename=DEFAULT_FILENAME):
        """
        loads package model into memory from the conan_package.json file
        :param filename: path to the cpp_package.json
        :return: a new instance of CppPackage
        """
        def from_json(o):
            if "components" in o:
                return {n: CppPackage.Component(c) for n, c in o["components"].items()}
            else:
                return o
        conan_package = CppPackage()
        conan_package.components = json.loads(load(filename), object_hook=from_json)
        return conan_package

    def save(self, filename=DEFAULT_FILENAME):
        """
        saves package model from memory into the cpp_package.json file
        :param filename: path to the cpp_package.json
        :return: None
        """
        text = json.dumps(self, default=lambda o: o.__dict__, indent=4)
        save(filename, text)

    def package_info(self, conanfile):
        """
        performs an automatically generated package_info method on conanfile, populating
        conanfile.package_info with the information available inside cpp_package.json
        :return: None
        """
        for cname, component in self.components.items():
            conanfile.cpp_info.components[cname].libs = component.libs
            conanfile.cpp_info.components[cname].requires = component.requires
            for generator, gname in component.names.items():
                # TODO: probably we want to revisit all this stuff with the new absolute
                #  target names via set_property
                conanfile.cpp_info.components[cname].set_property("cmake_target_name",
                                                                  "{}::{}".format(conanfile.ref.name,
                                                                                  gname))

    def add_component(self, name):
        """
        appens a new CppPackage.Configuration into the internal dictionary
        :param name: name of the given configuration (e.g. Debug)
        :return: a new CppPackage.Configuration instance (empty)
        """
        self.components[name] = CppPackage.Component()
        return self.components[name]

    class Component(object):
        """
        represents a single component (aka target) within package configuration
        """
        def __init__(self, values=None):
            if values:
                self.names = values["names"]
                self.requires = values["requires"]
                self.libs = values["libs"]
            else:
                self.names = dict()
                self.requires = []
                self.libs = []
