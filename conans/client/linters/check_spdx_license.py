# -*- coding: utf-8 -*-
from conans.client.linters.linters_base import ExportLinterBase
import spdx_lookup
import glob
import os




class CheckSPDXLicense(ExportLinterBase):
    linter_name = "check_spdx_license"
    
    def do_check(self):
        return self._check_license_id(self._conanfile.license)
        
    
    def _check_license_id(self,lic):
        match = spdx_lookup.by_id(lic)
        if match is None:
            self._output.error('License string: "%s" was not matched with a valid SPDX code!'
                               % lic)
            return False
        else:
            self._output.success("matched license id: %s" % lic)
            self._output.info("license name: %s" % match.name)
            self._output.info("OSI approved? %s" % str(match.osi_approved))
            
            return True
    
        
        
