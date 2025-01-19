from conan.api.subapi.new import NewAPI
from conan.internal.api.new.cmake_exe import cmake_exe_files
from conan.internal.api.new.cmake_lib import cmake_lib_files


conanws_yml = """\
editables:
  liba/0.1:
    path: liba
  libb/0.1:
    path: libb
  app1/0.1:
    path: app1
products:
- app1
"""

workspace_files = {"conanws.yml": conanws_yml}

for lib in ("liba", "libb"):
    definitions = {"name": lib}
    if lib == "libb":
        definitions["requires"] = ["liba/0.1"]
    elif lib == "libc":
        definitions["requires"] = ["libb/0.1"]
    files = NewAPI.render(cmake_lib_files, definitions)
    files = {f"{lib}/{k}": v for k, v in files.items()}
    workspace_files.update(files)


files = NewAPI.render(cmake_exe_files, definitions={"name": "app1", "requires": ["libb/0.1"]})
files = {f"app1/{k}": v for k, v in files.items()}
workspace_files.update(files)
