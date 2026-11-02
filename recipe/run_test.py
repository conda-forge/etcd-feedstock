from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

with socket.socket() as client, socket.socket() as peer:
    client.bind(("127.0.0.1", 0))
    peer.bind(("127.0.0.1", 0))
    client_url = f"http://127.0.0.1:{client.getsockname()[1]}"
    peer_url = f"http://127.0.0.1:{peer.getsockname()[1]}"

with tempfile.TemporaryDirectory() as directory:
    with open(Path(directory) / "etcd.log", "w+") as log:
        server = subprocess.Popen(
            [shutil.which("etcd"), "--name=test", f"--data-dir={directory}/data",
             f"--listen-client-urls={client_url}", f"--advertise-client-urls={client_url}",
             f"--listen-peer-urls={peer_url}", f"--initial-advertise-peer-urls={peer_url}",
             f"--initial-cluster=test={peer_url}"],
            stdout=log, stderr=subprocess.STDOUT,
        )
        ctl = [shutil.which("etcdctl"), f"--endpoints={client_url}", "--command-timeout=3s"]
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                result = subprocess.run(ctl + ["endpoint", "health"], capture_output=True, timeout=10)
                if result.returncode == 0:
                    break
                if server.poll() is not None:
                    raise RuntimeError("etcd exited before becoming healthy")
                time.sleep(0.5)
            else:
                raise TimeoutError("etcd did not become healthy")
            subprocess.run(ctl + ["put", "recipe-test", "ok"], check=True, timeout=10)
            value = subprocess.check_output(ctl + ["get", "recipe-test", "--print-value-only"], timeout=10)
            assert value.strip() == b"ok", value
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
            log.seek(0)
            print(log.read())
