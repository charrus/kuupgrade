#!/usr/bin/python3

import apt_pkg
import os.path
from os import getenv
import re
import requests
import shelve
import subprocess
import tempfile

# Parse the main page for links to versions
re_index = re.compile(r'<a href="(v[a-zA-Z0-9\-._]+\/)">' +
                      r'([a-zA-Z0-9\-._]+)\/<\/a>')

# Extract all the links in the version page
re_urls = re.compile(r'<a href="[a-zA-Z0-9\-._\/]+">' +
                     r'[a-zA-Z0-9\-._\/]+\.deb<\/a>')

# Extract a single package parts
re_all = re.compile(r'<a href="(?P<uri>[a-zA-Z0-9\-._/]+)">' +
                    r'(?P<dir>[a-z0-9]+/)?' +
                    r'(?P<filename>' +
                    r'(?P<package>[a-zA-Z0-9\-.]+)_' +
                    r'(?P<version>[a-zA-Z0-9\-.\/]+)_' +
                    r'(?P<arch>[a-zA-Z0-9\-\/]+)\.deb' +
                    r')' +
                    r'</a>')

# Extract numeric and optional text from versions
re_version = re.compile(r'[a-zA-Z]?(?P<vers>\d+)(?:-(?P<label>[^-]+))?')


# Helper functions to deal with kernel versions used by the site - i.e. v4.7.9
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
    return release, major, minor


def numeric_version(version):
    """
    Calculate a numeric form of the version - roughly:

    release * 1000000 + major * 1000 + minor

    Release candidates subtract 500
    """

    release, major, minor = split_version(version)

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
        # Populate when we can
        self.url = url
        self.arch = arch
        self.valid = False
        self.version = version
        self.rc = False
        (self.release, self.major, self.minor) = split_version(version)
        if "rc" in self.major:
            self.rc = True
        self.numeric_version = numeric_version(version)
        self.packages = []
        self.kern_versions = []

    def __str__(self):
        return self.version

    def __eq__(self, other):
        return self.numeric_verion == other.numeric_version

    def __lt__(self, other):
        return self.numeric_version < other.numeric_version

    def init(self):
        # Get more detailed info by parsing the version's page
        rver = requests.get(self.url)

        self.dpkg_version = None

        # Get all <a href='s
        for debs in re_urls.findall(rver.text):
            # Parse the ones that are dpkgs
            m = re_all.match(debs)
            if not m:
                continue

            # Skip if it's the wrong architecture
            if m.group('arch') not in [self.arch, "all"]:
                continue

            # This extracts details about the package
            # eg (with the full url truncated to make it clearer).
            # url: amd64/linux-image-unsigned-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
            #                                               ^ flvr^ 
            #            ^------------ package -------------------^ ^------ version ---------^ ^arc^
            #      ^dir^ ^-----------------------  filename  ------------------------------------------^
            # gives us:
            # filename: linux-image-unsigned-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
            # package: linux-image-unsigned-5.6.19-050619-generic
            # version: 5.6.19-050619.202006171132
            # flavour: generic (flvr above)
            # arch: amd64      (arc above)
            # dir: amd64/
            package = {}

            package_name = m.group('package')
            # Flavour is the all alpha part of a version appended, for example
            # generic, lowlatency etc.
            flavour = package_name.split("-")[-1]
            if flavour.isalpha():
                package['flavour'] = flavour
            else:
                package['flavour'] = "all"
            package['url'] = rver.url + m.group('uri')
            package['arch'] = m.group('arch')
            package['version'] = m.group('version')
            package['dir'] = m.group('dir')
            package['filename'] = m.group('filename')
            package['package'] = m.group('package')
            self.packages.append(package)

            # If this is one of the linux-image packes, then record both
            # the package and kernel version (so it matches uname -r)
            # linux-image is used as this will have the flavour
            # embedded in the package name. Note we're setting these at the
            # kernel level, not per package as above.
            # eg.
            # filename: linux-image-unsigned-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
            #                                ^--- kern_version --^ ^----- dpkg_version -----^
            #           ^------------ package -------------------^ ^------ version ---------^ ^arc^
            # gives us:
            # dpkg_version: 5.6.19-050619.202006171132 (from the package version)
            # kern_version: 5.6.19-050619-generic      (from the package name)
            if package['package'].startswith("linux-image"):
                self.kern_versions.append("-".join(m.group('package').split("-")[-3:]))
                if not self.dpkg_version:
                    self.dpkg_version = m.group('version')

        # If there are no packages lets kill ourselves now
        # If no dpkg version was extracted, this means we could
        # only fine the all arch ones - nothign for our arch.
        if not self.packages or not self.dpkg_version:
            raise LookupError("Unable to find any versions")

    def install(self, flavour="generic", dryrun=False):
        """Install the packages for this version
           flavour can be lowlatency, generic etc"""

        # Create a tempory directory, download the required dpkg's and then
        # install them if not dryrun mode
        with tempfile.TemporaryDirectory() as tmpdir:
            files_to_install = []

            for package in self.packages:
                if package['flavour'] in [self.flavour, "all"]:
                    filename = os.path.join(tmpdir, package['filename'])
                    print(f"Downloading {package['url']}")
                    r = requests.get(package['url'])
                    with open(filename, "wb") as f:
                        f.write(r.content)
                    files_to_install.append(filename)

            command = ['sudo', 'apt-get', 'install'] + files_to_install
            print(f"Running: {join(command)}")
            if not dryrun:
                subprocess.run(command)

    def remove(self, flavour="generic", dryrun=False):
        """Remove the packages for this version
           flavour can be lowlatency, generic etc"""

        packages_to_rm = []

        # Treating mainline as the source for packages, this will only remove
        # ones installed with this or similar tools. Standard & HWE are outside
        # the scope. Currently this is the same list that would be installed,
        # but perhaps it should be more promiscuous - remove i386 & lowlatency
        for package in self.packages:
            if package['flavour'] in [self.flavour, "all"]:
                packages_to_rm.append(package['package'])

        command = ['sudo', 'apt-get', 'remove'] + packages_to_rm
        print(f"Running: {join(command)}")
        if not dryrun:
            subprocess.run(command)


class LinuxKernels:
    """All Kernel on mainline"""

    URI_KERNEL_UBUNTU_MAINLINE = 'http://kernel.ubuntu.com/~kernel-ppa/mainline/'
    NUM_WORKERS = 16

    def __init__(self):
        self.kernels = []

        # Get our architecture: amd64/armv6/sparc
        apt_pkg.init()
        self.arch = apt_pkg.get_architectures()[0]

        # Get the list of installed kernels
        pkg_list = PackageList()
        self.installed = pkg_list.get_versions('linux-image')

        # Get the running kernel
        result = subprocess.check_output(['uname', '-r'])
        self.running_kernel = result.decode().rstrip()

    def __iter__(self):
        return LinuxKernelsIterator(self)

    def init(self, min_version="v4.0", release_candidates=False):
        """ Do the heavy lifting of init - parse and cache all the pages """

        cache_file = os.path.join(getenv("HOME"), ".LinuxKernels.cache")
        with shelve.open(cache_file) as cache:
            cache_version = "1.11"
            cache_valid = False

            # Rebuild the cache if the version above is changed - this version
            # should reflect only changes in the LinuxKenrel attributes
            # introduced with a code change, or fixing incorrect values
            # down to bugs
            if 'cache_version' in cache and cache['cache_version'] == cache_version:
                cache_valid = True
            else:
                print("Rebuilding cache")
                # Format has changed - so delete the cache version - from now
                # on it'll be a miss-mash. Probably best just remove the whole
                # thing tbh
                del cache['cache_version']

            # Convert the minimum version into a sortable value
            numeric_min_version = numeric_version(min_version)

            # Grab the main page
            r = requests.get(self.URI_KERNEL_UBUNTU_MAINLINE)

            # Just go through all the <a href's - skip if we're
            # not interested, load it from cache, or scrape if it's
            # not there
            for line in re_index.findall(r.text):
                version = line[1]
                if numeric_version(version) < numeric_min_version:
                    continue

                if cache_valid and version in cache:
                    kernel = cache[version]
                else:
                    kernel = LinuxKernel(version=version,
                                         arch=self.arch,
                                         url=r.url + line[0])
                    # This raises an exception if page cannot be parsed, or
                    # incorrect arch, flavour.
                    # This needs fixing and done in the constructor above
                    # ao the kernel object is never created in the first
                    # place.
                    # Currently it just skips adding it to the list of
                    # kernel versions
                    try:
                        kernel.init()
                    except LookupError:
                        continue

                    # Cache all that hard parsing work in LinuxKernel
                    cache[version] = kernel

                # kernels versions are idempotent - so cached above
                # If they're installed, or currently running is rather
                # more dynamic
                kernel.installed = kernel.dpkg_version in self.installed
                kernel.running = self.running_kernel in kernel.kern_versions
                self.kernels.append(kernel)

            # We're at the end of kernel versions - we're now at the same
            # cache version.
            cache['cache_version'] = cache_version

    def version(self, version):
        """ Return the kernel that matches the version listed on the site """
        for kernel in self.kernels:
            if kernel.version == version:
                return kernel


class LinuxKernelsIterator:
    """ Add an iterator for LinuxKernels to try that out """
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
            # Predictable output - let's make assumptions
            fields = dpkg.split()
            if len(fields) < 5:
                continue
            if fields[0] != 'ii':
                continue
            self.packages.append({'name': fields[1], 'version': fields[2]})

    def get_versions(self, name):
        """ Look for packages with a prefix - like linux-image """
        versions = []

        for package in self.packages:
            if package['name'].startswith(name):
                versions.append(package['version'])

        return versions
