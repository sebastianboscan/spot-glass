"""Run a named Cloudflare tunnel alongside the relay."""

import _thread
import shutil
import subprocess
import threading


class Tunnel:
    def __init__(self, name):
        if shutil.which("cloudflared") is None:
            raise SystemExit("cloudflared is not on PATH")
        self._stopping = False
        self._proc = subprocess.Popen(["cloudflared", "tunnel", "run", name])
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self):
        # If the tunnel dies, take the relay down too rather than leave it
        # running unreachable.
        self._proc.wait()
        if not self._stopping:
            print("[tunnel] cloudflared exited; shutting down", flush=True)
            _thread.interrupt_main()

    def stop(self):
        self._stopping = True
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
