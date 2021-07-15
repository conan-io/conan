import os
import platform

from conans import load
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_local_contents_and_generators():

    client = TestClient()
    hello = str(GenConanfile().with_name("hello").with_version("1.0")
                .with_import("from conan.tools.files import save").with_import("import os"))
    hello += """

    def package(self):
        save(self, os.path.join(self.package_folder, "my_hello.lib"), "contents")

    def post_install(self):
        save(self, os.path.join(self.package_folder, "my_hello_bis.lib"), "contents")
    """
    client.save({"conanfile.py": hello})
    client.run("create .")

    chat = str(GenConanfile().with_name("chat").with_version("1.0")
               .with_import("from conan.tools.files import save").with_import("import os")
               .with_requires("hello/1.0"))
    chat += """
    def package(self):
        save(self, os.path.join(self.package_folder, "my_chat.lib"), "contents")
    """
    client.save({"conanfile.py": chat})
    client.run("create .")

    consumer = str(GenConanfile()
                   .with_import("import os")
                   .with_import("from conan.tools.files import save")
                   .with_import("from conan.tools.layout import cmake_layout")
                   .with_name("consumer")
                   .with_version("1.0").with_requires("chat/1.0")
                   .with_settings("os", "arch", "compiler", "build_type")
                   .with_requirement("chat/1.0")
                   .with_generator("CMakeDeps")
               )
    consumer += """
    def layout(self):
        cmake_layout(self)
    """
    client.save({"conanfile.py": consumer})
    client.run("install . --local-folder -if=my_install")
    multi = platform.system() == "Windows"
    if not multi:
        path = os.path.join(client.current_folder, "cmake-build-release", "conan")
    else:
        path = os.path.join(client.current_folder, "build", "conan")

    # The packages are there and are always scoped by build_type
    assert os.path.exists(os.path.join(path, "hello-Release", "my_hello.lib"))
    assert os.path.exists(os.path.join(path, "hello-Release", "my_hello_bis.lib"))
    assert os.path.exists(os.path.join(path, "chat-Release", "my_chat.lib"))

    # The generators point to the user space folder
    contents = load(os.path.join(path, "chat-release-x86_64-data.cmake"))
    assert 'set(chat_PACKAGE_FOLDER_RELEASE "{}")'.format(os.path.join(path, "chat-Release")) \
           in contents
