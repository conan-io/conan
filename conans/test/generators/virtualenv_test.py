import copy
import os
import unittest

from conans import tools
from conans.test.utils.tools import TestClient
from conans.tools import os_info
from conans.util.files import load


class VirtualEnvGeneratorTest(unittest.TestCase):

    def basic_test(self, posix_empty_vars=True):
        env = copy.deepcopy(os.environ)
        client = TestClient()
        dep1 = """
import os
from conans import ConanFile

class BaseConan(ConanFile):
    name = "base"
    version = "0.1"

    def package_info(self):
        self.env_info.PATH.extend([os.path.join("basedir", "bin"),"samebin"])
        self.env_info.LD_LIBRARY_PATH.append(os.path.join("basedir", "lib"))
        self.env_info.BASE_VAR = "baseValue"
        self.env_info.SPECIAL_VAR = "baseValue"
        self.env_info.BASE_LIST = ["baseValue1", "baseValue2"]
        self.env_info.CPPFLAGS = ["-baseFlag1", "-baseFlag2"]
"""

        dep2 = """
import os
from conans import ConanFile

class DummyConan(ConanFile):
    name = "dummy"
    version = "0.1"
    requires = "base/0.1@lasote/testing"

    def package_info(self):
        self.env_info.PATH = [os.path.join("dummydir", "bin"),"samebin"]
        self.env_info.LD_LIBRARY_PATH.append(os.path.join("dummydir", "lib"))
        self.env_info.SPECIAL_VAR = "dummyValue"
        self.env_info.BASE_LIST = ["dummyValue1", "dummyValue2"]
        self.env_info.CPPFLAGS = ["-flag1", "-flag2"]
"""
        base = '''
[requires]
dummy/0.1@lasote/testing
[generators]
virtualenv
    '''
        client.save({"conanfile.py": dep1})
        client.run("export . lasote/testing")
        client.save({"conanfile.py": dep2}, clean_first=True)
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": base}, clean_first=True)
        client.run("install . --build")

        if os_info.is_windows and not os_info.is_posix:
            activate = load(os.path.join(client.current_folder, "activate.bat"))
            self.assertIn('SET PROMPT=(conanenv) %PROMPT%', activate)
            self.assertIn('SET BASE_LIST=dummyValue1;dummyValue2;baseValue1;baseValue2;%BASE_LIST%', activate)
            self.assertIn('SET BASE_VAR=baseValue', activate)
            self.assertIn('SET CPPFLAGS=-flag1 -flag2 -baseFlag1 -baseFlag2 %CPPFLAGS%', activate)
            self.assertIn('SET LD_LIBRARY_PATH=dummydir\\lib;basedir\\lib;%LD_LIBRARY_PATH%', activate)
            self.assertIn('SET PATH=dummydir\\bin;basedir\\bin;samebin;%PATH%', activate)
            self.assertIn('SET SPECIAL_VAR=dummyValue', activate)

            activate = load(os.path.join(client.current_folder, "activate.ps1"))
            self.assertIn('$env:BASE_LIST = "dummyValue1;dummyValue2;baseValue1;baseValue2;$env:BASE_LIST"', activate)
            self.assertIn('$env:BASE_VAR = "baseValue"', activate)
            self.assertIn('$env:CPPFLAGS = "-flag1 -flag2 -baseFlag1 -baseFlag2 $env:CPPFLAGS"', activate)
            self.assertIn('$env:LD_LIBRARY_PATH = "dummydir\\lib;basedir\\lib;$env:LD_LIBRARY_PATH"', activate)
            self.assertIn('$env:PATH = "dummydir\\bin;basedir\\bin;samebin;$env:PATH"', activate)
            self.assertIn('$env:SPECIAL_VAR = "dummyValue"', activate)

            deactivate = load(os.path.join(client.current_folder, "deactivate.bat"))
            self.assertIn('SET PROMPT=%s' % env.setdefault('PROMPT', ''), deactivate)
            self.assertIn('SET BASE_LIST=%s' % env.setdefault('BASE_LIST', ''), deactivate)
            self.assertIn('SET BASE_VAR=%s' % env.setdefault('BASE_VAR', ''), deactivate)
            self.assertIn('SET CPPFLAGS=%s' % env.setdefault('CPPFLAGS', ''), deactivate)
            self.assertIn('SET LD_LIBRARY_PATH=%s' % env.setdefault('LD_LIBRARY_PATH', ''), deactivate)
            self.assertIn('SET PATH=%s' % env.setdefault('PATH', ''), deactivate)
            self.assertIn('SET SPECIAL_VAR=%s' % env.setdefault('SPECIAL_VAR', ''), deactivate)

            deactivate = load(os.path.join(client.current_folder, "deactivate.ps1"))
            self.assertIn('$env:BASE_LIST = "%s"' % env.setdefault('BASE_LIST', ''), deactivate)
            self.assertIn('$env:BASE_VAR = "%s"' % env.setdefault('BASE_VAR', ''), deactivate)
            self.assertIn('$env:CPPFLAGS = "%s"' % env.setdefault('CPPFLAGS', ''), deactivate)
            self.assertIn('$env:LD_LIBRARY_PATH = "%s"' % env.setdefault('LD_LIBRARY_PATH', ''), deactivate)
            self.assertIn('$env:PATH = "%s"' % env.setdefault('PATH', ''), deactivate)
            self.assertIn('$env:SPECIAL_VAR = "%s"' % env.setdefault('SPECIAL_VAR', ''), deactivate)

        activate = load(os.path.join(client.current_folder, "activate.sh"))
        self.assertIn('OLD_PS1="$PS1"', activate)
        self.assertIn('export OLD_PS1', activate)
        self.assertIn('PS1="(conanenv) $PS1"', activate)
        self.assertIn('export PS1', activate)
        self.assertIn('BASE_LIST="dummyValue1":"dummyValue2":"baseValue1":"baseValue2":$BASE_LIST', activate)
        self.assertIn('export BASE_LIST', activate)
        self.assertIn('BASE_VAR="baseValue"', activate)
        self.assertIn('export BASE_VAR', activate)
        self.assertIn('CPPFLAGS="-flag1 -flag2 -baseFlag1 -baseFlag2 $CPPFLAGS"', activate)
        self.assertIn('export CPPFLAGS', activate)
        self.assertIn('SPECIAL_VAR="dummyValue"', activate)
        self.assertIn('export SPECIAL_VAR', activate)
        if os_info.is_windows:
            self.assertIn('LD_LIBRARY_PATH="dummydir\\lib":"basedir\\lib":$LD_LIBRARY_PATH', activate)
            self.assertIn('PATH="dummydir\\bin":"basedir\\bin":"samebin":$PATH', activate)
        else:
            self.assertIn('LD_LIBRARY_PATH="dummydir/lib":"basedir/lib":$LD_LIBRARY_PATH', activate)
            self.assertIn('PATH="dummydir/bin":"basedir/bin":"samebin":$PATH', activate)
        self.assertIn('export LD_LIBRARY_PATH', activate)
        self.assertIn('export PATH', activate)
        deactivate = load(os.path.join(client.current_folder, "deactivate.sh"))
        if posix_empty_vars:
            self.assertNotIn('unset PS1', deactivate)
            self.assertIn('unset OLD_PS1', deactivate)
            self.assertIn('unset BASE_LIST', deactivate)
            self.assertIn('unset BASE_VAR', deactivate)
            self.assertIn('unset CPPFLAGS', deactivate)
            self.assertIn('unset LD_LIBRARY_PATH', deactivate)
            self.assertIn('PATH="%s"' % env.setdefault('PATH', ''), deactivate)
            self.assertIn('export PATH', deactivate)
            self.assertIn('unset SPECIAL_VAR', deactivate)
        else:
            self.assertIn('OLD_PS1="%s"' % env.setdefault('OLD_PS1', ''), deactivate)
            self.assertIn('PS1=$OLD_PS1', deactivate)
            self.assertIn('export OLD_PS1', deactivate)
            self.assertNotIn('PS1="%s"' % env.setdefault('PS1', ''), deactivate)
            self.assertIn('export PS1', deactivate)
            self.assertIn('BASE_LIST="%s"' % env.setdefault('BASE_LIST', ''), deactivate)
            self.assertIn('export BASE_LIST', deactivate)
            self.assertIn('BASE_VAR="%s"' % env.setdefault('BASE_VAR', ''), deactivate)
            self.assertIn('export BASE_VAR', deactivate)
            self.assertIn('CPPFLAGS="%s"' % env.setdefault('CPPFLAGS', ''), deactivate)
            self.assertIn('export CPPFLAGS', deactivate)
            self.assertIn('LD_LIBRARY_PATH="%s"' % env.setdefault('LD_LIBRARY_PATH', ''), deactivate)
            self.assertIn('export LD_LIBRARY_PATH', deactivate)
            self.assertIn('PATH="%s"' % env.setdefault('PATH', ''), deactivate)
            self.assertIn('export PATH', deactivate)
            self.assertIn('SPECIAL_VAR="%s"' % env.setdefault('SPECIAL_VAR', ''), deactivate)
            self.assertIn('export SPECIAL_VAR', deactivate)

    def environment_test(self):
        env = {"PROMPT": "old_PROMPT",
               "OLD_PS1": "old_OLD_PS1",
               "PS1": "old_PS1",
               "BASE_LIST": "old_BASE_LIST",
               "BASE_VAR": "old_BASE_VAR",
               "CPPFLAGS": "old_CPPFLAGS",
               "LD_LIBRARY_PATH": "old_LD_LIBRARY_PATH",
               "SPECIAL_VAR": "old_SPECIAL_VAR"}
        with tools.environment_append(env):
            self.basic_test(posix_empty_vars=False)
