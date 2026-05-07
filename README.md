# FSX492
This project implements a disk-based file system called FSX492, which is a simple derivation of the UNIX Fast File System (FFS). It uses the Linux FUSE (Filesystem in Userspace) interface to implement a file system as a user-space process.

# Setup
## Debian / Ubuntu
Clone the repo:
```bash
git clone https://github.com/tigritik/FSX492.git
```
Install the necessary packages for development:
```bash
sudo apt install libfuse3-dev pkg-config fuse3
```

# Acknowledgements
This project follows the [write up](https://cs492-stevens.github.io/assignments/project.html) by Professor Ryan Tsang (rtsang1@stevens.edu).
