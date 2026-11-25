#!/usr/bin/env python3
"""HTTP baseline client: download test files, time each one, verify SHA-256."""

import hashlib
import time
import urllib.request

BASE_URL = "http://127.0.0.1:8000/"
FILES = ["f1", "f10", "f100"]
CHUNK_SIZE = 64 * 1024
MB = 1024 * 1024


def load_checksums(path="checksums.txt"):
    """Return {filename: sha256_hex} from lines formatted as '<hash>  <filename>'."""
    expected = {}
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                digest, name = parts
                expected[name] = digest
    return expected


def download(name):
    """Stream one file over HTTP. Return (sha256_hex, bytes_received, seconds)."""
    sha = hashlib.sha256()
    total = 0
    start = time.perf_counter()
    with urllib.request.urlopen(BASE_URL + name) as resp:
        while chunk := resp.read(CHUNK_SIZE):
            sha.update(chunk)
            total += len(chunk)
    elapsed = time.perf_counter() - start
    return sha.hexdigest(), total, elapsed


def main():
    expected = load_checksums()
    print(f"{'file':<6} {'seconds':>9} {'MB/s':>9}  status")
    for name in FILES:
        digest, size, elapsed = download(name)
        mbps = (size / MB) / elapsed
        status = "OK" if digest == expected.get(name) else "MISMATCH"
        print(f"{name:<6} {elapsed:>9.3f} {mbps:>9.2f}  {status}")


if __name__ == "__main__":
    main()
