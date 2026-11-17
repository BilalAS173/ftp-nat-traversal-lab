#!/usr/bin/env python3
"""Minimal FTP client over raw TCP sockets (RFC 959). Passive mode only."""

import argparse
import socket


class FTPError(Exception):
    pass


class FTPClient:
    def __init__(self, host, port=21, timeout=10):
        self.timeout = timeout
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.reader = self.sock.makefile("rb")
        code, text = self._read_reply()
        if code != 220:
            raise FTPError(f"unexpected greeting: {text}")

    # ---- control connection ----

    def _read_line(self):
        raw = self.reader.readline()
        if not raw:
            raise FTPError("control connection closed by server")
        return raw.decode("utf-8", errors="replace").rstrip("\r\n")

    def _read_reply(self):
        """Read one reply. Multi-line replies look like '220-...' ... '220 ...'."""
        first = self._read_line()
        code = int(first[:3])
        lines = [first]
        if first[3:4] == "-":
            while True:
                line = self._read_line()
                lines.append(line)
                if line[:3] == first[:3] and line[3:4] == " ":
                    break
        return code, "\n".join(lines)

    def command(self, cmd, *expected):
        self.sock.sendall((cmd + "\r\n").encode("utf-8"))
        code, text = self._read_reply()
        if expected and code not in expected:
            raise FTPError(f"{cmd.split()[0]} failed: {text}")
        return code, text

    # ---- passive data connection ----

    def _open_passive(self):
        _, text = self.command("PASV", 227)
        # Reply looks like: 227 Entering Passive Mode (h1,h2,h3,h4,p1,p2)
        start = text.index("(") + 1
        end = text.index(")", start)
        h1, h2, h3, h4, p1, p2 = (int(x) for x in text[start:end].split(","))
        ip = f"{h1}.{h2}.{h3}.{h4}"
        port = p1 * 256 + p2
        return socket.create_connection((ip, port), timeout=self.timeout)

    def _start_transfer(self, cmd):
        data = self._open_passive()
        try:
            self.command(cmd, 125, 150)
        except Exception:
            data.close()
            raise
        return data

    def _finish_transfer(self):
        code, text = self._read_reply()
        if code not in (226, 250):
            raise FTPError(f"transfer failed: {text}")

    # ---- public API ----

    def login(self, user, password):
        code, _ = self.command(f"USER {user}", 230, 331)
        if code == 331:
            self.command(f"PASS {password}", 230)

    def list(self):
        data = self._start_transfer("LIST")
        chunks = []
        with data:
            while chunk := data.recv(65536):
                chunks.append(chunk)
        self._finish_transfer()
        return b"".join(chunks).decode("utf-8", errors="replace")

    def retr(self, remote, local):
        data = self._start_transfer(f"RETR {remote}")
        with data, open(local, "wb") as f:
            while chunk := data.recv(65536):
                f.write(chunk)
        self._finish_transfer()

    def stor(self, local, remote):
        data = self._start_transfer(f"STOR {remote}")
        with data, open(local, "rb") as f:
            while chunk := f.read(65536):
                data.sendall(chunk)
        self._finish_transfer()

    def quit(self):
        try:
            self.command("QUIT", 221)
        finally:
            self.reader.close()
            self.sock.close()


def main():
    parser = argparse.ArgumentParser(description="Minimal FTP client")
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("ls")
    get_p = sub.add_parser("get")
    get_p.add_argument("remote")
    get_p.add_argument("local")
    put_p = sub.add_parser("put")
    put_p.add_argument("local")
    put_p.add_argument("remote")

    args = parser.parse_args()

    ftp = FTPClient(args.host, args.port)
    try:
        ftp.login(args.user, args.password)
        if args.action == "ls":
            print(ftp.list())
        elif args.action == "get":
            ftp.retr(args.remote, args.local)
        elif args.action == "put":
            ftp.stor(args.local, args.remote)
    finally:
        ftp.quit()


if __name__ == "__main__":
    main()
