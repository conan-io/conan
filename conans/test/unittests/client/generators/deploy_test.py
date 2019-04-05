from conans.test.utils.test_files import temp_folder


class DeployGeneratorTest(unittest.TestCase):

    def setUp(self):
        self.conanfile = ConanFile(TestBufferConanOutput(), None)
        self.conanfile.initialize(Settings({}), EnvValues())
        self.generator = CMakeGenerator(conanfile)
        self.generator.output_path = temp_folder()

    def variables_setup_test(self):
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        self.conanfile.deps_cpp_info.update(cpp_info, ref.name)

        content = self.generator.content
        cmake_lines = content.splitlines()

