import unittest
from parameterized import parameterized

from conans.client.conf.compiler_id import detect_compiler_id, CompilerId, UNKNOWN_COMPILER, \
    GCC, LLVM_GCC, CLANG, APPLE_CLANG, SUNCC, VISUAL_STUDIO, MSVC, INTEL, QCC, MCST_LCC
from conans.test.unittests.util.tools_test import RunnerMock


class CompilerIdTest(unittest.TestCase):
    def test_no_output(self):
        compiler_id = detect_compiler_id("gcc", runner=RunnerMock())
        self.assertEqual(UNKNOWN_COMPILER, compiler_id)

    def test_bad_output(self):
        runner = RunnerMock()
        runner.output = "#define UNKNOWN 1"
        compiler_id = detect_compiler_id("gcc", runner=runner)
        self.assertEqual(UNKNOWN_COMPILER, compiler_id)

    def test_bad_numbers(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ A\n" \
                        "#define __GNUC_MINOR__ B\n" \
                        "#define __GNUC_PATCHLEVEL__ C\n"
        compiler_id = detect_compiler_id("gcc", runner=runner)
        self.assertEqual(UNKNOWN_COMPILER, compiler_id)

    def test_incomplete(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ 7"
        compiler_id = detect_compiler_id("gcc", runner=runner)
        self.assertEqual(UNKNOWN_COMPILER, compiler_id)

    def test_gcc(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ 7\n" \
                        "#define __GNUC_MINOR__ 3\n" \
                        "#define __GNUC_PATCHLEVEL__ 0\n"
        compiler_id = detect_compiler_id("gcc", runner=runner)
        self.assertEqual(CompilerId(GCC, 7, 3, 0), compiler_id)

    def test_llvm_gcc(self):
        runner = RunnerMock()
        runner.output = "#define __llvm__ 1\n" \
                        "#define __GNUC__ 7\n" \
                        "#define __GNUC_MINOR__ 3\n" \
                        "#define __GNUC_PATCHLEVEL__ 0\n"
        compiler_id = detect_compiler_id("gcc", runner=runner)
        self.assertEqual(CompilerId(LLVM_GCC, 7, 3, 0), compiler_id)

    def test_clang(self):
        runner = RunnerMock()
        # clang defines __GNUC__ and may define _MSC_VER as well (on Windows)
        runner.output = "#define _MSC_VER 1922\n" \
                        "#define __GNUC__ 4\n" \
                        "#define __GNUC_MINOR__ 1\n" \
                        "#define __GNUC_PATCHLEVEL__ 1\n" \
                        "#define __clang__ 1\n"\
                        "#define __clang_major__ 9\n" \
                        "#define __clang_minor__ 0\n" \
                        "#define __clang_patchlevel__ 1\n"
        compiler_id = detect_compiler_id("clang", runner=runner)
        self.assertEqual(CompilerId(CLANG, 9, 0, 1), compiler_id)

    def test_apple_clang(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ 4\n" \
                        "#define __GNUC_MINOR__ 1\n" \
                        "#define __GNUC_PATCHLEVEL__ 1\n" \
                        "#define __clang__ 1\n"\
                        "#define __clang_major__ 10\n" \
                        "#define __clang_minor__ 0\n" \
                        "#define __clang_patchlevel__ 1\n" \
                        "#define __apple_build_version__ 10010046\n"
        compiler_id = detect_compiler_id("clang", runner=runner)
        self.assertEqual(CompilerId(APPLE_CLANG, 10, 0, 1), compiler_id)

    def test_suncc(self):
        runner = RunnerMock()
        runner.output = "#define __SUNPRO_CC 0x450\n"
        compiler_id = detect_compiler_id("suncc", runner=runner)
        self.assertEqual(CompilerId(SUNCC, 4, 5, 0), compiler_id)

    @parameterized.expand([("MSC_CMD_FLAGS=-D_MSC_VER=1400", 8, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1500", 9, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1600", 10, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1700", 11, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1800", 12, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1900", 14, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1910", 15, 0, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1911", 15, 3, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1912", 15, 5, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1913", 15, 6, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1914", 15, 7, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1915", 15, 8, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1916", 15, 9, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1921", 16, 1, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1922", 16, 2, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1923", 16, 3, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1924", 16, 4, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1925", 16, 5, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1926", 16, 6, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1927", 16, 7, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1928", 16, 8, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1928 -D_MSC_FULL_VER=192829500", 16, 9, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1929", 16, 10, 0),
                           ("MSC_CMD_FLAGS=-D_MSC_VER=1929 -D_MSC_FULL_VER=192930100", 16, 11, 0),
                           ])
    def test_visual_studio(self, line, major, minor, patch):
        runner = RunnerMock()
        runner.output = line
        compiler_id = detect_compiler_id("cl", runner=runner)
        self.assertEqual(CompilerId(VISUAL_STUDIO, major, minor, patch), compiler_id)

    def test_msvc(self):
        runner = RunnerMock()
        runner.output = "MSC_CMD_FLAGS=-D_MSC_VER=1930"
        compiler_id = detect_compiler_id("cl", runner=runner)
        self.assertEqual(CompilerId(MSVC, 19, 30, 0), compiler_id)

    def test_intel(self):
        runner = RunnerMock()
        # Intel C++ may define __GNUC__ and _MSC_VER for compatibility
        runner.output = "#define _MSC_VER 1922\n" \
                        "#define __GNUC__ 4\n" \
                        "#define __GNUC_MINOR__ 1\n" \
                        "#define __GNUC_PATCHLEVEL__ 1\n" \
                        "#define __INTEL_COMPILER 1900\n" \
                        "#define __INTEL_COMPILER_UPDATE 3\n"
        compiler_id = detect_compiler_id("clang", runner=runner)
        self.assertEqual(CompilerId(INTEL, 19, 0, 3), compiler_id)

    def test_qcc(self):
        runner = RunnerMock()
        runner.output = "#define __QNX__ 1\n" \
                        "#define __GNUC__ 4\n" \
                        "#define __GNUC_MINOR__ 2\n" \
                        "#define __GNUC_PATCHLEVEL__ 4\n"
        compiler_id = detect_compiler_id("qcc", runner=runner)
        self.assertEqual(CompilerId(QCC, 4, 2, 4), compiler_id)

    def test_mcst_lcc(self):
        runner = RunnerMock()
        runner.output = "#define __LCC__ 125\n" \
                        "#define __LCC_MINOR__ 6\n" \
                        "#define __e2k__ 1\n"
        compiler_id = detect_compiler_id("lcc", runner=runner)
        self.assertEqual(CompilerId(MCST_LCC, 1, 25, 6), compiler_id)
