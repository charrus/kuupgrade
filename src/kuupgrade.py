#!/usr/bin/python3

import argparse
import pprint

from LinuxKernels import LinuxKernels, numeric_version

parser = argparse.ArgumentParser(description='Upgrade ubuntu kernel')
parser.add_argument('--list', action='store_true',
                    help='List available kernels')
parser.add_argument('--dryrun', action='store_true', help='Dry run mode')
parser.add_argument('--install', help='Install kernel', metavar='version')
parser.add_argument('--remove', help='Remove kernel', metavar='version')
parser.add_argument('--info', help='Kernel info', metavar='version')
args = parser.parse_args()

if args.dryrun:
    print("Dry run set - nothing will be installed or removed")

kernels = LinuxKernels()
kernels.init()

if args.list:
    for kernel in kernels:
        running = ""
        installed = ""

        if kernel.running:
            running = "[Running]"
        if kernel.installed:
            installed = "[Installed]"
        version = kernel.version
        dpkg_version = kernel.dpkg_version

        print(f'{version:20} {dpkg_version:40} {running} {installed}')

if args.install:
    kernel = kernels.version(args.install)
    kernel.install(dryrun=args.dryrun)

if args.remove:
    kernel = kernels.version(args.remove)
    kernel.remove(dryrun=args.dryrun)

if args.info:
    kernel = kernels.version(args.info)
    print(f'Release Candidate: {kernel.rc}')
    print(f'Installed:         {kernel.installed}')
    print(f'Running:           {kernel.running}')
    print(f'Dpkg version:      {kernel.dpkg_version}')
    print(f'Version tuple:     {kernel.release}, {kernel.major}, ' +
          f'{kernel.minor}')
    print(f'Version for cmp:   {kernel.numeric_version}')
    pprint.pprint(kernel.packages)
