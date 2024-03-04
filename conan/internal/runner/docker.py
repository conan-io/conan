import os
import json
from io import BytesIO
import textwrap
import shutil
import docker

from conan.api.model import ListPattern
from conan.api.output import ConanOutput
from conan.api.conan_api import ConfigAPI


class DockerRunner:

    def __init__(self, conan_api, command, profile, args, raw_args):
        self.conan_api = conan_api
        self.args = args
        self.raw_args = raw_args
        self.docker_client = docker.from_env()
        self.docker_api = docker.APIClient()
        self.command = command
        self.dockerfile = str(profile.runner.get('dockerfile', ''))
        self.image = str(profile.runner.get('image', 'conanrunner'))
        self.suffix = profile.runner.get('suffix', args.profile_host[0] if args.profile_host else 'docker')
        self.remove = profile.runner.get('remove', True)
        self.cache = str(profile.runner.get('cache', 'clean'))
        self.runner_home = os.path.join(args.path, '.conanrunner')
        self.container = None

    def run(self, use_cache=True):
        """
        run conan inside a Docker continer
        """
        ConanOutput().info(msg=f'\nBuilding the Docker image: {self.image}')
        self.build_image()
        # Init docker python api
        name = None if self.remove else f'conan-runner-{self.suffix}'
        volumes, environment = self.create_runner_environment(use_cache)
        if name:
            ConanOutput().info(msg=f'\nRunning the Docker container: "{name}"\n')
        try:
            self.container = self.docker_client.containers.run(self.image,
                                                               "/bin/bash -c 'while true; do sleep 30; done;'",
                                                               name=name,
                                                               volumes=volumes,
                                                               environment=environment,
                                                               detach=True,
                                                               auto_remove=False)
            self.init_container(use_cache)
        except docker.errors.APIError as e:
            if self.remove:
                raise e
            self.container = docker_client.containers.get(name)
            self.container.start()

        # for line in container.attach(stdout=True, stream=True, logs=True):
        #     ConanOutput().info(line.decode('utf-8', errors='ignore').strip())
        self.run_command(' '.join([f'conan {self.command}'] + self.raw_args))
        # container.wait()
        self.update_local_cache(use_cache)
        self.container.stop()
        if self.remove:
            self.container.remove()

    def build_image(self):
        docker_build_logs = None
        if self.dockerfile:
            docker_build_logs = self.docker_api.build(path=self.dockerfile, tag=self.image)
        else:
            dockerfile = textwrap.dedent("""
                FROM ubuntu
                RUN apt update && apt upgrade -y
                RUN apt install -y build-essential
                RUN apt install -y python3-pip cmake git
                RUN cd /root && git clone https://github.com/davidsanfal/conan.git conan-io
                RUN cd /root/conan-io && pip install -e .
                """)

            docker_build_logs = self.docker_api.build(fileobj=BytesIO(dockerfile.encode('utf-8')),
                                                      nocache=False,
                                                      tag=self.image)
        for chunk in docker_build_logs:
            for line in chunk.decode("utf-8").split('\r\n'):
                if line:
                    stream = json.loads(line).get('stream')
                    if stream:
                        ConanOutput().info(stream.strip())

    def run_command(self, command):
        try:
            ConanOutput().info(msg=f'RUNNING: "/bin/bash -c \'{command}\'"')
            exec_stream = self.container.exec_run(f'/bin/bash -c \'{command}\'', stream=True, tty=True)
            while True:
                print(next(exec_stream.output).decode('utf-8', errors='ignore').strip())
        except StopIteration:
            pass

    def create_runner_environment(self, use_cache):
        volumes = {self.args.path: {'bind': self.args.path, 'mode': 'rw'}}
        environment = {'CONAN_REMOTE_ENVIRONMNET': '1'}
        if use_cache:
            if self.cache == 'shared':
                volumes[ConfigAPI(self.conan_api).home()] = {'bind': '/root/.conan2', 'mode': 'rw'}
            if self.cache in ['clean', 'copy']:
                shutil.rmtree(self.runner_home, ignore_errors=True)
                os.mkdir(self.runner_home)
                shutil.copytree(os.path.join(ConfigAPI(self.conan_api).home(), 'profiles'), os.path.join(self.runner_home, 'profiles'))
                if self.cache == 'copy':
                    tgz_path = os.path.join(self.runner_home, 'conan_cache_save.tgz')
                    self.conan_api.cache.save(self.conan_api.list.select(ListPattern("*")), tgz_path)
        return volumes, environment

    def init_container(self, use_cache):
        if use_cache:
            if self.cache in ['clean', 'copy']:
                self.run_command('mkdir -p ${HOME}/.conan2/profiles')
                self.run_command('cp -r '+self.args.path+'/.conanrunner/profiles/. ${HOME}/.conan2/profiles/.')
                if self.cache == 'copy':
                    self.run_command('conan cache restore '+self.args.path+'/.conanrunner/conan_cache_save.tgz')
                self.run_command('mkdir -p ${HOME}/.conan2/profiles')
                self.run_command('cp -r '+self.args.path+'/.conanrunner/profiles/. -r ${HOME}/.conan2/profiles/.')

    def update_local_cache(self, use_cache):
        if use_cache and self.cache in ['copy', 'clean']:
            self.run_command('conan cache save "*" --file '+self.args.path+'/.conanrunner/conan_cache_docker.tgz')
            tgz_path = os.path.join(self.runner_home, 'conan_cache_docker.tgz')
            package_list = self.conan_api.cache.restore(tgz_path)
