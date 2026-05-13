#!/usr/bin/env python3
import os
import subprocess
import threading
import time
import tempfile
import shutil
import signal
import sys

# -------- CONFIG --------
FUSE_BINARY = "fsx492"          # your compiled FS
FUSE_ARGS = ["-f", "-d", "-s"]  # run single threaded debug mode
MOUNT_TIMEOUT = 10              # seconds
# ------------------------


##############################################################################
# BEGIN TEST DEFINITIONS
##############################################################################

# define tests below by creating functions that are prefixed with "test_"


def test_basic(mountpoint):

    # TEST: directory listing

    print(f"[test] list {mountpoint}")
    entries = os.listdir(mountpoint)
    print(entries)
    assert "hello.txt" in entries, "readdir missing file"

    # TEST: file existence
    path = os.path.join(mountpoint, "hello.txt")
    print(f"[test] file existence: {path}")
    assert os.path.exists(path), "file missing"

    # TEST: read
    print(f"[test] read {path}")
    with open(path, "r") as f:
        data = f.read()
    assert "hello" in data, "unexpected file content"

    # TEST: partial read
    print(f"[test] partial read {path}")
    with open(path, "r") as f:
        f.seek(6)
        data = f.read()
    assert "world" in data, "partial read failed"

    # TEST: out of bounds read
    print(f"[test] out of bounds read {path}")
    with open(path, "r") as f:
        f.seek(30)
        data = f.read()
    assert len(data) == 0, "out of bounds read should return nothing"

    # TEST: stat
    print(f"[test] stat {path}")
    st = os.stat(path)
    assert st.st_size == len("hello world!\n"), "invalid file size"

    print("[test] passed basic")


def test_large_file(mountpoint):

    # TEST: large file copy
    src = "./data/gospels.txt"
    assert os.path.exists(src), "src not found: {}".format(src)

    dst = f"{mountpoint}/{os.path.basename(src)}"
    shutil.copy(src, dst)
    assert os.path.exists(dst), "copy failed: {} does not exist".format(dst)

    with open(src, 'rb') as f:
        srcdata = f.read()

    with open(dst, 'rb') as f:
        dstdata = f.read()

    assert len(srcdata) == len(dstdata), \
        "length check failed: {} (src) != {} (dst)".format(
            len(srcdata), len(dstdata))

    diff = -1
    for i in range(len(srcdata)):
        if srcdata[i] != dstdata[i]:
            diff = i
            break

    assert diff < 0, "data different @ {}:\nsrc: {}\ndst: {}".format(
        diff, srcdata[diff:diff+10], dstdata[diff:diff+10])

    print("[test] passed large file")


def test_subdirectory_file_ops(mountpoint):

    # TEST: create / remove files in subdir
    subdir = os.path.join(mountpoint, "subdir")

    print(f"[test] mkdir {subdir}")
    os.mkdir(subdir)

    filepath = os.path.join(subdir, "nested.txt")

    print(f"[test] create {filepath}")
    with open(filepath, "w") as f:
        f.write("nested data")

    assert os.path.exists(filepath), "nested file missing"

    print(f"[test] remove {filepath}")
    os.remove(filepath)

    assert not os.path.exists(filepath), "nested file still exists"

    print(f"[test] rmdir {subdir}")
    os.rmdir(subdir)

    assert not os.path.exists(subdir), "subdir still exists"

    print("[test] passed subdirectory file ops")


def test_many_directories(mountpoint):

    # TEST: create more than a blocks worth of directories
    block_size = 1024
    dirent_size = 32
    direntries_per_block = block_size // dirent_size
    # there are only 64 total inodes in the base image
    # yes I can create an image with more but I can't
    # guarantee the graders will use that image
    # so we will test 1.5 blocks worth of dirents
    count = int(1.5 * direntries_per_block) # 1.5 blocks worth

    print(f"[test] creating {count} directories")

    for i in range(count):
        path = os.path.join(mountpoint, f"dir_{i}")
        os.mkdir(path)

    entries = os.listdir(mountpoint)

    for i in range(count):
        assert f"dir_{i}" in entries, f"missing dir_{i}"

    print(f"[test] removing {count} directories")

    for i in range(count):
        path = os.path.join(mountpoint, f"dir_{i}")
        os.rmdir(path)

    entries = os.listdir(mountpoint)

    for i in range(count):
        assert f"dir_{i}" not in entries, f"dir_{i} still exists"

    print("[test] passed many directories")


def test_overwrite_file(mountpoint):

    # TEST: overwite file contents (O_TRUNC)
    path = os.path.join(mountpoint, "overwrite.txt")

    print(f"[test] initial write {path}")

    with open(path, "w") as f:
        f.write("abcdef")

    print(f"[test] overwrite {path}")

    with open(path, "w") as f:
        f.write("xyz")

    with open(path, "r") as f:
        data = f.read()

    assert data == "xyz", f"overwrite failed: got '{data}'"

    st = os.stat(path)
    assert st.st_size == 3, "file size not truncated"

    print("[test] passed overwrite file")


def test_append_mode(mountpoint):

    # TEST: append file contents (O_APPEND)
    path = os.path.join(mountpoint, "append.txt")

    with open(path, "w") as f:
        f.write("hello")

    with open(path, "a") as f:
        f.write(" world")

    with open(path, "r") as f:
        data = f.read()

    assert data == "hello world", f"append failed: got '{data}'"

    print("[test] passed append mode")


def test_middle_write(mountpoint):

    # TEST: writing to a middle of file (lseek)
    path = os.path.join(mountpoint, "middle.txt")

    print(f"[test] create {path}")

    with open(path, "w") as f:
        f.write("hello world")

    print(f"[test] overwrite middle of file")

    with open(path, "r+") as f:
        f.seek(6)
        f.write("FUSE")

    with open(path, "r") as f:
        data = f.read()

    assert data == "hello FUSEd", \
        f"middle write failed: got '{data}'"

    st = os.stat(path)

    assert st.st_size == len("hello FUSEd"), \
        "unexpected file size after middle write"

    print("[test] passed middle write")


def test_hard_links(mountpoint):

    # TEST: hard linking, link counts, inode comparison
    src = os.path.join(mountpoint, "original.txt")
    dst = os.path.join(mountpoint, "linked.txt")

    print(f"[test] create {src}")

    with open(src, "w") as f:
        f.write("hello")

    print(f"[test] create hard link {dst}")

    os.link(src, dst)

    st_src = os.stat(src)
    st_dst = os.stat(dst)

    # TEST: same inode
    assert st_src.st_ino == st_dst.st_ino, \
        "hard links should share inode"

    # TEST: link count increased
    assert st_src.st_nlink == 2, \
        f"expected 2 links, got {st_src.st_nlink}"

    # TEST: shared contents
    with open(dst, "r") as f:
        data = f.read()

    assert data == "hello", \
        "linked file contents incorrect"

    # TEST: content updates in both files
    with open(dst, "w") as f:
        f.write("hello world")
        f.flush()
        os.fsync(f.fileno())

    with open(src, "r") as f:
        datasrc = f.read()

    with open(dst, "r") as f:
        datadst = f.read()

    print(datadst)
    print(datasrc)
    assert datasrc == datadst == "hello world", \
        "linked file contents updated incorrectly"

    # TEST: remove link, decrement count. Poll bc of caching
    print(f"[test] unlink {dst}")
    os.remove(dst)
    st_src = os.stat(src)

    assert st_src.st_nlink == 1, \
        f"link count not decremented (got {st_src.st_nlink})"

    print("[test] passed hard links")


def test_timestamps(mountpoint):

    # TEST: access time modification
    path = os.path.join(mountpoint, "time.txt")

    with open(path, "w") as f:
        f.write("hello")

    st1 = os.stat(path)

    time.sleep(1)

    with open(path, "a") as f:
        f.write(" world")

    st2 = os.stat(path)

    assert st2.st_mtime > st1.st_mtime, "mtime not updated"

    time.sleep(1)

    with open(path, "r") as f:
        f.read()

    st3 = os.stat(path)

    assert st3.st_atime >= st2.st_atime, "atime not updated"

    print("[test] passed timestamps")


def test_chmod(mountpoint):

    # TEST: permission changes
    path = os.path.join(mountpoint, "perm.txt")

    with open(path, "w") as f:
        f.write("data")

    print(f"[test] chmod 600 {path}")

    os.chmod(path, 0o600)

    st = os.stat(path)

    mode = st.st_mode & 0o777

    assert mode == 0o600, f"chmod failed: got {oct(mode)}"

    print(f"[test] chmod 644 {path}")

    os.chmod(path, 0o644)

    st = os.stat(path)

    mode = st.st_mode & 0o777

    assert mode == 0o644, f"chmod failed: got {oct(mode)}"

    print("[test] passed chmod")


##############################################################################
# END TEST DEFINITIONS
##############################################################################

TESTS = {
    k[len("test_"):]: v for k, v in globals().items() if k.startswith('test_')
}


def reset_mount(mountpoint, fs_name=FUSE_BINARY):
    """reset fuse filesystem mountpoint after failure"""
    result = subprocess.run(
        ['mount'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False)

    if fs_name in result.stdout:
        subprocess.run(
            ['fusermount', '-u', mountpoint],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False)

    try:
        shutil.rmtree(mountpoint)
    except Exception:
        pass

    os.makedirs(mountpoint, exist_ok=True)

def is_mounted(mountpoint, fs_name=None):
    mountpoint = os.path.abspath(mountpoint)

    try:
        with open("/proc/self/mounts", "r") as f:
            lines = [line.strip() for line in f.readlines()]

        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue

            dev, mnt, fstype = parts[:3]

            if os.path.abspath(mnt) == mountpoint:
                if fs_name is None:
                    return True
                if fs_name in dev or fs_name in fstype:
                    return True
        return False
    except Exception:
        return False


def wait_for_mount(mountpoint, timeout=MOUNT_TIMEOUT):
    """Wait until mountpoint is ready by probing it."""
    start = time.time()
    while time.time() - start < timeout:
        if is_mounted(mountpoint, fs_name="fsx492"):
            return True
        time.sleep(0.1)
    return False


def run_filesystem(mountpoint, ready_event, stop_event, logfile="fsx492.log"):
    """Run the FUSE filesystem."""
    cmd = ['stdbuf', '-oL', '-eL'] + [f"./{FUSE_BINARY}"] + FUSE_ARGS + [mountpoint]

    # unmount file system if needed first
    reset_mount(mountpoint)

    log = open(logfile, 'w')
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait until mount is ready
    if wait_for_mount(mountpoint):
        print("[fs] mounted")
        ready_event.set()
    else:
        print("[fs] mount timeout")
        proc.terminate()
        return

    # Keep process alive until stop_event
    while not stop_event.is_set():
        if proc.poll() is not None:
            print("[fs] process exited early!")
            return
        time.sleep(0.2)

    log.close()
    print("[fs] shutting down...")
    proc.send_signal(signal.SIGINT)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_tests(test, mountpoint, ready_event, stop_event):
    """Run filesystem tests."""
    ready_event.wait()

    print(f"[test] starting test: {test}")

    try:
        TESTS[test](mountpoint)
    except AssertionError as e:
        print(f"[test] FAILED: {e}")
    finally:
        stop_event.set()


if __name__ == "__main__":
    DEFAULT_MOUNTPOINT = './testfs'
    DEFAULT_IMAGE = 'data/test.img'
    import argparse
    parser = argparse.ArgumentParser('test.py',
        description="test script for fsx492")
    parser.add_argument('test', type=str, default='basic',
        help=f"options: {','.join(TESTS.keys())}")
    parser.add_argument('--mountpoint', type=str, default=DEFAULT_MOUNTPOINT,
        help=f"the path to mount at (default {DEFAULT_MOUNTPOINT})")
    parser.add_argument('--img', type=str, default='data/test.img',
        help=("the path to the image file, which will be restored from backup "
            f"(default: {DEFAULT_IMAGE})"))

    args = parser.parse_args()

    mountpoint = args.mountpoint
    assert args.test in TESTS, "test not found: {}".format(args.test)
    assert callable(TESTS[args.test]), "not callable: {}".format(args.test)

    imgpath = args.img
    assert os.path.exists(imgpath), "file not found: {}".format(imgpath)
    imgbkp = f"{imgpath}.bkp"
    assert os.path.exists(imgbkp), "could not find backup: {}".format(imgbkp)

    print(f"[main] cwd: {os.getcwd()}")
    print(f"[main] mountpoint: {mountpoint}")
    print(f"[main] restoring {imgpath} from {imgbkp}")
    shutil.copy(imgbkp, imgpath)

    ready_event = threading.Event()
    stop_event = threading.Event()

    fs_thread = threading.Thread(
        target=run_filesystem,
        args=(mountpoint, ready_event, stop_event),
        daemon=True
    )

    test_thread = threading.Thread(
        target=run_tests,
        args=(args.test, mountpoint, ready_event, stop_event),
        daemon=True
    )

    fs_thread.start()
    test_thread.start()

    test_thread.join()
    stop_event.set()
    fs_thread.join()

    # Try to unmount (Linux)
    print("[main] unmounting...")
    subprocess.run(["fusermount", "-u", mountpoint],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

    shutil.rmtree(mountpoint)
    print("[main] done")


