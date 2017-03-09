SET PATH=%PYTHON%;%PYTHON%\\Scripts;C:\\mingw64\\bin;%PATH%
SET PYTHONPATH=%PYTHONPATH%;%CD%
SET CONAN_LOGGING_LEVEL=10
SET CONAN_COMPILER=Visual Studio
SET CONAN_COMPILER_VERSION=12
%PYTHON%/Scripts/pip.exe install -r conans/requirements.txt
%PYTHON%/Scripts/pip.exe install -r conans/requirements_dev.txt
%PYTHON%/Scripts/pip.exe install -r conans/requirements_server.txt