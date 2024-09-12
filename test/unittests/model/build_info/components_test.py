import unittest

from conans.model.build_info import CppInfo


class CppInfoComponentsTest(unittest.TestCase):

    def test_components_set(self):
        cpp_info = CppInfo(set_defaults=True)
        cpp_info.components["liba"].libs = ["liba"]
        cpp_info.components["libb"].includedirs.append("includewhat")
        cpp_info.components["libc"].libs.append("thelibc")
        self.assertListEqual(list(cpp_info.components.keys()), ["liba", "libb", "libc"])

        self.assertListEqual(cpp_info.components["libb"].includedirs, ["include", "includewhat"])
        self.assertListEqual(cpp_info.components["libc"].libs, ["thelibc"])

    def test_no_components_inside_components(self):
        cpp_info = CppInfo()
        with self.assertRaises(AttributeError):
            _ = cpp_info.components["libb"].components

    def test_cppinfo_components_dirs(self):
        info = CppInfo()
        info.components["OpenSSL"].includedirs = ["include"]
        info.components["OpenSSL"].libdirs = ["lib"]
        info.components["OpenSSL"].builddirs = ["build"]
        info.components["OpenSSL"].bindirs = ["bin"]
        info.components["OpenSSL"].resdirs = ["res"]
        info.components["Crypto"].includedirs = ["headers"]
        info.components["Crypto"].libdirs = ["libraries"]
        info.components["Crypto"].builddirs = ["build_scripts"]
        info.components["Crypto"].bindirs = ["binaries"]
        info.components["Crypto"].resdirs = ["resources"]
        self.assertEqual(["include"], info.components["OpenSSL"].includedirs)
        self.assertEqual(["lib"], info.components["OpenSSL"].libdirs)
        self.assertEqual(["build"], info.components["OpenSSL"].builddirs)
        self.assertEqual(["bin"], info.components["OpenSSL"].bindirs)
        self.assertEqual(["res"], info.components["OpenSSL"].resdirs)
        self.assertEqual(["headers"], info.components["Crypto"].includedirs)
        self.assertEqual(["libraries"], info.components["Crypto"].libdirs)
        self.assertEqual(["build_scripts"], info.components["Crypto"].builddirs)
        self.assertEqual(["binaries"], info.components["Crypto"].bindirs)
        self.assertEqual(["resources"], info.components["Crypto"].resdirs)

        info.components["Crypto"].includedirs = ["different_include"]
        info.components["Crypto"].libdirs = ["different_lib"]
        info.components["Crypto"].builddirs = ["different_build"]
        info.components["Crypto"].bindirs = ["different_bin"]
        info.components["Crypto"].resdirs = ["different_res"]
        self.assertEqual(["different_include"], info.components["Crypto"].includedirs)
        self.assertEqual(["different_lib"], info.components["Crypto"].libdirs)
        self.assertEqual(["different_build"], info.components["Crypto"].builddirs)
        self.assertEqual(["different_bin"], info.components["Crypto"].bindirs)
        self.assertEqual(["different_res"], info.components["Crypto"].resdirs)

        info.components["Crypto"].includedirs.extend(["another_include"])
        info.components["Crypto"].includedirs.append("another_other_include")
        info.components["Crypto"].libdirs.extend(["another_lib"])
        info.components["Crypto"].libdirs.append("another_other_lib")
        info.components["Crypto"].builddirs.extend(["another_build"])
        info.components["Crypto"].builddirs.append("another_other_build")
        info.components["Crypto"].bindirs.extend(["another_bin"])
        info.components["Crypto"].bindirs.append("another_other_bin")
        info.components["Crypto"].resdirs.extend(["another_res"])
        info.components["Crypto"].resdirs.append("another_other_res")
        self.assertEqual(["different_include", "another_include", "another_other_include"],
                         info.components["Crypto"].includedirs)
        self.assertEqual(["different_lib", "another_lib", "another_other_lib"],
                         info.components["Crypto"].libdirs)
        self.assertEqual(["different_build", "another_build", "another_other_build"],
                         info.components["Crypto"].builddirs)
        self.assertEqual(["different_bin", "another_bin", "another_other_bin"],
                         info.components["Crypto"].bindirs)
        self.assertEqual(["different_res", "another_res", "another_other_res"],
                         info.components["Crypto"].resdirs)
