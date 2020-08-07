#!/usr/bin/python3

import apt_pkg
import multiprocessing as mp
import pprint
import re
import requests
import requests_cache
import subprocess

def split_version(version):
    sub_versions = version.split('.')
    major = sub_versions[0]
    sub_minor = "0"
    minor = "0"
    if len(sub_versions) > 1:
        minor = sub_versions[1]
        if len(sub_versions) > 2:
            sub_minor = sub_versions[2]
    return major,minor,sub_minor

def numeric_version(version):
    major,minor,subminor = split_version(version)

    re_version = re.compile(r'(\w)?(?P<vers>\d+)(?:-(?P<label>[^-]*)(-(.*)))?')

    m = re_version.match(major)
    numeric = int(m.group("vers"))
    numeric *= 1000

    m = re_version.match(minor)
    numeric += int(m.group("vers"))
    numeric *= 1000
    if m.group("label") and m.group("label").startswith("rc"):
        rc = m.group("label").lstrip("rc")
        numeric += -500 + int(rc)

    m = re_version.match(subminor)
    numeric = numeric + int(m.group("vers"))

    return numeric

class LinuxKernel:
    """A Kernel on mainline"""

    def __init__(self, version, arch, url):
        self.url = url
        self.arch = arch
        self.valid = False
        self.version = version
        self.rc = False
        if version.find("rc"):
            self.rc = True
        self.numeric_version = numeric_version(version)

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

    def __iter__(self):
        return LinuxKernelsIterator(self)

    def init(self, min_version="v4.0"):
        # Grab the main page
        numeric_min_version = numeric_version(min_version)

        with requests_cache.disabled():
            r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

        re_index = re.compile(r'<a href="(v[a-zA-Z0-9\-._]+\/)">([a-zA-Z0-9\-._]+)\/<\/a>')

        for line in re_index.findall(r.text):
            version = line[1]
            if numeric_version(version) < numeric_min_version:
                continue

            kernel = LinuxKernel(version=line[1],
                                 arch=self.arch,
                                 url=r.url + line[0])
            try:
                kernel.init()
            except LookupError:
                continue

            kernel.installed = kernel.deb_version in self.installed
            kernel.running = kernel.deb_version == self.running_kernel
            self.kernels.append(kernel)
            print(".", end="", flush=True)

    def version(self, version):
        for kernel in kernels:
            if kernel.version == version:
                return kernel

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
