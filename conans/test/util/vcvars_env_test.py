import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import save
import os


class VCVarsTest(unittest.TestCase):

    def basic(self):
        save("test1.bat", """@echo off
set MYVAR=OK
set MYVAR2=OK
""")

        save("test2.bat", """@echo off
if defined MYVAR (SET RESPONSE=%MYVAR%;Yeah!) else (SET RESPONSE=Nop!)
""")

        save("test3.bat", """@echo off
set VAR1=HOLA
set VAR1=ADIOS;%VAR1%
set VAR1=BYE;%VAR1%
""")

        def call(cmd):
            print (cmd, " => \t",)
            os.system(cmd)
            # print "MYVAR ", os.environ.get("MYVAR")
            print("")
        print("")
        call("set MYVAR=HOLA && echo %^MYVAR%")
        call("call set MYVAR=HOLA && echo %MYVAR%")
        call("call set MYVAR=HOLA && echo %^MYVAR%")
        call("call set MYVAR=HOLA && call echo %^MYVAR%")
        call("if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) && call echo %^RESPONSE%")
        call("if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) & call echo %^RESPONSE%")
        call("(if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!)) && call echo %^RESPONSE%")
        call("(if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!)) & call echo %^RESPONSE%")
        call("call set MYVAR=OK && if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) && call echo %^RESPONSE%")
        call("call set MYVAR=OK && (if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!)) && call echo %^RESPONSE%")
        call("call set MYVAR=OK && if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) & call echo %^RESPONSE%")
        call("call set MYVAR=OK & if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) && call echo %^RESPONSE%")
        call("call set MYVAR=OK & if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) & call echo %^RESPONSE%")
        call("call set MYVAR=OK & if defined %MYVAR% (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) && call echo %^RESPONSE%")
        call("call set MYVAR=OK & if defined %MYVAR% (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) & call echo %^RESPONSE%")
        call("call set MYVAR=OK & if defined %^MYVAR% (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) && call echo %^RESPONSE%")
        call("call set MYVAR=OK & if defined %^MYVAR% (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!) & call echo %^RESPONSE%")

        call("call test1.bat && echo %^MYVAR%")
        call("call test1.bat &  echo %^MYVAR%")
        call("call test1.bat && call echo %^MYVAR%")
        call("call test1.bat & call echo %^MYVAR%")
        call("call test1.bat && call test2.bat && call echo %RESPONSE%")
        call("call test1.bat && call (if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!)) && call echo %RESPONSE%")
        call('call test1.bat && call "if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!))" && call echo %RESPONSE%')
        call("call test1.bat && (if defined MYVAR (SET RESPONSE=Yeah!) else (SET RESPONSE=Nop!)) && call echo %RESPONSE%")
        call('call test1.bat && (if "%MYVAR%"=="" (SET RESPONSE=Nop!) else (SET RESPONSE=%^MYVAR%;Yeah!)) '
             "&& (if defined MYVAR2 (SET RESPONSE2=Oui!) else (SET RESPONSE2=Nein!)) "
             "&& call echo %RESPONSE% %RESPONSE2%")

        call('SET "VAR1=VALUE1" SET "VAR2=VALUE2" && call echo %VAR1% %VAR2%')
        call("call test3.bat && call echo %VAR1%")

    def conan_env_deps(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile, tools
import os

class HelloConan(ConanFile):
    settings = "os", "compiler", "arch"

    def build(self):
        print os.environ.get("CL")
        print os.environ.get("LIB")
        vcvars = tools.vcvars_command(self.settings)
        self.run(vcvars)
        print os.environ.get("CL")
        print os.environ.get("LIB")
'''
        files = {}
        files["conanfile.py"] = conanfile
        client.save(files)
        client.run("build .")
        # print client.user_io.out
