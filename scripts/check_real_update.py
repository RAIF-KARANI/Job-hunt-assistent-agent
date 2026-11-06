"""
The real update test: run it before every release (D3), after build_installer.py.

    python scripts/check_real_update.py                 # all four checks, ~5 min
    python scripts/check_real_update.py self_update     # just one
    python scripts/check_real_update.py --old 1.1.0     # update from another old version

pytest can't catch what broke updates up to 1.1.0: that took a running app, its
tray and the real installer together (D42). So this installs the separate
JobLens Test Build (own AppId, own folder, fake LOCALAPPDATA) and really updates
it. The app, tray, shortcut, installer and the updater's download/verify/install
are all real; only GitHub is a local stand-in (an HTTPS proxy with a certificate
that only this test trusts). The page is driven through WebView2's debug port.
A real JobLens is never touched, even a running one, and each check proves it.

    new_from_old   an old JobLens updates to this build (it hides instead of quitting)
    self_update    this build updates to the next version (it must quit by itself)
    hand_run       Setup run by hand while JobLens sits in the tray
    failure        an update that fails: the old JobLens reopens and says so

Needs: dist/JobLens from build_installer.py, and the Test Build installer of the
old version in dist/ (git-ignored: to make one, check out that tag and run
build_installer.py --test-install). The other Test Builds are made here from
dist/JobLens. "Next version" is the same app with a higher version number. The
Setup logs are kept in build/update-check/. Exit code 0 only if all checks pass.
"""

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import websockets

from build_installer import REAL_APP_ID, ROOT, TEST_APP_ID, __version__, find_iscc, uninstall_entry

DIST = ROOT / "dist"
KEPT_LOGS = ROOT / "build" / "update-check"
OPENSSL = Path(r"C:\Program Files\Git\mingw64\bin\openssl.exe")
OLD_VERSION = "1.0.3"     # the last kind that hides to the tray instead of quitting
CDP_PORT = 9347
QUICK_KEY = "Ctrl+Alt+F9"  # not the default: a real JobLens may be holding that one
GH = "https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases/download/"


def check(ok, what):
    if not ok:
        raise AssertionError(what)
    print("  ok:", what, flush=True)


def registered(app_id=TEST_APP_ID):
    return (uninstall_entry(app_id) or {}).get("DisplayVersion")


def powershell(script):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True).stdout.strip()


def next_version(version):
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def test_build(version):
    return DIST / f"JobLens-TestBuild-Setup-{version}.exe"


def make_test_build(version):
    """Rebuilt whenever dist/JobLens is newer, so this never tests an old app."""
    app, setup = DIST / "JobLens" / "JobLens.exe", test_build(version)
    if not app.exists():
        sys.exit("dist/JobLens is missing: run python scripts/build_installer.py first.")
    if setup.exists() and setup.stat().st_mtime >= app.stat().st_mtime:
        return
    print(f"Making the Test Build of {version}...", flush=True)
    subprocess.run([str(find_iscc()), f"/DAppVersion={version}", "/DTestBuild", "/Q", "installer/joblens.iss"],
                   check=True, cwd=ROOT)


def make_certificate(folder):
    """github.com, for this test only: nothing is added to Windows' trusted list."""
    config = folder / "openssl.cnf"
    config.write_text("[req]\ndistinguished_name=dn\n[dn]\n", encoding="utf-8")
    pem, key = folder / "github.pem", folder / "github.key"
    # OPENSSL_CONF: another program's setting can point at a file that isn't there.
    subprocess.run([str(OPENSSL), "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(pem),
                    "-days", "2", "-subj", "/CN=github.com", "-addext", "subjectAltName=DNS:github.com"],
                   check=True, capture_output=True, env={**os.environ, "OPENSSL_CONF": str(config)})
    return pem, key


def fake_github(body, pem, key):
    """CONNECT github.com -> TLS with our certificate -> serve `body`. Returns the port."""
    server = socket.create_server(("127.0.0.1", 0))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(pem, key)

    def serve(client):
        try:
            head = b""
            while b"\r\n\r\n" not in head:
                head += client.recv(4096)
            client.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
            secure = context.wrap_socket(client, server_side=True)
            request = b""
            while b"\r\n\r\n" not in request:
                request += secure.recv(4096)
            secure.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body))
            secure.sendall(body)
            secure.close()
        except OSError as e:
            print("  fake GitHub:", e)

    def accept():
        while True:
            client, _ = server.accept()
            threading.Thread(target=serve, args=(client,), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    return server.getsockname()[1]


async def _evaluate(expression):
    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=3) as response:
        pages = [p for p in json.load(response) if p.get("type") == "page" and "#/quick" not in p.get("url", "")]
    async with websockets.connect(pages[0]["webSocketDebuggerUrl"], max_size=None) as socket_to_page:
        await socket_to_page.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": expression, "awaitPromise": True, "returnByValue": True}}))
        while True:
            message = json.loads(await asyncio.wait_for(socket_to_page.recv(), 120))
            if message.get("id") == 1:
                return message


def page(expression):
    result = asyncio.run(_evaluate(expression)).get("result", {})
    if "exceptionDetails" in result:
        raise RuntimeError(str(result["exceptionDetails"])[:400])
    return result.get("result", {}).get("value")


def wait_for_page(seconds=45):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if page("!!(window.pywebview && window.pywebview.api && window.pywebview.api.update_status)"):
                return True
        except Exception:  # not up yet: refused, no page, or a page mid-load
            pass
        time.sleep(0.5)
    return False


class Case:
    """One Test Build, installed in a temp folder, and the fake GitHub offering `target`."""

    def __init__(self, name, client_version, target_version, certificate):
        self.name, self.client_version, self.target_version = name, client_version, target_version
        self.certificate = certificate
        self.tmp = Path(tempfile.mkdtemp(prefix="joblens-update-check-"))
        self.folder = self.tmp / "JobLens Test Build"
        self.exe = str(self.folder / "JobLens.exe")
        self.home = self.tmp / "appdata" / "JobLens"
        self.target = test_build(target_version)
        self.port = None

    def prepare(self):
        check(registered() is None, "no Test Build is installed from an earlier run")
        (self.home / "data").mkdir(parents=True)
        (self.home / ".env").write_text(f"SETUP_DONE=true\nUPDATE_CHECK=false\nQUICK_KEY={QUICK_KEY}\nTRACING=off\n", encoding="utf-8")
        (self.home / "data" / "marker.txt").write_text("my data", encoding="utf-8")
        body = self.target.read_bytes()
        name = f"JobLens-Setup-{self.target_version}.exe"
        (self.home / "update_check.json").write_text(json.dumps({
            "current": self.client_version, "latest": f"v{self.target_version}", "newer": True, "name": "test", "page": GH,
            "published_at": None, "notes": "", "error": None, "checked_at": time.time(),
            "installer": {"name": name, "size": len(body), "url": f"{GH}v{self.target_version}/{name}",
                          "sha256": hashlib.sha256(body).hexdigest()}}), encoding="utf-8")
        self.port = fake_github(body, *self.certificate)
        subprocess.run([str(test_build(self.client_version)), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                        f"/DIR={self.folder}", f"/LOG={self.tmp / 'client-install.log'}"], check=True)
        check(registered() == self.client_version, f"{self.client_version} is installed")

    def env(self):
        return {**os.environ, "LOCALAPPDATA": str(self.tmp / "appdata"), "HTTPS_PROXY": f"http://127.0.0.1:{self.port}",
                "REQUESTS_CA_BUNDLE": str(self.certificate[0]),
                "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": f"--remote-debugging-port={CDP_PORT}"}

    def running(self):
        """{pid: has a visible window}: only the JobLens in this test's folder."""
        path = self.exe.replace("'", "''")
        out = powershell(f"Get-Process -Name JobLens -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -eq '{path}' }} | "
                         "ForEach-Object { \"$($_.Id):$([int]($_.MainWindowHandle -ne 0))\" }")
        return {pid: visible == "1" for pid, visible in (line.split(":") for line in out.split())}

    def start(self):
        subprocess.Popen([self.exe], env=self.env(), cwd=str(self.tmp))
        check(wait_for_page(), "JobLens started")
        time.sleep(2)  # the tray and the shortcut
        return next(iter(self.running()))

    def click_install(self):
        pid = self.start()
        status = page("window.pywebview.api.update_status().then(s => [s.latest, s.newer])")
        check(status == [f"v{self.target_version}", True], f"it offers v{self.target_version}")
        check(page("window.pywebview.api.download_update()").get("verified"), "the download is verified")
        check(page("window.pywebview.api.install_update()").get("ok"), "Install now started the installer")
        return pid

    def follow_update(self, old_pid, seconds=75):
        """Wait until a new JobLens is up, and the version changed if it's going to."""
        start = time.time()
        new_pid = None
        while time.time() - start < seconds:
            new_pid = next((pid for pid in self.running() if pid != old_pid), None)
            changed = registered() != self.client_version
            if new_pid and (changed or time.time() - start > 30):
                break
            time.sleep(0.5)
        return new_pid

    def setup_log(self, wanted, seconds=15):
        """Setup's log, once `wanted` is in it (the app may be moving the file)."""
        end = time.time() + seconds
        text = ""
        while time.time() < end:
            for log in (self.home / "updates" / "install.log", self.home / "last_update.log"):
                if log.exists():
                    text = log.read_text(encoding="utf-8-sig", errors="replace")
                    if wanted in text:
                        return text
            time.sleep(0.5)
        return text

    def check_data_kept(self):
        check((self.home / "data" / "marker.txt").read_text(encoding="utf-8") == "my data", "the data folder is intact")

    def clean_up(self):
        path = self.exe.replace("'", "''")
        powershell(f"Get-Process -Name JobLens -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -eq '{path}' }} | Stop-Process -Force")
        time.sleep(2)
        if (self.folder / "LICENSE.txt").exists():
            os.chmod(self.folder / "LICENSE.txt", 0o666)
        uninstaller = self.folder / "unins000.exe"
        if uninstaller.exists():
            subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        for _ in range(60):
            if registered() is None and not Path(self.exe).exists():
                break
            time.sleep(1)
        KEPT_LOGS.mkdir(parents=True, exist_ok=True)
        for log in (self.home / "updates" / "install.log", self.home / "last_update.log"):
            if log.exists():
                shutil.copy(log, KEPT_LOGS / f"{self.name}-{log.name}")
        shutil.rmtree(self.tmp, ignore_errors=True)


def check_updated(case, old_pid, log_says):
    new_pid = case.follow_update(old_pid)
    check(new_pid, "a new JobLens opened by itself")
    check(old_pid not in case.running(), "the old JobLens is gone")
    check(registered() == case.target_version, f"Windows shows {case.target_version}")
    check(wait_for_page(30), "the new page came up")
    text = case.setup_log("Installation process succeeded.")
    check("Installation process succeeded." in text, "Setup's log says it succeeded")
    check(log_says in text, f"Setup's log says: {log_says}")
    check(page("window.pywebview.api.update_status().then(s => s.install_problem || null)") is None, "no install problem is shown")
    case.check_data_kept()


def new_from_old(case):
    check_updated(case, case.click_install(), "it was ended.")
    # A stale dist/JobLens shows up here: the page reports the frozen app's version.
    check(page("window.pywebview.api.update_status().then(s => s.current)") == __version__, f"the app says {__version__}")


def self_update(case):
    check_updated(case, case.click_install(), "JobLens is closed (check result 0).")


def hand_run(case):
    pid = case.start()
    # The X button: JobLens hides to the tray.
    powershell("Add-Type -Name W -Namespace N -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool "
               "PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);'; "
               f"$p = Get-Process -Id {pid}; [N.W]::PostMessage($p.MainWindowHandle, 0x10, [IntPtr]::Zero, [IntPtr]::Zero)")
    time.sleep(2)
    check(case.running().get(pid) is False, "the X button hid JobLens to the tray")
    log = case.tmp / "hand.log"
    code = subprocess.run([str(case.target), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log}"], env=case.env()).returncode
    check(code == 0, "Setup finished")
    check(registered() == case.target_version, f"Windows shows {case.target_version}")
    check(not case.running(), "JobLens closed when Setup asked it to")
    check("did not quit" not in log.read_text(encoding="utf-8-sig", errors="replace"), "nothing was force-closed")
    case.check_data_kept()


def failure(case):
    os.chmod(case.folder / "LICENSE.txt", 0o444)  # read-only: Setup can't replace it
    old_pid = case.click_install()
    check(case.follow_update(old_pid, seconds=60), "the old JobLens opened again")
    check(registered() == case.client_version, f"Windows still shows {case.client_version}")
    check(wait_for_page(30), "its page came up")
    problem = page("window.pywebview.api.update_status().then(s => s.install_problem || null)")
    check(problem and problem.get("version") == case.target_version, "it knows the update failed")
    page("window.location.hash = '#/settings'")
    time.sleep(2)
    card = page("(document.querySelector('.updates [role=alert]') || {}).innerText") or ""
    check(f"The update to v{case.target_version} didn't finish." in card, "Settings says so")
    case.check_data_kept()


def main():
    new, after = __version__, next_version(__version__)
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    checks = {"new_from_old": new_from_old, "self_update": self_update, "hand_run": hand_run, "failure": failure}
    parser.add_argument("checks", nargs="*", default=list(checks), help=f"default: all of them ({', '.join(checks)})")
    parser.add_argument("--old", default=OLD_VERSION, help=f"the old version to update from (default {OLD_VERSION})")
    args = parser.parse_args()
    unknown = set(args.checks) - set(checks)
    if unknown:
        parser.error(f"no such check: {', '.join(sorted(unknown))}")

    if not test_build(args.old).exists():
        sys.exit(f"{test_build(args.old).name} is missing from dist/: see the top of this file.")
    make_test_build(new)
    make_test_build(after)
    versions = {"new_from_old": (args.old, new)}

    real = registered(REAL_APP_ID)
    failed = []
    with tempfile.TemporaryDirectory(prefix="joblens-update-cert-") as folder:
        certificate = make_certificate(Path(folder))
        for name in args.checks:
            client, target = versions.get(name, (new, after))
            print(f"\n=== {name}: {client} -> {target} ===", flush=True)
            case = Case(name, client, target, certificate)
            try:
                case.prepare()
                checks[name](case)
            except Exception as e:
                failed.append(name)
                print(f"  FAILED: {e!r}", flush=True)
            finally:
                case.clean_up()
            if registered(REAL_APP_ID) != real:
                sys.exit("The REAL JobLens install changed during the test - this must never happen.")

    print(f"\nYour JobLens ({real or 'not installed'}) was not touched.")
    print(f"FAILED: {', '.join(failed)}" if failed else "All update checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
