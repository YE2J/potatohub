# macOS 26.2 — Broken Homebrew CPython Error Transcripts

## python3.11 `ensurepip` failure

```
$ /opt/homebrew/bin/python3.11 -m venv venv
Error: Command '[.../venv/bin/python3.11', '-m', 'ensurepip', '--upgrade', '--default-pip'] returned non-zero exit status 1.
```

## python3.11 `pyexpat` symbol mismatch

```
$ /opt/homebrew/bin/python3.11 -m venv --without-pip venv
$ curl -sS https://bootstrap.pypa.io/get-pip.py | python3
  File "<frozen importlib._bootstrap>", line 1178, in _find_and_load
  ...
ImportError: dlopen(.../pyexpat.cpython-311-darwin.so, 0x0002):
  Symbol not found: _XML_SetAllocTrackerActivationThreshold
  Referenced from: pyexpat.cpython-311-darwin.so
  Expected in: /usr/lib/libexpat.1.dylib
```

Root cause: Homebrew's CPython links against its own `libexpat` at build time, but the system `/usr/lib/libexpat.1.dylib` on macOS 26.2 has a different symbol set.

## python3.12 `ensurepip` failure

```
$ /opt/homebrew/bin/python3.12 -m venv venv
Error: Command '[.../venv/bin/python3.12', '-m', 'ensurepip', '--upgrade', '--default-pip'] returned non-zero exit status 1.
```

Same underlying issue — Homebrew's Python 3.12 build is also broken on macOS 26.2.

## Fix: uv

```
$ brew install uv
$ uv venv --python 3.12
Downloading cpython-3.12.13-macos-aarch64-none (download) (23.8MiB)
 Downloaded cpython-3.12.13-macos-aarch64-none (download)
Using CPython 3.12.13
Creating virtual environment at: .venv
$ source .venv/bin/activate
$ uv pip install -e .
Resolved 32 packages in 4.53s
Prepared 19 packages in 10.87s
Installed 32 packages in 52ms
```

uv downloads its own CPython binary, bypassing Homebrew's broken one entirely.
