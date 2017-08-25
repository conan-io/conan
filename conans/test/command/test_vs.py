'''
Created on 25 de ago. de 2017

@author: drodri
'''
from conans.tools import vs_installation_path, vcvars_command
import os

print vs_installation_path("15")
print vs_installation_path("15")
print vs_installation_path("15")
print vs_installation_path("15")


class Settings(object):
    def get_safe(self, key):
        if key == "arch":
            return "x86"
        if key == "compiler.version":
            return "15"
        
settings = Settings()
cmd = vcvars_command(settings)
print cmd
os.system("%s && set" % cmd)