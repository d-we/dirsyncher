# DirSyncher
Sync directories to a (remote) location.


## Why?
The major benefit of DirSyncher is that it behaves *like a remote mounted folder* without the issues related to executing programs from within a remotely mounted folder, e.g., some tools get incredibly slow when spawned directly in sshfs folders.
To achieve this, DirSyncher monitors the source directory for changes and copies these changes to an sshfs folder, instead of directly using an sshfs folder.

## Dependencies
- [python-watchdog](https://pypi.org/project/pynput/)

## Functionality  
Syncs changes to a local directory to a remote directory.

## Example Usage
```bash
./dirsyncher.py ./local-dir lab-machine:remote-dir -x build,venv
```
This will sync the local directory `./local-dir` to the remote directory `remote-dir` on the machine with the SSH name`lab-machine`.
Also, it will exclude all paths containing the string `"build"`. These will not be synced.
