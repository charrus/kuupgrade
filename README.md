# kuupgrade (Kernel Ubuntu Upgrade)

Work in progress.

So far:
* List available kernels
* Install a kernel
* Remove a kernl

Ultimately it'll have facilities to upgrade to the latest, or latest point release.

It's very alpha - so will change a lot.

Sample output (just a small section):

## Listing available kernels
```
$ kuupgrade --list

<snip>
v5.6.13              5.6.13-050613.202005141310                
v5.6.14              5.6.14-050614.202005200733                
v5.6.15              5.6.15-050615.202005271638                
v5.6.16              5.6.16-050616.202006030730                
v5.6.17              5.6.17-050617.202006071230                
v5.6.18              5.6.18-050618.202006101539                
v5.6.19              5.6.19-050619.202006171132                [Installed]
v5.6                 5.6.0-050600.202003292333                 
v5.7-rc1             5.7.0-050700rc1.202004122032              
v5.7-rc2             5.7.0-050700rc2.202004192230              
v5.7-rc3             5.7.0-050700rc3.202004262131              
v5.7-rc4             5.7.0-050700rc4.202005051752              
v5.7-rc5             5.7.0-050700rc5.202005101931              
v5.7-rc6             5.7.0-050700rc6.202005172030              
v5.7-rc7             5.7.0-050700rc7.202005242331              
v5.7.1               5.7.1-050701.202006071230                 
v5.7.2               5.7.2-050702.202006101934                 
<snip>
```

## Installing a kernel
```
$ ./kuupgrade.py --install v5.8
Downloading https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.8/amd64/linux-headers-5.8.0-050800-generic_5.8.0-050800.202008022230_amd64.deb
Downloading https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.8/amd64/linux-headers-5.8.0-050800_5.8.0-050800.202008022230_all.deb
Downloading https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.8/amd64/linux-image-unsigned-5.8.0-050800-generic_5.8.0-050800.202008022230_amd64.deb
Downloading https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.8/amd64/linux-modules-5.8.0-050800-generic_5.8.0-050800.202008022230_amd64.deb
Running: apt-get install /tmp/tmppcglp1s7/linux-headers-5.8.0-050800-generic_5.8.0-050800.202008022230_amd64.deb /tmp/tmppcglp1s7/linux-headers-5.8.0-050800_5.8.0-050800.202008022230_all.deb /tmp/tmppcglp1s7/linux-image-unsigned-5.8.0-050800-generic_5.8.0-050800.202008022230_amd64.deb /tmp/tmppcglp1s7/linux-modules-5.8.0-050800-generic_5.8.0-050800.202008022230_amd64.deb
```

## Removing a kernel
```
$ ./kuupgrade.py --remove v5.6.19
Running: apt-get remove linux-headers-5.6.19-050619-generic linux-headers-5.6.19-050619 linux-image-unsigned-5.6.19-050619-generic linux-modules-5.6.19-050619-generic
```

## Getting information on a kernel
```
$ ./kuupgrade.py --info v5.6.19
Release Candidate: False
Installed:         True
Running:           True
Dpkg version:      5.6.19-050619.202006171132
Kernel versions:   ['5.6.19-050619-generic', '5.6.19-050619-lowlatency']
Version tuple:     [ 5, 6, 19 ]
Version for cmp:   5006019
Package list:
    linux-headers-5.6.19-050619-generic
        arch:     amd64
        flavour:  generic
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-headers-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
        filename: linux-headers-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
    linux-headers-5.6.19-050619-lowlatency
        arch:     amd64
        flavour:  lowlatency
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-headers-5.6.19-050619-lowlatency_5.6.19-050619.202006171132_amd64.deb
        filename: linux-headers-5.6.19-050619-lowlatency_5.6.19-050619.202006171132_amd64.deb
    linux-headers-5.6.19-050619
        arch:     all
        flavour:  all
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-headers-5.6.19-050619_5.6.19-050619.202006171132_all.deb
        filename: linux-headers-5.6.19-050619_5.6.19-050619.202006171132_all.deb
    linux-image-unsigned-5.6.19-050619-generic
        arch:     amd64
        flavour:  generic
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-image-unsigned-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
        filename: linux-image-unsigned-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
    linux-image-unsigned-5.6.19-050619-lowlatency
        arch:     amd64
        flavour:  lowlatency
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-image-unsigned-5.6.19-050619-lowlatency_5.6.19-050619.202006171132_amd64.deb
        filename: linux-image-unsigned-5.6.19-050619-lowlatency_5.6.19-050619.202006171132_amd64.deb
    linux-modules-5.6.19-050619-generic
        arch:     amd64
        flavour:  generic
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-modules-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
        filename: linux-modules-5.6.19-050619-generic_5.6.19-050619.202006171132_amd64.deb
    linux-modules-5.6.19-050619-lowlatency
        arch:     amd64
        flavour:  lowlatency
        url:      https://kernel.ubuntu.com/~kernel-ppa/mainline/v5.6.19/amd64/linux-modules-5.6.19-050619-lowlatency_5.6.19-050619.202006171132_amd64.deb
        filename: linux-modules-5.6.19-050619-lowlatency_5.6.19-050619.202006171132_amd64.deb
```
