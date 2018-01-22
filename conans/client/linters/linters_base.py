# -*- coding: utf-8 -*-
from six import with_metaclass


global_registered_linters = {}

class RegisterLintersMeta(type):
    def __init__(cls, name, bases, dct):
        
        if not hasattr(cls,"category") and name != "LinterBase":
            raise TypeError("linter has no category!")
            
        if hasattr(cls,"category") and cls.category not in global_registered_linters:
            global_registered_linters[cls.category] = {}
        
        
        if hasattr(cls,"linter_name"):
            ln = cls.linter_name
            if ln not in global_registered_linters[cls.category]:
                global_registered_linters[cls.category][ln] = cls
        
        super(RegisterLintersMeta,cls).__init__(name,bases,dct)
    
    
class LinterBase(with_metaclass(RegisterLintersMeta,object)):
    def __init__(self,conanfile,output):
        self._conanfile = conanfile
        self._output = output
    
    
class ExportLinterBase(LinterBase):
    category = "export"

class InstallLinterBase(LinterBase):
    category = "install"
