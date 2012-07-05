#!/usr/bin/env python

import errno
import fuse
import os
import stat
import sys
import threading
import time
from drive_service import DriveService

fuse.fuse_python_api = (0,2)

class DriveFuse(fuse.Fuse):
    def __init__(self, email, *args, **kw):
        super(DriveFuse, self).__init__(*args, **kw)
        self.drive_service = DriveService(email)
        self.codec = 'utf-8'

    # mknod, write, flush, unlink, mkdir, rmdir, rename, truncate
    def getattr(self, path):
        f = self.drive_service.lookup(unicode(path, self.codec))
        if f is None:
            return -errno.ENOENT

        st = fuse.Stat()
        if f.is_folder():
            st.st_mode = stat.S_IFDIR | 0744
            st.st_nlink = 1 + len(f.parents)
        else:
            st.st_mode = stat.S_IFREG | 0744
            st.st_nlink = len(f.parents)
        st.st_size = f.get_file_size()
        st.st_ino = 0
        st.st_dev = 0
        st.st_uid = os.getuid()
        st.st_gid = os.getgid()
        st.st_atime = f.get_access_date()
        st.st_mtime = f.get_modify_date()
        st.st_ctime = f.get_create_date()

        return st

    def readdir(self, path, offset):
        folder = self.drive_service.lookup(unicode(path, self.codec))
        if folder is None:
            yield -errno.ENOENT
        dirents = self.drive_service.readdir(folder)
        dirnames = [e.escaped_name for e in dirents]
        dirnames.extend([".", ".."])
        for n in dirnames:
            yield fuse.Direntry(n.encode(self.codec))

    def open(self, path, flags):
        pass
    def read(self, path, size = -1, offset = 0, fh = None):
        pass
    def release(self, path, flags, fh = None):
        pass

def main():
    """
    Mount the filesystem

    Returns 0 to indicate successful operation
    """

    usage = """
    Drive Fuse: Mounts Google Drive files on a local filesystem
    drive_fuse.py email mountpoint""" + fuse.Fuse.fusage

    email = sys.argv[1]
    mountpoint = sys.argv[2]

    dfs = DriveFuse(email, version = "%prog " + fuse.__version__,
		    usage = usage)
    dfs.parse(errex=1)
    dfs.main()
    return 0

if __name__ == '__main__':
    main()
