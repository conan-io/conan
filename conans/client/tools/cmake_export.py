import os
from itertools import chain

def _patch_file(cmake,conanfile,fname):
    with open(fname,"r") as f:
        filestr = f.read()
        
    pf = cmake.definitions.get("CMAKE_INSTALL_PREFIX")
    replstr = "${CONAN_%s_ROOT}" % conanfile.name.upper()
    
    newfilestr = filestr.replace(pf,replstr)
    with open(fname,"w") as f:
        f.write(newfilestr)
        
def patch_cmake_config_abs_paths(cmake):
    """
    changes references to the absolute path of the installed package in 
    exported cmake config files to the appropriate conan variable. This makes 
    most (sensible) cmake config files portable.
    
    For example, if a package foo installs a file called "fooConfig.cmake" to 
    be used by cmake's find_package method, normally this file will contain 
    absolute paths to the installed package folder, for example it will contain
    a line such as:
        
        SET(Foo_INSTALL_DIR /home/developer/.conan/data/Foo/1.0.0/...)
        
    This will cause cmake find_package() method to fail when someone else 
    installs the package via conan. 
    
    This function will replace such mentions to
        
        SET(Foo_INSTALL_DIR ${CONAN_FOO_ROOT})
        
    which is a variable that is set by conanbuildinfo.cmake, so that find_package()
    now correctly works on this conan package. 
    
    If the install() method of the CMake object in the conan file is used, this
    function should be called _after_ that invocation. For example:
        
        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
            cmake.install()
            
            patch_cmake_config_abs_paths(cmake)
    
    
    :param cmake: a CMake object 
    """
    conanfile = cmake._conanfile
    allwalk = chain(os.walk(conanfile.build_folder),os.walk(conanfile.package_folder))
    filematches = []
    for root,dirs,files in allwalk:
        matches = [os.path.splitext(_)[1] == ".cmake" for _ in files]
        filematches.extend(os.path.join(root,files[_]) for _ in range(len(matches)) if matches[_])
    
    for fname in filematches:
        _patch_file(cmake,conanfile,fname)