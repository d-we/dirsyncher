# DirSyncher
Sync directories to a (remote) location.

## Dependencies
- [python-watchdog](https://pypi.org/project/pynput/)

## Functionality  
Syncs changes to a local directory to a remote directory. The remote directory has to exist.

## Example Usage
```bash
./dirsyncher.py ./local-dir lab-machine:remote-dir -x build
```
This will sync the local directory `./local-dir` to the remote directory `remote-dir` on the machine with the SSH name`lab-machine`.
Also, it will exclude all paths containing the string `"build"`. These will not be synced.
