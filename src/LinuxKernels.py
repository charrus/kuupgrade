#!/usr/bin/python3

import apt_pkg
import multiprocessing as mp
import pprint
import re
import requests
import requests_cache
import subprocess

class LinuxKernel:
    """A Kernel on mainline"""

    def __init__(self, version, arch, url):
        self.url = url
        self.version = version
        self.arch = arch
        self.valid = False

    def init(self):
        REX = re.compile(r'<a href="([a-zA-Z0-9\-._\/]+)">([a-zA-Z0-9\-._\/]+)<\/a>')
        REX_HEADER_ALL = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*_all.deb')
        REX_HEADER = re.compile(r'[a-zA-Z0-9\-._\/]*linux-headers-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        REX_IMAGE = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-[a-zA-Z0-9.\-_]*generic_([a-zA-Z0-9.\-]*)_' + self.arch + r'.deb')
        REX_IMAGE_EXTRA = re.compile(r'[a-zA-Z0-9\-._\/]*linux-image-extra-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')
        REX_MODULES = re.compile(r'[a-zA-Z0-9\-._\/]*linux-modules-[a-zA-Z0-9.\-_]*generic_[a-zA-Z0-9.\-]*_' + self.arch + r'.deb')

        # Extract the urls for our architecture
        # Especially for the all debs, these are listed multiple times
        # per architecture, so use a dict to make them unique
        urls = {}

        # Grab the version page
        rver = requests.get(self.url)
        # The version can be extracted from the .deb filenames
        deb_versions = REX_IMAGE.findall(rver.text)
        # If we can't extract the version, then skip it
        if not deb_versions:
            raise LookupError("Unable to find any versions")

        self.deb_version = deb_versions[0]

        for debs in REX.findall(rver.text):
            # First group is the uri - so add the base url
            file_url = rver.url + debs[0]
            # Second group is the embedded version in the deb filename
            file_name = debs[1]

            if REX_HEADER.match(file_name):
                urls[file_url] = 1
            elif REX_HEADER_ALL.match(file_name):
                urls[file_url] = 1
            elif REX_IMAGE.match(file_name):
                urls[file_url] = 1
            elif REX_IMAGE_EXTRA.match(file_name):
                urls[file_url] = 1
            elif REX_MODULES.match(file_name):
                urls[file_url] = 1
            else:
                continue

        self.urls = list(urls.keys())
        self.valid = True

    def __str__(self):
        return self.version

class LinuxKernels:
    """All Kernel on mainline"""

    URI_KERNEL_UBUNTU_MAINLINE = 'http://kernel.ubuntu.com/~kernel-ppa/mainline/'
    NUM_WORKERS = 16

    def __init__(self):
        self.kernels = []

        REX_INDEX = re.compile(r'<a href="(v[a-zA-Z0-9\-._]+\/)">([a-zA-Z0-9\-._]+)\/<\/a>')

        # Get our architecture
        apt_pkg.init()
        self.arch = apt_pkg.get_architectures()[0]

        # Get the list of installed kernels
        pkg_list = PackageList()
        self.installed = pkg_list.get_versions('linux-image')

        # Get the running kernel
        result = subprocess.run(['uname', '-r'], stdout=subprocess.PIPE)
        self.running_kernel = result.stdout.decode()

        # Setup the cache
        requests_cache.install_cache('kuupgrade')

        # Grab the main page
        with requests_cache.disabled():
            r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

            for line in REX_INDEX.findall(r.text):
                kernel = LinuxKernel(version=line[1],
                                     arch=self.arch,
                                     url=r.url + line[0])
                self.kernels.append(kernel)

    def __iter__(self):
        return LinuxKernelsIterator(self)

    def init(self):
        # Create a queue to submit requests for each version
        self.query_queue = mp.Queue()
        self.result_queue = mp.Queue()

        # Attach a process to each worker and start it
        self.workers = [
            mp.Process(
                target=self._add_version_worker, args=(self.query_queue,self.result_queue)
            )
            for _ in range(self.NUM_WORKERS)
        ]
        for worker in self.workers:
            worker.start()

        # Iterate through all the versions and add them to the queue
        for kernel in self.kernels:
            self.query_queue.put(kernel)

        # Stop all the workers
        for _ in range(self.NUM_WORKERS):
            self.query_queue.put('STOP')

        remaining = self.NUM_WORKERS

        while True:
            kernel = self.result_queue.get()
            if kernel == 'STOP':
                remaining -= 1
                if remaining == 0:
                    break
                else:
                    continue
            kernel.valid = True
        
    def add_version(self, kernel):
        kernel.init()
        kernel.installed = kernel.deb_version in self.installed
        kernel.running = kernel.deb_version == self.running_kernel

    def _add_version_worker(self, query_queue,result_queue):
        while True:
            kernel = query_queue.get()
            if kernel == 'STOP':
                self.result_queue.put('STOP')
                break

            try:
                self.add_version(kernel)
            except LookupError:
                kernel.valid = False
                continue;

            self.result_queue.put(kernel)

class LinuxKernelsIterator:
    def __init__(self, kernels):
        self._kernels = kernels
        self._index = 0

    def __next__(self):
        if self._index < len(self._kernels.kernels):
            kernel = self._kernels.kernels[self._index]
            self._index += 1
            return kernel

        raise StopIteration

class PackageList:
    """ Represents a list of installed packages """

    def __init__(self):
        self.packages = self.installed_packages()

    def installed_packages(self):
        packages = {}
        result = subprocess.run(['dpkg', '-l'], stdout=subprocess.PIPE)

        for dpkg in result.stdout.decode('utf-8').splitlines():
            fields = dpkg.split()
            if len(fields) < 5:
                continue
            status = fields[0]
            name = fields[1]
            version = fields[2]
            if status != 'ii':
                continue
            pkg_id = name + '|' + version
            packages[pkg_id] = { 'name': name, 'version': version }

        return packages

    def get_versions(self, name):
        versions = []
        for pkg_id in self.packages.keys():
            if pkg_id.startswith(name):
                versions.append(self.packages[pkg_id]['version'])
        return versions
