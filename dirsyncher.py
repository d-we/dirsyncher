#! /usr/bin/env python3


import os
import shutil
import time
import tempfile
import argparse
import subprocess
import hashlib
import random
import string

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    VERBOSE = '\033[96m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def copy_symlink(src, dest):
    link_target = os.readlink(src)
    if os.path.isabs(link_target):
        print(f"{bcolors.FAIL}[!] Tool does not handle absolute symlinks! Aborting!{bcolors.ENDC}")
        exit(1)
    os.symlink(link_target, dest)
    

def hash_file(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as fd:
        for chunk in iter(lambda: fd.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
    

def is_same_file(file_a, file_b):
    try:
        # of both are symlinks we need to compare the target
        if os.path.islink(file_a) and os.path.islink(file_b):
            return os.readlink(file_a) == os.readlink(file_b)

        # if only one is a symlink we return false
        if os.path.islink(file_a) and not os.path.islink(file_b):
            return False
        if os.path.islink(file_b) and not os.path.islink(file_a):
            return False

        # if boths are actual files we compare the hash
        return hash_file(file_a) == hash_file(file_b)
    except FileNotFoundError:
        return False

def is_excluded(exclude_directories, file):
    for exclude in exclude_directories:
        if exclude in file:
            return True
    return False

# this copies the directory while leaving the additional files 
# that are already in the dest in place
def copy_dir(source_dir, dest_dir, exclude_directories = [], verbose = False):
    if not os.path.exists(dest_dir):
        os.mkdir(dest_dir)

    for file in os.listdir(source_dir):
        source = source_dir + "/" + file
        dest = dest_dir + "/" + file
        if is_excluded(exclude_directories, source):
            print(f"{bcolors.VERBOSE}[*] Skipping {source}...{bcolors.ENDC}")
            continue
        if os.path.isdir(source):
            copy_dir(source, dest, exclude_directories)
        else:
            #try:
            if not is_same_file(source, dest):
                if os.path.islink(source):
                    copy_symlink(source, dest)
                else:
                        shutil.copy(source, dest)
            else:
                if verbose:
                    print(f"{bcolors.VERBOSE}[*] Same already: {source}.{bcolors.ENDC}")

            #except FileNotFoundError:
            #    print(f"{bcolors.WARNING}[!] Could not copy {source}!{bcolors.ENDC}")

class FileSyncher(FileSystemEventHandler):

    def __init__(self, local_path, remote_path, verbose = False, exclude_directories = []):
        super().__init__()
        self.local_path = local_path
        self.remote_path = remote_path
        self.verbose = verbose
        self.exclude_directories = exclude_directories

    def is_excluded(self, file):
        return is_excluded(self.exclude_directories, file)
        
    def get_relative_path(self, remote_path):
        return os.path.relpath(remote_path, self.local_path)

    def delete_file_or_folder(self, path):
        try:
            try:
                os.remove(path)
            except (IsADirectoryError, PermissionError):
                shutil.rmtree(path)
        except PermissionError:
            print(f"{bcolors.WARNING}[!] Permission denied when trying to delete {path}!{bcolors.ENDC}")

    def copy_file_or_folder(self, src_path, dest_path):
        if os.path.islink(src_path):
            copy_symlink(src_path, dest_path)
            return
            
        try:
            # try copytree first as it also handles symlinks
            shutil.copytree(src_path, dest_path)
        except NotADirectoryError:
            shutil.copy(src_path, dest_path)
        
    def on_modified(self, event):
        if self.is_excluded(event.src_path):
            return

        if self.verbose: print(f"[+] Updating {event.src_path}")

        if os.path.isfile(event.src_path):
            file_relpath = self.get_relative_path(event.src_path)
            try:
                shutil.copy(event.src_path, self.remote_path + "/" + file_relpath)
            except FileNotFoundError:
                # file does not exist; probably already deleted
                pass
    
    def on_created(self, event):
        if self.is_excluded(event.src_path):
            return

        if self.verbose: print(f"[+] Creating {event.src_path}")

        file_relpath = self.get_relative_path(event.src_path)
        try:
            self.copy_file_or_folder(event.src_path, self.remote_path + "/" + file_relpath)
        except FileNotFoundError:
            # file does not exist; probably already deleted
            pass
    
    def on_deleted(self, event):
        if self.is_excluded(event.src_path):
            return

        if self.verbose: print(f"[+] Deleting {event.src_path}")
        file_relpath = self.get_relative_path(event.src_path)

        try: 
            self.delete_file_or_folder(self.remote_path + "/" + file_relpath)
        except FileNotFoundError:
            # file does not exist; so we dont need to delete
            pass
    
    def on_moved(self, event):
        if self.is_excluded(event.src_path):
            return

        if self.verbose: print(f"[+] Moving {event.src_path} to {event.dest_path}")

        src_relpath = self.get_relative_path(event.src_path)
        dest_relpath = self.get_relative_path(event.dest_path)
        try:
            shutil.move(self.remote_path + "/" + src_relpath, self.remote_path + "/" + dest_relpath)
        except FileNotFoundError:
            # file does not exist; probably already deleted
            pass
        

def parse_arguments() -> dict:
    parser = argparse.ArgumentParser()
    parser.add_argument(type=str,  # cast argument to this type
                        metavar="<source-directory>",  # the value used for help messages
                        dest="source",
                        action="store",  # just store the value
                        help="The directory to sync from")
    parser.add_argument(type=str,  # cast argument to this type
                        metavar="<destination-directory>",  # the value used for help messages
                        dest="destination",
                        action="store",  # just store the value
                        help="The directory to sync to")
    parser.add_argument('--exclude', '-x',
                        type=str,  # cast argument to this type
                        metavar="<exclude-directory-pattern>",  # the value used for help messages
                        dest="exclude",
                        action="store",  # just store the value
                        help="All files/directories containing this pattern will be excluded (comma-separate multiple entries)")
    parser.add_argument('--verbose',
                        dest="verbose",
                        action="store_true",  # just store that the value was set
                        help="Enable verbose messages",
                        required=False)

    return vars(parser.parse_args())

def remote_file_exists(remote_path, remote_host):
    p = subprocess.run(["ssh", remote_host, f"test -f {remote_path}"])
    return p.returncode == 0

def remote_dir_exists(remote_path, remote_host):
    p = subprocess.run(["ssh", remote_host, f"test -d {remote_path}"])
    return p.returncode == 0

def create_remote_dir(remote_path, remote_host):
    subprocess.run(["ssh", remote_host, f"mkdir {remote_path}"])

def create_sshfs_mount(local_path, remote_path, remote_host):
    if not remote_dir_exists(remote_path, remote_host):
        create_remote_dir(remote_path, remote_host)

    p = subprocess.run(["sshfs", f"{remote_host}:{remote_path}", local_path])

    if p.returncode != 0:
        print(f"{bcolors.FAIL}[!] Failed to create sshfs directory. Aborting!{bcolors.ENDC}")
        print(f"{bcolors.FAIL}[!] Does the remote directory exist? If not, create it!")
        print(f"{bcolors.FAIL}[!] Command used: sshfs {remote_host}:{remote_path} {local_path}")
        exit(1)

def remove_sshfs_mount(local_path):
    try:
        p = subprocess.run(["fusermount3", "-u", local_path])
        if p.returncode != 0:
            print(f"{bcolors.WARNING}[!] Failed to cleanup sshfs directory!{bcolors.ENDC}")
    except FileNotFoundError:
        print(f"{bcolors.WARNING}[!] fusermount3 not found! Unmounting could go wrong!{bcolors.ENDC}")
    
def create_empty_file(file_path):
    open(file_path, 'a').close()

def sshfs_functionality_check(sshfs_mount_path, remote_host, remote_path):
    # this function checks if the sync is working correctly, e.g.,
    # sometimes FUSE-T (macOS) stops working silently

    # create a file and check whether it exists in the remote directory
    testfile_name = "." \
        + "".join([random.choice(string.ascii_letters) for _ in range(32)]) \
        + "-dirsyncher-testfile"
    testfile_path_local = sshfs_mount_path + "/" + testfile_name
    testfile_path_remote = remote_path + "/" + testfile_name
    assert not os.path.exists(testfile_path_local)

    create_empty_file(testfile_path_local)
    success = remote_file_exists(testfile_path_remote, remote_host)

    os.remove(testfile_path_local)
    return success

def main():
    arg_dict = parse_arguments()

    local_path = arg_dict["source"]

    if ":" in arg_dict["destination"]:

        remote_connection_used = True
        # parse host
        remote_host, remote_path = arg_dict["destination"].split(":")

        if "~" in remote_path:
            print(f"{bcolors.FAIL}[!] dirsyncher does not support remote paths containing '~'. "
                  f"Please extend the path. Aborting!{bcolors.ENDC}")
            exit(1)

        # create an sshfs
        sshfs_temp_directory = tempfile.mktemp()
        os.mkdir(sshfs_temp_directory)
        create_sshfs_mount(sshfs_temp_directory, remote_path, remote_host)

        if not sshfs_functionality_check(sshfs_temp_directory, remote_host, remote_path):
            print(f"{bcolors.FAIL}[!] sshfs functionality check failed!\n"
                  f"[!] Maybe FUSE-T is acting up?{bcolors.ENDC}")
            exit(1)

        # let the remote path point to the sshfs directory
        remote_path_org = remote_path
        remote_path = sshfs_temp_directory
    else:
        remote_path_org = arg_dict["destination"]
        remote_path = arg_dict["destination"]

    if arg_dict["exclude"] is None:
        exclude_directories = []
    elif "," in arg_dict["exclude"]:
        # if we have multiple exclude patterns we split them
        exclude_directories = [e.strip() for e in arg_dict["exclude"].split(",")]

        # remove empty strings
        exclude_directories = [i for i in exclude_directories if i] 
    else:
        exclude_directories = list([arg_dict["exclude"]])

    print(f"{bcolors.OKBLUE}[!] Initializing...{bcolors.ENDC}")

    if arg_dict["verbose"]:
        ts_before_initial_sync = time.time()

    copy_dir(local_path, remote_path, exclude_directories, arg_dict["verbose"])

    if arg_dict["verbose"]:
        ts_after_initial_sync = time.time()
        print(f"{bcolors.VERBOSE}[DBG] Initial sync took {ts_after_initial_sync - ts_before_initial_sync:.2f} seconds.{bcolors.ENDC}")

    print(f"{bcolors.OKBLUE}[!] Copy finished...{bcolors.ENDC}")
    
    event_handler = FileSyncher(local_path, remote_path, arg_dict["verbose"], exclude_directories)

    observer = Observer()
    observer.schedule(event_handler, local_path, recursive=True)
    observer.start()

    # print it here after we started running cause the initial copy can take some time
    if remote_connection_used:
        print(f"{bcolors.OKGREEN}[+] Syncing from {local_path} to {remote_path_org} (on {remote_host}){bcolors.ENDC}")
    else:
        print(f"{bcolors.OKGREEN}[+] Syncing from {local_path} to {remote_path_org} (local){bcolors.ENDC}")
    if arg_dict["verbose"]:
        print(f"{bcolors.OKBLUE}[*] Using local directory: {sshfs_temp_directory}{bcolors.ENDC}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if remote_connection_used:
            remove_sshfs_mount(sshfs_temp_directory)
            try:
                shutil.rmtree(sshfs_temp_directory)
            except OSError:
                # Some OSes (e.g. macOS) seem to instantiate an unmount upon 
                # the first rmtree call (also resulting in an OSError) while 
                # allowing a second call to actually remove the directory.
                shutil.rmtree(sshfs_temp_directory)
        observer.stop()
        observer.join()

    



if __name__ == "__main__":
    main()
