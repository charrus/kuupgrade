#!/usr/bin/python3

import apt_pkg
import os.path
import re
import requests
import shelve
import subprocess
import tempfile

# Parse the main page for links to versions
re_index = re.compile(r'<a href="(v[a-zA-Z0-9\-._]+\/)">([a-zA-Z0-9\-._]+)\/<\/a>')

# Extract all the links in the version page
re_urls = re.compile(r'<a href="[a-zA-Z0-9\-._\/]+">[a-zA-Z0-9\-._\/]+\.deb<\/a>')

# Extract a single package parts
re_all = re.compile(r'<a href="(?P<uri>[a-zA-Z0-9\-._/]+)">'+
                    r'(?P<dir>[a-z0-9]+/)?'+
                    r'(?P<filename>'+
                        r'(?P<package>[a-zA-Z0-9\-.]+)_'+
                        r'(?P<version>[a-zA-Z0-9\-.\/]+)_'+
                        r'(?P<arch>[a-zA-Z0-9\-\/]+)\.deb'+
                    r')'+
                    r'</a>')

# Extract numeric and optional text from versions
re_version = re.compile(r'[a-zA-Z]?(?P<vers>\d+)(?:-(?P<label>[^-]+))?')


def split_version(version):
    """
    Split the version into release, major, minor
    """

    sub_versions = version.split('.')
    release = sub_versions[0]
    m = re_version.match(release)
    release = m.group("vers")
    minor = "0"
    major = "0"
    if len(sub_versions) > 1:
        major = sub_versions[1]
        if len(sub_versions) > 2:
            minor = sub_versions[2]
    return release,major,minor

def numeric_version(version):
    """
    Calculate a numeric form of the version - roughly:

    release * 1000000 + major * 1000 + minor

    Release candidates subtract 500
    """

    release,major,minor = split_version(version)

    m = re_version.match(release)
    numeric = int(m.group("vers"))
    numeric *= 1000

    m = re_version.match(major)
    numeric += int(m.group("vers"))
    numeric *= 1000
    if m.group("label") and m.group("label").startswith("rc"):
        rc = m.group("label").lstrip("rc")
        numeric += -500 + int(rc)

    m = re_version.match(minor)
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
        (self.release, self.major, self.minor) = split_version(version)
        self.numeric_version = numeric_version(version)
        self.packages = []

    def __str__(self):
        return self.version

    def __eq__(self, other):
        return self.numeric_verion == other.numeric_version

    def __lt__(self, other):
        return self.numeric_version < other.numeric_version

    def init(self):
        # Grab the version page
        rver = requests.get(self.url)

        for debs in re_urls.findall(rver.text):
            m = re_all.match(debs)
            if not m:
                continue

            if m.group('arch') not in [self.arch, "all"]:
                continue

            package = {}

            package_name = m.group('package')
            # Flavour is the all alpha part of a version appended, for example
            # generic, lowlatency etc.
            flavour = package_name.split("-")[-1]
            if flavour.isalpha():
                package['flavour'] = flavour
            else:
                package['flavour'] = None
            package['url'] = rver.url + m.group('uri')
            package['arch'] = m.group('arch')
            package['version'] = m.group('version')
            package['dir'] = m.group('dir')
            package['filename'] = m.group('filename')
            package['package'] = m.group('package')
            self.packages.append(package)
            self.dpkg_version = m.group('version')

        if not self.packages:
            raise LookupError("Unable to find any versions")


    def install(self, flavour="generic", dryrun=False):
        """Install the packages for this version
           flavour can be lowlatency, generic etc"""

        with tempfile.TemporaryDirectory() as tmpdir:
            files_to_install = []

            for package in self.packages:
                if package['flavour'] and package['flavour'] != flavour:
                    continue
                filename = os.path.join(tmpdir,package['filename'])
                print("Downloading "+package['url'])
                r = requests.get(package['url'])
                with open(filename, "wb") as f:
                    f.write(r.content)
                files_to_install.append(filename)

            command = ['sudo', 'apt-get', 'install'] + files_to_install
            print("Running: "+" ".join(command))
            if not dryrun:
                subprocess.run(command)

    def remove(self, flavour="generic", dryrun=False):
        """Remove the packages for this version
           flavour can be lowlatency, generic etc"""

        packages_to_rm = []

        for package in self.packages:
            pkgflavour = package['flavour']
            if pkgflavour and pkgflavour != flavour:
                continue
            packages_to_rm.append(package['package'])

        command = ['sudo', 'apt-get', 'remove'] + packages_to_rm
        print("Running: "+" ".join(command))
        if not dryrun:
            subprocess.run(command)

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

    def __iter__(self):
        return LinuxKernelsIterator(self)

    def init(self, min_version="v4.0", release_candidates=False):
        with shelve.open('LinuxKernels') as d:
            cache_version = "1.3"
            cache_valid = False

            if 'cache_version' in d and d['cache_version'] == cache_version:
                cache_valid = True
            else:
                d['cache_version'] = cache_version
                print("Rebuilding cache")

            # Grab the main page
            numeric_min_version = numeric_version(min_version)

            r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

            for line in re_index.findall(r.text):
                version = line[1]
                if numeric_version(version) < numeric_min_version:
                    continue

                if cache_valid and version in d:
                    kernel = d[version]
                else:
                    kernel = LinuxKernel(version=version,
                                         arch=self.arch,
                                         url=r.url + line[0])
                    try:
                        kernel.init()
                    except LookupError:
                        continue

                    kernel.installed = kernel.dpkg_version in self.installed
                    kernel.running = kernel.dpkg_version == self.running_kernel
                    d[version] = kernel

                self.kernels.append(kernel)

    def version(self, version):
        for kernel in self.kernels:
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
        self.packages = []

        result = subprocess.run(['dpkg', '-l'], stdout=subprocess.PIPE)

        for dpkg in result.stdout.decode().splitlines():
            fields = dpkg.split()
            if len(fields) < 5:
                continue
            if fields[0] != 'ii':
                continue
            self.packages.append({ 'name': fields[1], 'version': fields[2]})

    def get_versions(self, name):
        versions = []
        for package in self.packages:
            if package['name'].startswith(name):
                versions.append(package['version'])

        return versions
