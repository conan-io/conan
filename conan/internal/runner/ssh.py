from pathlib import Path
from typing import Iterable
import fnmatch
import pathlib
import tempfile

from conan.api.output import Color, ConanOutput
from conan.errors import ConanException
from conan.tools.scm import Version
from conan import conan_version

import os
from io import BytesIO
import sys

from conan.internal.runner.output import RunnerOutput

def ssh_info(msg, error=False):
    fg=Color.BRIGHT_MAGENTA
    if error:
        fg=Color.BRIGHT_RED
    ConanOutput().status('\n┌'+'─'*(2+len(msg))+'┐', fg=fg)
    ConanOutput().status(f'| {msg} |', fg=fg)
    ConanOutput().status('└'+'─'*(2+len(msg))+'┘\n', fg=fg)

class SSHRunner:

    def __init__(self, conan_api, command, host_profile, build_profile, args, raw_args):
        try:
            from paramiko.config import SSHConfig
            from paramiko.client import SSHClient
        except ImportError:
            raise ConanException(
                "Paramiko is required for SSH runner. If conan is installed in a virtual environment, try to install "
                "the 'paramiko' package, or consider installing conan package with extra requires 'conan[runners]'"
            )
        self.conan_api = conan_api
        self.command = command
        self.host_profile = host_profile
        self.build_profile = build_profile
        self.remote_host_profile = None
        self.remote_build_profile = None
        self.remote_python_command = None
        self.remote_create_dir = None
        self.remote_is_windows = None
        self.args = args
        self.raw_args = raw_args
        self.ssh_config = None
        self.remote_workspace = None
        self.remote_conan = None
        self.remote_conan_home = None
        if host_profile.runner.get('use_ssh_config', False):
            ssh_config_file = Path.home() / ".ssh" / "config"
            ssh_config = SSHConfig.from_file(open(ssh_config_file))

        hostname = host_profile.runner.get("host") # TODO: this one is required
        if ssh_config and ssh_config.lookup(hostname):
            hostname = ssh_config.lookup(hostname)['hostname']
        self.boostrap_conan = host_profile.runner.get('boostrap_conan', False)
        self.boostrap_conan_version = host_profile.runner.get('boostrap_conan_version', str(conan_version))

        # this self.client manages the main ssh connection
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.connect(hostname)
        self.output = ConanOutput()
        self.output.set_warnings_as_errors(True)
        self.runner_output = RunnerOutput(hostname)
        # This client manages just the sftp transfers
        # TODO: Integrate both client calls in one
        self.remote_conn = RemoteConnection(self.client, self.runner_output)


    def run(self, use_cache=True):
        ssh_info('Got to SSHRunner.run(), doing nothing')

        self.ensure_runner_environment()
        self.copy_working_conanfile_path()

        raw_args = self.raw_args
        raw_args[raw_args.index(self.args.path)] = self.remote_create_dir
        raw_args = " ".join(raw_args)

        _Path = pathlib.PureWindowsPath if self.remote_is_windows else pathlib.PurePath
        remote_json_output = _Path(self.remote_create_dir).joinpath("conan_create.json").as_posix()
        command = f"{self.remote_conan} create {raw_args} --format json > {remote_json_output}"

        ssh_info(f"Remote command: {command}")

        stdout, _ = self._run_command(command)
        first_line = True
        while not stdout.channel.exit_status_ready():
            line = stdout.channel.recv(1024)
            if first_line and self.remote_is_windows:
                # Avoid clearing and moving the cursor when the remote server is Windows
                # https://github.com/PowerShell/Win32-OpenSSH/issues/1738#issuecomment-789434169
                line = line.replace(b"\x1b[2J\x1b[m\x1b[H",b"")
            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()
            first_line = False

        if stdout.channel.recv_exit_status() == 0:
            self.update_local_cache(remote_json_output)

    def ensure_runner_environment(self):
        # Check python3 is available in remote host
        if self.remote_conn.run_command("python3 --version", "Checking python3 version").success:
            self.remote_python_command = "python3"
        else:
            result = self.remote_conn.run_command("python --version", "Checking python version")
            if result.success and "Python 3" in result.stdout:
                self.remote_python_command = "python"
            else:
                self.output.error("Unable to locate Python 3 executable in remote SSH environment")

        # Determine if remote host is Windows
        result = self.remote_conn.run_command(f'{self.remote_python_command} -c "import os; print(os.name)"', "Checking remote OS type")
        if not result.success:
            self.output.error("Unable to determine remote OS type")
        self.remote_is_windows = result.stdout == "nt"

        # Get remote user home folder
        result = self.remote_conn.run_command(f'{self.remote_python_command} -c "from pathlib import Path; print(Path.home())"', "Checking remote home folder")
        if not result.success:
            self.output.error("Unable to determine remote home user folder")
        home_folder = result.stdout

        # Expected remote paths
        remote_folder = Path(home_folder) / ".conan2remote"
        self.remote_workspace = remote_folder.as_posix().replace("\\", "/")
        remote_conan_home = Path(home_folder) / ".conan2remote" / "conanhome"
        remote_conan_home = remote_conan_home.as_posix().replace("\\", "/")
        self.remote_conan_home = remote_conan_home

        # Ensure remote folders exist
        for folder in [self.remote_workspace, self.remote_conan_home]:
            if not self.remote_conn.run_command(f'{self.remote_python_command} -c "import os; os.makedirs(\'{folder}\', exist_ok=True)"', f"Checking {folder} folder exists").success:
                self.output.error(f"Unable to create remote workfolder at {folder}: {result.stderr}")

        python_venv = remote_folder / "venv"
        conan_cmd = (python_venv / "Scripts" / "conan.exe" if self.remote_is_windows else python_venv / "bin" / "conan").as_posix()

        if self.boostrap_conan:
            self._ensure_conan_installed(python_venv, conan_cmd)

        self._create_remote_conan_wrapper(conan_cmd)

    def _ensure_conan_installed(self, python_venv, conan_cmd):
        if self.boostrap_conan_version.endswith("-dev"):
            self.output.error(f"Remote Conan bootstrap version ({self.boostrap_conan_version}) cannot be a development version, "
                               "please specify a valid version or URL")

        # Check if remote Conan executable exists, otherwise invoke pip inside venv
        has_remote_conan = self.remote_conn.check_file_exists(conan_cmd)
        python_cmd = (python_venv / "Scripts" / "python.exe" if self.remote_is_windows else python_venv / "bin" / "python").as_posix()
        if not has_remote_conan:
            result = self.remote_conn.run_command(f"{self.remote_python_command} -m venv {python_venv}", "Creating remote venv")
            if not result.success:
                self.output.error(f"Unable to create remote venv: {result.stderr}")
            self._install_conan_remotely(python_cmd)
        else:
            version = self.remote_conn.run_command(f"{conan_cmd} --version", "Checking conan version", verbose=True).stdout
            remote_conan_version = Version(version[version.rfind(" ")+1:])
            if remote_conan_version != self.boostrap_conan_version:
                self.output.verbose(f"Remote Conan version mismatch: {remote_conan_version} != {self.boostrap_conan_version}")
                self._install_conan_remotely(python_cmd)

    def _install_conan_remotely(self, python_command: str):
        is_url = self.boostrap_conan_version.startswith("https://")
        if is_url:
            result = self.remote_conn.run_command(
                f"{python_command} -m pip install {self.boostrap_conan_version}",
                f"Installing conan from URL {self.boostrap_conan_version}",
            )
        else:
            result = self.remote_conn.run_command(
                f"{python_command} -m pip install conan=={self.boostrap_conan_version}",
                f"Installing conan {self.boostrap_conan_version}",
            )
        if not result.success:
            self.output.error(f"Unable to install conan in venv: {result.stderr}")

    def _create_remote_conan_wrapper(self, conan_cmd: str):
        remote_env = {
            'CONAN_HOME': self.remote_conan_home,
            'CONAN_RUNNER_ENVIRONMENT': "1"
        }
        if self.remote_is_windows:
            # Wrapper script with environment variables preset
            env_lines = "\n".join([f"set {k}={v}" for k,v in remote_env.items()])
            conan_bat_contents = f"""@echo off\n{env_lines}\n{conan_cmd} %*\n"""
            conan_bat = self.remote_workspace + "/conan.bat"
            try:
                sftp = self.client.open_sftp()
                sftp.putfo(BytesIO(conan_bat_contents.encode()), conan_bat)
            except:
                raise ConanException("unable to set up Conan remote script")
            finally:
                sftp.close()

            self.remote_conan = conan_bat
        _, _stdout, _stderr = self.client.exec_command(f"{self.remote_conan} config home")
        ssh_info(f"Remote conan config home returned: {_stdout.read().decode().strip()}")
        _, _stdout, _stderr = self.client.exec_command(f"{self.remote_conan} profile detect --force")
        self._sync_conan_config()

    def _sync_conan_config(self):
        # Transfer conan config to remote
        self.remote_conn.put_dir(
            self.conan_api.config.home(),
            self.remote_conan_home,
            exclude_patterns=["p", ".conan.db", "*.pyc", "__pycache__", ".DS_Store", ".git"]
        )

    def copy_working_conanfile_path(self):
        resolved_path = Path(self.args.path).resolve()
        if resolved_path.is_file():
            resolved_path = resolved_path.parent

        if not resolved_path.is_dir():
            return ConanException("Error determining conanfile directory")

        # Create temporary destination directory
        temp_dir_create_cmd = f"""{self.remote_python_command} -c "import tempfile; print(tempfile.mkdtemp(dir='{self.remote_workspace}'))"""
        _, _stdout, _ = self.client.exec_command(temp_dir_create_cmd)
        if _stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to create remote temporary directory")
        self.remote_create_dir = _stdout.read().decode().strip().replace("\\", '/')

        # Copy current folder to destination using sftp
        # self.remote_conn.put_dir(resolved_path.as_posix(), self.remote_create_dir)
        _Path = pathlib.PureWindowsPath if self.remote_is_windows else pathlib.PurePath
        sftp = self.client.open_sftp()
        for root, dirs, files in os.walk(resolved_path.as_posix()):
            relative_root = Path(root).relative_to(resolved_path)
            for dir in dirs:
                    dst = _Path(self.remote_create_dir).joinpath(relative_root).joinpath(dir).as_posix()
                    sftp.mkdir(dst)
            for file in files:
                orig = os.path.join(root, file)
                dst = _Path(self.remote_create_dir).joinpath(relative_root).joinpath(file).as_posix()
                sftp.put(orig, dst)
        sftp.close()

    def _run_command(self, command):
        ''' Run a command in an SSH session.
            When requesting a pseudo-terminal from the server,
            ensure we pass width and height that matches the current
            terminal
        '''
        channel = self.client.get_transport().open_session()
        if sys.stdout.isatty():
            width, height = os.get_terminal_size()
            channel.get_pty(width=width, height=height)

        channel.exec_command(command)

        stdout = channel.makefile("r")
        stderr = channel.makefile("r")
        return stdout, stderr

    def update_local_cache(self, json_result):
        # ('conan list --graph=create.json --graph-binaries=build --format=json > pkglist.json'
        _Path = pathlib.PureWindowsPath if self.remote_is_windows else pathlib.PurePath
        pkg_list_json = _Path(self.remote_create_dir).joinpath("pkg_list.json").as_posix()
        pkg_list_command = f"{self.remote_conan} list --graph={json_result} --graph-binaries=build --format=json > {pkg_list_json}"
        _, stdout, _ = self.client.exec_command(pkg_list_command)
        if stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to generate remote package list")

        conan_cache_tgz = _Path(self.remote_create_dir).joinpath("cache.tgz").as_posix()
        cache_save_command = f"{self.remote_conan} cache save --list {pkg_list_json} --file {conan_cache_tgz}"
        _, stdout, _ = self.client.exec_command(cache_save_command)
        if stdout.channel.recv_exit_status() != 0:
            raise ConanException("Unable to save remote conan cache state")

        with tempfile.TemporaryDirectory() as tmp:
            local_cache_tgz = os.path.join(tmp, 'cache.tgz')
            self.remote_conn.get(conan_cache_tgz, local_cache_tgz)
            self.conan_api.cache.restore(local_cache_tgz)


class RemoteConnection:
    def __init__(self, client, runner_output: RunnerOutput):
        from paramiko.client import SSHClient
        self.client: SSHClient = client
        self.runner_output = runner_output

    def put(self, src: str, dst: str) -> None:
        try:
            sftp = self.client.open_sftp()
            sftp.put(src, dst)
            sftp.close()
        except IOError as e:
            self.runner_output.error(f"Unable to copy {src} to {dst}:\n{e}")

    def put_dir(self, src: str, dst: str, exclude_patterns: Iterable[str] = []) -> None:
        source_folder = Path(src)
        destination_folder = Path(dst)
        for item in source_folder.iterdir():
            dest_item = (destination_folder / item.name).as_posix()
            # Check if item matches any exclude pattern
            if any(fnmatch.fnmatch(item.name, pattern) for pattern in exclude_patterns):
                continue
            if item.is_file():
                self.runner_output.verbose(f"Copying file {item.as_posix()} to {dest_item}")
                self.put(item.as_posix(), dest_item)
            elif item.is_dir():
                self.runner_output.verbose(f"Copying directory {item.as_posix()} to {dest_item}")
                self.mkdir(dest_item, ignore_existing=True)
                self.put_dir(item.as_posix(), dest_item, exclude_patterns)

    def get(self, src: str, dst: str) -> None:
        try:
            sftp = self.client.open_sftp()
            sftp.get(src, dst)
            sftp.close()
        except IOError as e:
            self.runner_output.error(f"Unable to copy from remote {src} to {dst}:\n{e}")

    def mkdir(self, folder: str, ignore_existing=False) -> None:
        sftp = self.client.open_sftp()
        try:
            sftp.mkdir(folder)
        except IOError:
            if ignore_existing:
                pass
            else:
                raise
        finally:
            sftp.close()

    def check_file_exists(self, file: str) -> bool:
        try:
            sftp = self.client.open_sftp()
            sftp.stat(file)
            sftp.close()
            return True
        except FileNotFoundError:
            return False

    class RunResult:
        def __init__(self, success, stdout, stderr):
            self.success = success
            self.stdout = stdout
            self.stderr = stderr

    def run_command(self, command: str, friendly_command: str = "", verbose: bool = False) -> RunResult:
        _, stdout, stderr = self.client.exec_command(command)
        log = self.runner_output.status if verbose else self.runner_output.verbose
        log(f'{friendly_command}...', fg=Color.BLUE)
        self.runner_output.debug(f'$ {command}')
        result = RemoteConnection.RunResult(stdout.channel.recv_exit_status() == 0,
                                            stdout.read().decode().strip(),
                                            stderr.read().decode().strip())
        log(f"{result.stdout}")
        return result
