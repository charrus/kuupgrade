#!/usr/bin/python3

import apt_pkg
import os.path
import re
import requests
import requests_cache
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
re_version = re.compile(r'(\w)?(?P<vers>\d+)(?:-(?P<label>[^-]*)(-(.*)))?')


def split_version(version):
    """
    Split the version into major, minor, subminor
    """

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
    """
    Calculate a numeric form of the version - roughly:

    major * 1000000 + minor * 1000 + subminor

    Release candidates subtract 500
    """

    major,minor,subminor = split_version(version)

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
            self.deb_version = m.group('version')

        if not self.packages:
            raise LookupError("Unable to find any versions")


    def install(self, flavour="generic", dryrun=False):
        """Install the packages for this version
           flavour can be lowlatency, generic etc"""

        with requests_cache.disabled():
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

        # Setup the cache
        requests_cache.install_cache('kuupgrade')

    def __iter__(self):
        return LinuxKernelsIterator(self)

    def init(self, min_version="v4.0"):
        # Grab the main page
        numeric_min_version = numeric_version(min_version)

        with requests_cache.disabled():
            r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

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
