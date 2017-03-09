if not exist "C:\mingw64" appveyor DownloadFile "https://s3-eu-west-1.amazonaws.com/downloads.conan.io/x86_64-6.3.0-release-posix-sjlj-rt_v5-rev1.7z"
if not exist "C:\mingw64" 7z x x86_64-6.3.0-release-posix-sjlj-rt_v5-rev1.7z -oc:\
SET PATH=%PYTHON%;%PYTHON%\\Scripts;C:\\mingw64\\bin;%PATH%
SET PYTHONPATH=%PYTHONPATH%;%CD%
SET CONAN_LOGGING_LEVEL=10
SET CONAN_COMPILER=Visual Studio
SET CONAN_COMPILER_VERSION=12
%PYTHON%/Scripts/pip.exe install -r conans/requirements.txt
%PYTHON%/Scripts/pip.exe install -r conans/requirements_dev.txt
%PYTHON%/Scripts/pip.exe install -r conans/requirements_server.txt