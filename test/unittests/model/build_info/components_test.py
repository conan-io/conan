from conan.internal.model.cpp_info import CppInfo


class TestCppInfoComponents:

    def test_components_set(self):
        cpp_info = CppInfo(set_defaults=True)
        cpp_info.components["liba"].libs = ["liba"]
        cpp_info.components["libb"].includedirs.append("includewhat")
        cpp_info.components["libc"].libs.append("thelibc")
        assert list(cpp_info.components.keys()) == ["liba", "libb", "libc"]

        assert cpp_info.components["libb"].includedirs == ["include", "includewhat"]
        assert cpp_info.components["libc"].libs == ["thelibc"]

        import pytest
        with pytest.raises(AttributeError):
            cpp_info.required_components = ["liba::liba"]

    def test_no_components_inside_components(self):
        cpp_info = CppInfo()
        import pytest
        with pytest.raises(AttributeError):
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
        assert ["include"] == info.components["OpenSSL"].includedirs
        assert ["lib"] == info.components["OpenSSL"].libdirs
        assert ["build"] == info.components["OpenSSL"].builddirs
        assert ["bin"] == info.components["OpenSSL"].bindirs
        assert ["res"] == info.components["OpenSSL"].resdirs
        assert ["headers"] == info.components["Crypto"].includedirs
        assert ["libraries"] == info.components["Crypto"].libdirs
        assert ["build_scripts"] == info.components["Crypto"].builddirs
        assert ["binaries"] == info.components["Crypto"].bindirs
        assert ["resources"] == info.components["Crypto"].resdirs

        info.components["Crypto"].includedirs = ["different_include"]
        info.components["Crypto"].libdirs = ["different_lib"]
        info.components["Crypto"].builddirs = ["different_build"]
        info.components["Crypto"].bindirs = ["different_bin"]
        info.components["Crypto"].resdirs = ["different_res"]
        assert ["different_include"] == info.components["Crypto"].includedirs
        assert ["different_lib"] == info.components["Crypto"].libdirs
        assert ["different_build"] == info.components["Crypto"].builddirs
        assert ["different_bin"] == info.components["Crypto"].bindirs
        assert ["different_res"] == info.components["Crypto"].resdirs

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
        assert ["different_include", "another_include", "another_other_include"] == \
                         info.components["Crypto"].includedirs
        assert ["different_lib", "another_lib", "another_other_lib"] == \
                         info.components["Crypto"].libdirs
        assert ["different_build", "another_build", "another_other_build"] == \
                         info.components["Crypto"].builddirs
        assert ["different_bin", "another_bin", "another_other_bin"] == \
                         info.components["Crypto"].bindirs
        assert ["different_res", "another_res", "another_other_res"] == \
                         info.components["Crypto"].resdirs
