import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load


class GeneratorsTest(unittest.TestCase):

    def test_base(self):
        base = '''
[generators]
cmake
gcc
qbs
qmake
scons
txt
visual_studio
xcode
ycm
    '''
        files = {"conanfile.txt": base}
        client = TestClient()
        client.save(files)
        client.run("install --build")
        self.assertEqual(sorted(['conanfile.txt', 'conaninfo.txt', 'conanbuildinfo.cmake',
                                 'conanbuildinfo.gcc', 'conanbuildinfo.qbs', 'conanbuildinfo.pri',
                                 'SConscript_conan', 'conanbuildinfo.txt', 'conanbuildinfo.props',
                                 'conanbuildinfo.xcconfig', '.ycm_extra_conf.py']),
                         sorted(os.listdir(client.current_folder)))

        qmake = load(os.path.join(client.current_folder, "conanbuildinfo.pri"))
        self.assertIn("CONAN_RESDIRS += ", qmake)
        self.assertEqual(qmake.count("CONAN_LIBS += "), 1)
