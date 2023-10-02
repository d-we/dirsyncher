# DirSyncher
Sync directories to a (remote) location.

## Dependencies
- [python-watchdog](https://pypi.org/project/pynput/)

## Functionality  
Syncs changes to a local directory to a remote directory. The remote directory has to exist.

## Example Usage
```bash
./dirsyncher.py ./local-dir lab-machine:remote-dir
```