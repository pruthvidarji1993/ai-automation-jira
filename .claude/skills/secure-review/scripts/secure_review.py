#!/usr/bin/env python3
"""secure-review runner. Stdlib only, so the skill folder can be copied into any repo.

  scan     detect stacks, install pinned scanners on demand, run them, write scan.json
  report   merge scan.json + review.json into report.html and print the developer list
  selftest check detection, normalisers, diff scoping and HTML escaping offline
"""
import argparse
import datetime
import hashlib
import html
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PY_PINS = {"pip-audit": "2.10.1", "bandit": "1.9.4", "semgrep": "1.182.1"}
GITLEAKS = "8.30.1"
OSV = "2.6.0"
WSV = "web-secure-verification@1.0.2"
HOME = Path(os.environ.get("SECURE_REVIEW_HOME") or Path.home() / ".cache" / "secure-review")
WIN = os.name == "nt"

SKIP_DIRS = {"node_modules", "venv", "dist", "build", "out", "coverage", "__pycache__", "site-packages",
             "vendor", "Pods", "DerivedData", "target"}
MANIFESTS = re.compile(r"(^|/)(package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|requirements[^/]*\.txt|"
                       r"pyproject\.toml|poetry\.lock|Pipfile(\.lock)?|uv\.lock|composer\.(json|lock)|"
                       r"Podfile(\.lock)?|Package\.resolved)$")
# Ecosystems osv-scanner audits; npm and PyPI are covered by web-secure-verification and pip-audit.
OSV_STACKS = {"php", "ios"}
SEVERITIES = ["critical", "high", "medium", "low", "info"]
# Scanners in web-secure-verification that report code quality, not security.
WSV_QUALITY = {"outdated", "hydration", "bundle", "rsc-boundary"}
WSV_OWASP = {"npm-audit": "A06", "deprecated": "A06", "outdated": "A06", "secrets": "A07",
             "code-security": "A03", "nextjs": "A05", "source-maps": "A05", "supply-chain": "A08"}
OWASP = {"A01": "Broken Access Control", "A02": "Cryptographic Failures", "A03": "Injection",
         "A04": "Insecure Design", "A05": "Security Misconfiguration",
         "A06": "Vulnerable and Outdated Components", "A07": "Identification and Authentication Failures",
         "A08": "Software and Data Integrity Failures", "A09": "Security Logging and Monitoring Failures",
         "A10": "Server-Side Request Forgery"}
CWE_OWASP = {22: "A01", 200: "A01", 284: "A01", 285: "A01", 352: "A01", 601: "A01", 639: "A01",
             295: "A02", 319: "A02", 326: "A02", 327: "A02", 328: "A02", 330: "A02", 338: "A02",
             20: "A03", 74: "A03", 77: "A03", 78: "A03", 79: "A03", 89: "A03", 94: "A03", 95: "A03",
             643: "A03", 1336: "A03", 209: "A04", 16: "A05", 489: "A05", 611: "A05", 1104: "A06",
             259: "A07", 287: "A07", 384: "A07", 521: "A07", 798: "A07", 494: "A08", 502: "A08",
             829: "A08", 117: "A09", 778: "A09", 918: "A10"}


def run(cmd, cwd=None, timeout=1800):
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"


def tail(text, n=200):
    """The line worth showing from a tool's stderr: its first ERROR line, else its last line."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    line = next((l for l in lines if l.upper().startswith("ERROR")), lines[-1] if lines else "no output")
    return line[:n]


def finding(source, rule, severity, title, file=None, line=None, detail="", fix="", owasp=None, cwe=None,
            category="security"):
    return {"source": source, "rule": rule, "severity": severity if severity in SEVERITIES else "medium",
            "title": title, "file": file, "line": line, "detail": detail, "fix": fix, "owasp": owasp,
            "cwe": cwe, "category": category}


# ---- stack detection ------------------------------------------------------

def detect(root):
    projects = []
    for dirpath, dirs, files in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirs[:] = [] if len(rel.parts) >= 3 else sorted(
            d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        stacks = set()
        if "package.json" in files:
            try:
                pkg = json.loads(Path(dirpath, "package.json").read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pkg = {}
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if deps or "workspaces" not in pkg:  # a bare workspace root: its packages are scanned on their own
                stacks.add("node")
            if "next" in deps:
                stacks |= {"next", "react"}
            elif deps.keys() & {"react", "react-dom", "react-native"}:
                stacks.add("react")
            if deps.keys() & {"express", "@nestjs/core", "fastify", "koa", "hono", "@hapi/hapi"}:
                stacks.add("node-api")
            if "react-native" in deps:
                stacks.add("react-native")
        py_files = [f for f in files if f in {"pyproject.toml", "Pipfile", "setup.py", "setup.cfg"}
                    or (f.startswith("requirements") and f.endswith(".txt"))]
        if py_files:
            stacks.add("python")
            text = " ".join(Path(dirpath, f).read_text(encoding="utf-8", errors="ignore").lower() for f in py_files)
            stacks |= {fw for fw in ("django", "flask", "fastapi") if fw in text}
        if "Dockerfile" in files:
            stacks.add("docker")
        if "composer.json" in files:
            stacks.add("php")
        if {"Podfile", "Package.swift"} & set(files):  # native iOS side of React Native apps
            stacks.add("ios")
        if stacks:
            projects.append({"path": rel.as_posix() if rel.parts else ".", "stacks": sorted(stacks)})
    return projects


# ---- git scope ------------------------------------------------------------

def default_base(root):
    best = None
    for ref in ("origin/develop", "origin/main", "origin/master", "develop", "main", "master"):
        code, out, _ = run(["git", "rev-list", "--count", f"{ref}..HEAD"], cwd=root)
        if code == 0 and (best is None or int(out) < best[1]):
            best = (ref, int(out))
    return best[0] if best else None


def changed_files(root, base):
    files = set()
    for args in (["diff", "--relative", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
                 ["diff", "--relative", "--name-only", "--diff-filter=ACMR", "HEAD"],
                 ["ls-files", "--others", "--exclude-standard"]):
        code, out, _ = run(["git", *args], cwd=root)
        if code == 0:
            files |= {line.strip() for line in out.splitlines() if line.strip()}
    return {f for f in files if (root / f).is_file()}


def git_ignored(root, files):
    if not files:
        return set()
    p = subprocess.run(["git", "check-ignore", "--stdin"], cwd=root, input="\n".join(sorted(files)),
                       capture_output=True, text=True)
    return {l.strip() for l in p.stdout.splitlines() if l.strip()}


def in_scope(f, changed, deps_changed):
    if f.get("source") == "gitleaks" and "Committed in" in f.get("detail", ""):
        return True  # found in a commit on this branch; the file may since be deleted
    return f["file"] in changed if f.get("file") else deps_changed


def exclude_output(root):
    """Keep reports out of git without touching the project's .gitignore."""
    code, out, _ = run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=root)
    if code != 0:
        return
    path = (root / out.strip()).resolve()
    text = path.read_text() if path.exists() else ""
    if ".secure-review/" not in text.split():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + ("" if text.endswith("\n") or not text else "\n") + ".secure-review/\n")


# ---- tool installation ----------------------------------------------------

def download(url):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read()
    except Exception:  # python.org macOS builds often lack CA certs; curl uses the system store
        p = subprocess.run(["curl", "-fsSL", "--connect-timeout", "15", "--max-time", "120", url],
                           capture_output=True, timeout=150)
        if p.returncode != 0:
            raise RuntimeError(f"download failed: {url} {tail(p.stderr.decode(errors='ignore'))}")
        return p.stdout


def venv_bin(name):
    return HOME / "venv" / ("Scripts" if WIN else "bin") / (name + (".exe" if WIN else ""))


_py_ready = None


def ensure_py_tools(tools):
    global _py_ready
    if _py_ready is not None:
        return _py_ready
    marker = HOME / "venv" / "secure-review-pins.json"
    if marker.exists() and json.loads(marker.read_text()) == PY_PINS:
        _py_ready = True
        return True
    if sys.version_info < (3, 10):
        tools.append(tool("python-tools", ".", "skipped", "bandit/pip-audit/semgrep need Python 3.10+; "
                          f"this is {platform.python_version()}"))
        _py_ready = False
        return False
    print(f"installing {', '.join(PY_PINS)} into {HOME / 'venv'} (one time)...", flush=True)
    code, _, err = run([sys.executable, "-m", "venv", HOME / "venv"])
    if code == 0:
        code, _, err = run([venv_bin("python"), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                            *[f"{k}=={v}" for k, v in PY_PINS.items()]], timeout=1800)
    if code != 0:
        tools.append(tool("python-tools", ".", "failed", f"install failed: {tail(err)}"))
        _py_ready = False
        return False
    marker.write_text(json.dumps(PY_PINS))
    _py_ready = True
    return True


def ensure_binary(name, version_args, minimum, fetch):
    """Cached pinned binary, else one already on PATH, else a verified download, else Homebrew."""
    exe = HOME / "bin" / (name + (".exe" if WIN else ""))
    if exe.exists():
        return exe
    on_path = shutil.which(name)
    if on_path and version_at_least(" ".join(run([on_path, *version_args])[1:]), minimum):
        return on_path
    try:
        print(f"installing {name} into {exe.parent} (one time)...", flush=True)
        blob = fetch()
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(blob)
        exe.chmod(0o755)
        return exe
    except Exception as e:
        # Some networks block GitHub's release-asset host; Homebrew pulls from its own CDN.
        if not shutil.which("brew"):
            raise
        print(f"{e}; trying brew install {name}...", flush=True)
        code, _, err = run(["brew", "install", name], timeout=900)
        if code != 0 or not shutil.which(name):
            raise RuntimeError(f"{e}; brew install failed: {tail(err)}")
        return shutil.which(name)


def version_at_least(text, minimum):
    m = re.search(r"(\d+)\.(\d+)", text or "")
    return bool(m) and (int(m[1]), int(m[2])) >= minimum


def platform_names(x64):
    os_name = {"Darwin": "darwin", "Linux": "linux", "Windows": "windows"}.get(platform.system())
    arch = {"x86_64": x64, "amd64": x64, "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower())
    if not os_name or not arch:
        raise RuntimeError(f"no prebuilt binary for {platform.system()}/{platform.machine()}")
    return os_name, arch


def verified_download(base, asset, sums_file):
    blob = download(base + asset)
    sums = download(base + sums_file).decode()
    expected = next((l.split()[0] for l in sums.splitlines() if l.split() and l.split()[-1].lstrip("*") == asset), None)
    if expected != hashlib.sha256(blob).hexdigest():
        raise RuntimeError(f"{asset} checksum mismatch - refusing to install")
    return blob


def fetch_gitleaks():
    os_name, arch = platform_names("x64")
    asset = f"gitleaks_{GITLEAKS}_{os_name}_{arch}.{'zip' if WIN else 'tar.gz'}"
    blob = verified_download(f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS}/", asset,
                             f"gitleaks_{GITLEAKS}_checksums.txt")
    if WIN:
        return zipfile.ZipFile(io.BytesIO(blob)).read("gitleaks.exe")
    with tarfile.open(fileobj=io.BytesIO(blob)) as t:
        return t.extractfile("gitleaks").read()


def fetch_osv():
    os_name, arch = platform_names("amd64")
    return verified_download(f"https://github.com/google/osv-scanner/releases/download/v{OSV}/",
                             f"osv-scanner_{os_name}_{arch}{'.exe' if WIN else ''}", "osv-scanner_SHA256SUMS")


def ensure_gitleaks():
    return ensure_binary("gitleaks", ["version"], (8, 19), fetch_gitleaks)  # 8.19+ has `dir`/`git`


def ensure_osv():
    return ensure_binary("osv-scanner", ["--version"], (2, 0), fetch_osv)  # 2.x has `scan source`


def tool(name, project, status, note="", count=0):
    return {"tool": name, "project": project, "status": status, "note": note, "count": count}


# ---- normalisers (one per scanner) ----------------------------------------

def norm_wsv(data, prefix):
    out = []
    for result in data.get("results", []):
        scanner = result.get("scanner")
        for i in result.get("issues", []):
            file = i.get("file")
            # ids embed "-<file>-<line>"; strip it so one verdict can cover every instance of a rule
            rule = i.get("ruleId") or (i["id"].split(f"-{file}")[0] if file else i["id"])
            if file and prefix != ".":
                file = f"{prefix}/{file}"
            # The secrets scanner quotes the start of the value; the report may go to a client.
            detail = re.sub(r'Value starts with: "[^"]*"', "Value redacted.", i.get("description", ""))
            out.append(finding("web-secure-verification", f"{scanner}:{rule}",
                               i.get("severity"), i.get("title", ""), file, i.get("line"),
                               detail, i.get("fix", ""), WSV_OWASP.get(scanner),
                               category="quality" if scanner in WSV_QUALITY else
                               "compliance" if scanner == "license" else "security"))
    return out


def norm_bandit(data, root):
    out = []
    for r in data.get("results", []):
        cwe = (r.get("issue_cwe") or {}).get("id")
        sev = r["issue_severity"].lower()
        if r.get("issue_confidence") == "LOW":
            sev = "low"
        # B105-B107 quote the password in the message and the code snippet.
        secret = r["test_id"] in ("B105", "B106", "B107")
        title = re.sub(r"'[^']*'", "'[redacted]'", r["issue_text"]) if secret else r["issue_text"]
        out.append(finding("bandit", r["test_id"], sev, title, rel_path(r["filename"], root),
                           r["line_number"], "" if secret else r.get("code", "").strip()[:300], r.get("more_info", ""),
                           CWE_OWASP.get(cwe), f"CWE-{cwe}" if cwe else None))
    return out


def norm_pip_audit(data, prefix, req):
    # One finding per package: a single upgrade fixes them all, and 65 rows for one Django bump is noise.
    out = []
    version = lambda s: tuple(int(n) for n in re.findall(r"\d+", s))
    for dep in data.get("dependencies", []):
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        cves = [a for v in vulns for a in v.get("aliases", []) if a.startswith("CVE-")]
        ids = ", ".join(cves or [v["id"] for v in vulns])
        # Lowest fix per advisory on any branch; the highest of those clears every advisory.
        fixes = [min(v["fix_versions"], key=version) for v in vulns if v.get("fix_versions")]
        fix = (f"Upgrade {dep['name']} to {max(fixes, key=version)} or later" if fixes
               else f"No fixed version published for {dep['name']}; replace or mitigate")
        out.append(finding("pip-audit", dep["name"], "high",
                           f"Vulnerable dependency: {dep['name']} {dep['version']} ({len(vulns)} advisories)",
                           None, None, ids[:600], f"{fix} ({prefix}/{req})", "A06"))
    return out


def norm_osv(data, root):
    out, seen = [], set()
    version = lambda s: tuple(int(n) for n in re.findall(r"\d+", s))
    for result in data.get("results", []):
        src = rel_path(result["source"]["path"], root)
        for p in result.get("packages", []):
            pkg, vulns = p["package"], p.get("vulnerabilities") or []
            key = (pkg["name"], pkg.get("version"))
            if not vulns or pkg.get("ecosystem") in ("npm", "PyPI") or key in seen:
                continue
            seen.add(key)
            scores = [float(g["max_severity"]) for g in p.get("groups", []) if g.get("max_severity")]
            top = max(scores, default=None)
            sev = "high" if top is None else "critical" if top >= 9 else "high" if top >= 7 else \
                "medium" if top >= 4 else "low"
            current, fixes = version(pkg.get("version", "")), []
            for v in vulns:
                fixed = [e["fixed"] for a in v.get("affected", []) for r in a.get("ranges", [])
                         for e in r.get("events", []) if "fixed" in e and version(e["fixed"]) > current]
                if fixed:
                    fixes.append(min(fixed, key=version))
            cves = [a for v in vulns for a in v.get("aliases", []) if a.startswith("CVE-")]
            fix = (f"Upgrade {pkg['name']} to {max(fixes, key=version)} or later" if fixes
                   else f"No fixed version published for {pkg['name']}; replace or mitigate")
            out.append(finding("osv-scanner", pkg["name"], sev,
                               f"Vulnerable dependency: {pkg['name']} {pkg.get('version')} ({len(vulns)} advisories)",
                               None, None, ", ".join(sorted(set(cves)) or [v["id"] for v in vulns])[:600],
                               f"{fix} ({src}, {pkg.get('ecosystem')})", "A06"))
    return out


def norm_semgrep(data):
    out = []
    for r in data.get("results", []):
        meta = r.get("extra", {}).get("metadata", {})
        owasp = next((o[:3] for o in meta.get("owasp", []) if "2021" in o), None)
        cwe = (meta.get("cwe") or [None])[0]
        sev = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}.get(r.get("extra", {}).get("severity"), "medium")
        out.append(finding("semgrep", r["check_id"], sev, r["extra"].get("message", "")[:200].strip(),
                           r["path"], r["start"]["line"], r["extra"].get("message", "").strip(),
                           r["extra"].get("fix") or "", owasp, cwe.split(":")[0] if cwe else None))
    return out


def norm_gitleaks(data, src_root):
    return [finding("gitleaks", x["RuleID"], "critical", f"Secret in source: {x.get('Description') or x['RuleID']}",
                    rel_path(x["File"], src_root), x.get("StartLine"),
                    "Value redacted." + (f" Committed in {x['Commit'][:8]}." if x.get("Commit") else ""),
                    "Rotate the credential, then move it to an environment variable or secret store. "
                    "Removing it from the file does not remove it from git history.", "A07", "CWE-798")
            for x in data or []]


def rel_path(f, root):
    p = Path(f)
    try:
        return (Path(root) / p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        s = p.as_posix()
        return s[2:] if s.startswith("./") else s


# ---- scanner runs ---------------------------------------------------------

def guarded(name, proj, tools, fn, *args):
    """Run one scanner; an unexpected crash becomes a 'failed' row so the other tools still run."""
    try:
        return fn(*args)
    except Exception as e:
        tools.append(tool(name, proj, "failed", f"{type(e).__name__}: {e}"[:200]))
        return []


def scan_wsv(root, proj, stacks, mode, tools, raw):
    npx = shutil.which("npx")
    pdir = root / proj
    if not npx:
        tools.append(tool("web-secure-verification", proj, "skipped", "npx not found - install Node.js 18+"))
        return []
    if not (pdir / "node_modules").is_dir():
        # Installing would run the project's postinstall scripts - the reviewer decides, not this script.
        tools.append(tool("web-secure-verification", proj, "skipped",
                          "node_modules missing - install dependencies first, then re-run"))
        return []
    skip = {"hydration", "bundle", "rsc-boundary"}  # React quality checks, not security - 75% of results on a big app
    if "next" not in stacks:
        skip |= {"nextjs", "rsc-boundary"}
    if "react" not in stacks:
        skip |= {"hydration"}
    if mode == "deps":
        skip |= {"secrets", "code-security", "nextjs", "rsc-boundary", "hydration", "bundle", "source-maps"}
    out = raw / f"wsv-{re.sub(r'[^a-z0-9]+', '-', proj.lower())}.json"
    cmd = [npx, "-y", "-p", WSV, "web-secure-verify", "scan", "--path", pdir, "--format", "json", "--output", out]
    if skip:
        cmd += ["--skip", ",".join(sorted(skip))]
    _, _, err = run(cmd)
    if not out.exists():
        tools.append(tool("web-secure-verification", proj, "failed", tail(err)))
        return []
    found = norm_wsv(json.loads(out.read_text()), proj)
    tools.append(tool("web-secure-verification", proj, "ran", f"skipped scanners: {', '.join(sorted(skip)) or 'none'}",
                      len(found)))
    return found


def scan_bandit(root, proj, changed, tools):
    targets = [root / proj]
    if changed is not None:
        prefix = "" if proj == "." else proj + "/"
        targets = [root / f for f in changed if f.endswith(".py") and f.startswith(prefix)]
        if not targets:
            tools.append(tool("bandit", proj, "skipped", "no changed Python files"))
            return []
    # .claude/ holds this skill's own script once it is copied into the project.
    code, out, err = run([venv_bin("bandit"), "-f", "json", "-q", "-r", *targets, "-x",
                          "*/.venv/*,*/venv/*,*/node_modules/*,*/site-packages/*,*/.git/*,*/migrations/*,"
                          "*/.claude/*,*/.secure-review/*"])
    try:
        found = norm_bandit(json.loads(out), root)
    except ValueError:
        tools.append(tool("bandit", proj, "failed", tail(err)))
        return []
    tools.append(tool("bandit", proj, "ran", "", len(found)))
    return found


def scan_pip_audit(root, proj, tools):
    pdir = root / proj
    reqs = sorted(p.name for p in pdir.glob("requirements*.txt"))
    jobs = [(r, ["-r", pdir / r]) for r in reqs] or (
        [("pyproject.toml", [pdir])] if (pdir / "pyproject.toml").exists() else [])
    if not jobs:
        tools.append(tool("pip-audit", proj, "skipped", "no requirements*.txt or pyproject.toml"))
        return []
    found = []
    for name, args in jobs:
        code, out, err = run([venv_bin("pip-audit"), *args, "-f", "json", "--progress-spinner", "off"])
        try:
            got = norm_pip_audit(json.loads(out), proj, name)
        except ValueError:
            tools.append(tool("pip-audit", f"{proj}/{name}", "failed", tail(err)))
            continue
        tools.append(tool("pip-audit", f"{proj}/{name}", "ran", "", len(got)))
        found += got
    return found


def scan_osv(root, tools):
    try:
        exe = ensure_osv()
    except Exception as e:
        tools.append(tool("osv-scanner", ".", "failed", str(e)))
        return []
    code, out, err = run([exe, "scan", "source", "-r", root, "--format", "json"], timeout=1800)
    try:
        found = norm_osv(json.loads(out), root)
    except ValueError:
        no_lock = "no package sources" in (err or "").lower()  # composer.json without composer.lock, etc.
        tools.append(tool("osv-scanner", ".", "skipped" if no_lock else "failed",
                          "no lockfile found (composer.lock / Podfile.lock) - generate one and re-run" if no_lock else tail(err)))
        return []
    tools.append(tool("osv-scanner", ".", "ran", "Composer, CocoaPods", len(found)))
    return found


def scan_semgrep(root, stacks, changed, tools):
    # Only registry packs verified to exist: an unknown pack fails the whole semgrep run.
    packs = {"python": "p/python", "django": "p/django", "flask": "p/flask", "react": "p/react",
             "next": "p/nextjs", "node": "p/nodejs", "node-api": "p/expressjs", "docker": "p/dockerfile",
             "php": "p/php", "ios": "p/swift"}
    configs = ["p/owasp-top-ten", *sorted({packs[s] for s in stacks if s in packs})]
    targets = ["."]
    if changed is not None:
        targets = sorted(changed)
        if not targets:
            tools.append(tool("semgrep", ".", "skipped", "no changed files"))
            return []
    cmd = [venv_bin("semgrep"), "scan", "--json", "--quiet", "--metrics=off", "--timeout", "20",
           "--exclude", ".claude", "--exclude", ".secure-review"]
    for c in configs:
        cmd += ["--config", c]
    # shortcut: one semgrep call with every changed file as an argument; batch it if a diff ever hits ARG_MAX.
    code, out, err = run(cmd + targets, cwd=root, timeout=3600)
    try:
        data = json.loads(out)
    except ValueError:
        tools.append(tool("semgrep", ".", "failed", tail(err)))
        return []
    found = norm_semgrep(data)
    tools.append(tool("semgrep", ".", "ran", f"rulesets: {', '.join(configs)}", len(found)))
    return found


def scan_gitleaks(root, mode, changed, is_git, tools, raw, base=None):
    try:
        exe = ensure_gitleaks()
    except Exception as e:
        tools.append(tool("gitleaks", ".", "failed", str(e)))
        return []
    out = raw / "gitleaks.json"
    args = lambda o: ["--redact", "--no-banner", "--report-format", "json", "--report-path", o, "--exit-code", "0"]

    def scan(cmd, report):
        run(cmd, timeout=3600)
        return json.loads(report.read_text() or "[]") if report.exists() else None

    found, notes = [], []
    if changed is None:
        cmd, note = ([exe, "git", root, *args(out)], "full git history") if is_git else \
                    ([exe, "dir", root, *args(out)], "working tree (not a git repo)")
        data = scan(cmd, out)
        if data is None:
            tools.append(tool("gitleaks", ".", "failed", "no report written"))
            return []
        found, notes = norm_gitleaks(data, root), [note]
    else:
        if changed:
            # Copy only changed files so the scan covers uncommitted work without walking the whole tree.
            src = Path(tempfile.mkdtemp(dir=raw))
            for f in changed:
                (src / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / f, src / f)
            data = scan([exe, "dir", src, *args(out)], out)
            found += norm_gitleaks(data or [], src)
            shutil.rmtree(src, ignore_errors=True)
            notes.append("changed files incl. uncommitted")
        if is_git and base:  # a key committed then deleted on this branch is still live
            hist = raw / "gitleaks-branch.json"
            data = scan([exe, "git", root, *args(hist), "--log-opts", f"{base}..HEAD"], hist)
            found += norm_gitleaks(data or [], root)
            notes.append("commits since base")
        if not notes:
            tools.append(tool("gitleaks", ".", "skipped", "no changed files"))
            return []
    tools.append(tool("gitleaks", ".", "ran", " + ".join(notes), len(found)))
    return found


def cmd_scan(a):
    root = Path(a.root).resolve()
    out = Path(a.out).resolve() if a.out else root / ".secure-review" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    is_git = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root)[0] == 0
    if is_git:
        exclude_output(root)
    mode, base, changed, notes = a.mode, a.base, None, []
    if mode == "diff":
        base = base or (default_base(root) if is_git else None)
        if base:
            changed = changed_files(root, base)
        else:
            mode = "full"
            notes.append("no git base branch found - ran a full scan instead of diff")
    projects = detect(root)
    stacks = set().union(*(p["stacks"] for p in projects)) if projects else set()
    if not stacks:
        notes.append("no known stack detected - " + ("no dependency manifest found" if mode == "deps" else
                     "ran only the language-agnostic tools (semgrep OWASP rules, gitleaks)"))
    tools, found = [], []

    def py_ready():
        try:
            return ensure_py_tools(tools)
        except Exception as e:
            tools.append(tool("python-tools", ".", "failed", f"{type(e).__name__}: {e}"[:200]))
            return False

    for p in projects:
        if "node" in p["stacks"]:
            found += guarded("web-secure-verification", p["path"], tools, scan_wsv, root, p["path"],
                             set(p["stacks"]), mode, tools, raw)
        if "python" in p["stacks"] and py_ready():
            if mode != "deps":
                found += guarded("bandit", p["path"], tools, scan_bandit, root, p["path"], changed, tools)
            found += guarded("pip-audit", p["path"], tools, scan_pip_audit, root, p["path"], tools)
    if stacks & OSV_STACKS:
        found += guarded("osv-scanner", ".", tools, scan_osv, root, tools)
    if mode != "deps":
        if py_ready():
            found += guarded("semgrep", ".", tools, scan_semgrep, root, stacks, changed, tools)
        found += guarded("gitleaks", ".", tools, scan_gitleaks, root, mode, changed, is_git, tools, raw, base)
    found = [f for f in found if not re.match(r"(.*/)?\.(claude|secure-review)/", f.get("file") or "")]
    if is_git:
        ignored = git_ignored(root, {f["file"] for f in found if f.get("file")})
        if ignored:
            found = [f for f in found if f.get("file") not in ignored]
            notes.append(f"dropped findings in {len(ignored)} git-ignored file(s) (build output, local files)")
    out_of_scope = 0
    if changed is not None:
        deps_changed = any(MANIFESTS.search(f) for f in changed)
        kept = [f for f in found if in_scope(f, changed, deps_changed)]
        out_of_scope, found = len(found) - len(kept), kept
    found.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["file"] or "", f["line"] or 0))
    for n, f in enumerate(found, 1):
        f["id"] = f"F{n:03d}"
    meta = {"project": root.name, "root": str(root), "date": datetime.datetime.now().isoformat(timespec="minutes"),
            "mode": mode, "base": base, "changedFiles": sorted(changed) if changed is not None else None,
            "projects": projects, "stacks": sorted(stacks), "outOfScope": out_of_scope, "notes": notes}
    (out / "scan.json").write_text(json.dumps({"meta": meta, "tools": tools, "findings": found}, indent=1))
    counts = {s: sum(f["severity"] == s for f in found) for s in SEVERITIES}
    print(f"out: {out}\nmode: {mode}  base: {base}  stacks: {', '.join(sorted(stacks)) or 'none detected'}")
    if changed is not None:
        print(f"changed files: {len(changed)}  findings outside the diff (not shown): {out_of_scope}")
    for t in tools:
        print(f"  {t['status']:<8} {t['tool']:<24} {t['project']:<20} {t['count']:>4}  {t['note'][:90]}")
    print("findings: " + "  ".join(f"{s} {c}" for s, c in counts.items()))
    for n in notes:
        print(f"note: {n}")


# ---- report ---------------------------------------------------------------

def merge(scan, review):
    verdicts, rules = review.get("verdicts", {}), review.get("rules", {})
    findings = []
    added = [{"id": f"A{n:03d}", "status": "confirmed", **finding("ai", "", "medium", ""), **x}
             for n, x in enumerate(review.get("added", []), 1)]
    for f in scan["findings"] + added:
        v = verdicts.get(f.get("id")) or rules.get(f"{f['source']}:{f['rule']}") or {}
        f = {**f, "status": v.get("status", f.get("status", "unverified")), "note": v.get("note", f.get("note", ""))}
        if v.get("severity") in SEVERITIES:
            f["severity"] = v["severity"]
        f.update({k: v[k] for k in ("title", "fix") if v.get(k)})  # readable wording for raw scanner output
        findings.append(f)
    findings.sort(key=lambda f: (SEVERITIES.index(f["severity"]), f.get("file") or "", f.get("line") or 0))
    return findings


def rating(shown):
    sec = [f for f in shown if f.get("category", "security") == "security" and f["status"] == "confirmed"]
    for sev, label in (("critical", "Critical"), ("high", "High"), ("medium", "Moderate"), ("low", "Low")):
        if any(f["severity"] == sev for f in sec):
            return label
    return "No confirmed issues"


def render(scan, review, findings):
    e = lambda s: html.escape(str(s if s is not None else ""))
    meta, summary = scan["meta"], review.get("summary", {})
    shown = [f for f in findings if f["status"] != "false-positive"]
    security = [f for f in shown if f.get("category", "security") == "security"]
    other = [f for f in shown if f.get("category", "security") != "security"]
    risk = rating(shown)
    paras = lambda t: "".join(f"<p>{e(p)}</p>" for p in str(t or "").split("\n\n") if p.strip())
    counts = "".join(f'<div class="tile sev-{s}"><b>{sum(f["severity"] == s for f in security)}</b>{s}</div>'
                     for s in SEVERITIES[:4])
    owasp_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td><td>{n or '-'}</td></tr>"
        for k, v in OWASP.items() for n in [sum(f.get("owasp") == k for f in security)])
    unmapped = sum(not f.get("owasp") for f in security)
    tool_rows = "".join(f"<tr><td>{e(t['tool'])}</td><td>{e(t['project'])}</td>"
                        f"<td class='st-{e(t['status'])}'>{e(t['status'])}</td><td>{t['count']}</td>"
                        f"<td>{e(t['note'])}</td></tr>" for t in scan["tools"])
    loc = lambda f: f"{f['file']}:{f['line']}" if f.get("file") and f.get("line") else (f.get("file") or "dependency")

    def cards(items):
        return "".join(
            f"<article class='finding sev-{f['severity']}'><header><span class='sev'>{f['severity']}</span>"
            f"<h4>{e(f['title'])}</h4><span class='status st-{e(f['status'])}'>{e(f['status'])}</span></header>"
            f"<p class='loc'><code>{e(loc(f))}</code> · {e(f['source'])} · {e(f.get('owasp') or 'unmapped')}"
            f"{' · ' + e(f['cwe']) if f.get('cwe') else ''} · {e(f.get('id', ''))}</p>"
            f"{'<p>' + e(f['detail']) + '</p>' if f.get('detail') else ''}"
            f"{'<p><b>Reviewer:</b> ' + e(f['note']) + '</p>' if f.get('note') else ''}"
            f"{'<p><b>Fix:</b> ' + e(f['fix']) + '</p>' if f.get('fix') else ''}</article>" for f in items) \
            or "<p class='muted'>None.</p>"

    roadmap = [("Fix before release", ["critical", "high"]), ("Next sprint", ["medium"]), ("Backlog", ["low", "info"])]
    road = "".join(f"<li><b>{label}</b> - {sum(f['severity'] in sevs for f in security)} finding(s)</li>"
                   for label, sevs in roadmap)
    fp = sum(f["status"] == "false-positive" for f in findings)
    scope = (f"Changes against <code>{e(meta['base'])}</code> ({len(meta['changedFiles'] or [])} files)"
             if meta["mode"] == "diff" else "Whole repository" if meta["mode"] == "full" else "Dependencies only")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Security Review - {e(meta['project'])}</title>
<style>
:root{{--bg:#fff;--fg:#1b1f24;--muted:#5b6470;--line:#d9dee4;--card:#f6f8fa;--crit:#b42318;--high:#c4320a;--med:#9a6700;--low:#3b6fb6;--ok:#1a7f37}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1216;--fg:#e6e9ed;--muted:#9aa4af;--line:#2b323a;--card:#171b21;--crit:#ff7b72;--high:#ffa657;--med:#e3b341;--low:#79c0ff;--ok:#56d364}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:960px;margin:0 auto;padding:32px 16px 64px}}h1{{margin:0 0 4px;font-size:26px}}h2{{margin:40px 0 12px;font-size:19px;border-bottom:1px solid var(--line);padding-bottom:6px}}
.muted,.loc{{color:var(--muted)}}.risk{{display:inline-block;margin:12px 0;padding:6px 14px;border-radius:6px;background:var(--card);border:1px solid var(--line);font-weight:600}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}}.tile{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;text-transform:capitalize}}
.tile b{{display:block;font-size:26px}}table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
.tablewrap{{overflow-x:auto}}.finding{{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:6px;padding:12px 14px;margin:10px 0}}
.finding header{{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}}.finding h4{{margin:0;flex:1;font-size:15px}}.finding p{{margin:6px 0;overflow-wrap:anywhere}}
.sev{{text-transform:uppercase;font-size:12px;font-weight:700}}.status{{font-size:12px;color:var(--muted)}}
.sev-critical{{border-left-color:var(--crit)}}.sev-critical .sev,.tile.sev-critical b{{color:var(--crit)}}.sev-high{{border-left-color:var(--high)}}.sev-high .sev,.tile.sev-high b{{color:var(--high)}}
.sev-medium{{border-left-color:var(--med)}}.sev-medium .sev,.tile.sev-medium b{{color:var(--med)}}.sev-low,.sev-info{{border-left-color:var(--low)}}.sev-low .sev,.tile.sev-low b{{color:var(--low)}}
.st-ran,.st-confirmed{{color:var(--ok)}}.st-failed{{color:var(--crit)}}code{{font-size:13px}}
@media print{{body{{background:#fff;color:#000}}.finding{{break-inside:avoid}}}}
</style></head><body><main>
<h1>Security Review: {e(meta['project'])}</h1>
<p class="muted">{e(meta['date'])} · Scope: {scope} · Stack: {e(', '.join(meta['stacks']) or 'not detected')}</p>
<div class="risk">Overall risk: {e(risk)}</div>
<h2>Executive summary</h2>{paras(summary.get('executive')) or '<p class="muted">Not written.</p>'}
<div class="tiles">{counts}</div>
<h2>Remediation roadmap</h2><ul>{road}</ul>
<h2>OWASP Top 10 (2021) coverage</h2><div class="tablewrap"><table><tr><th>ID</th><th>Category</th><th>Findings</th></tr>{owasp_rows}</table></div>
<p class="muted">{unmapped} finding(s) not mapped to a category. A category with no findings was checked but is not proven secure; see the checks below.</p>
<h2>Findings</h2>{cards(security)}
<h2>Compliance and quality</h2>{cards(other)}
<h2>Checks run</h2><div class="tablewrap"><table><tr><th>Tool</th><th>Project</th><th>Status</th><th>Raw</th><th>Notes</th></tr>{tool_rows}
<tr><td>AI code review</td><td>.</td><td class="st-{'ran' if review else 'skipped'}">{'ran' if review else 'skipped'}</td><td>{len(review.get('added', []))}</td><td>Access control, session, injection, SSRF/CSRF, platform checks the scanners cannot see</td></tr></table></div>
<h2>Scope and limitations</h2>{paras(summary.get('scope'))}{paras(summary.get('limitations'))}
<p class="muted">{fp} scanner result(s) were reviewed and dismissed as false positives.{f" {meta['outOfScope']} pre-existing result(s) outside the changed files are excluded." if meta['outOfScope'] else ''}
Unverified findings were not individually confirmed by a reviewer.</p>
</main></body></html>"""


# Matched against rule ids only: titles like "token stored in localStorage" are not about a literal secret.
SECRET_HINT = re.compile(r"secret|password|passwd|credential|api.?key|private.?key|hard.?code|B10[567]", re.I)


def secret_literals(root, findings):
    """String literals on lines flagged as secrets, so no report text can repeat them."""
    values = set()
    for f in findings:
        if not (f.get("file") and f.get("line")) or not (
                f["source"] == "gitleaks" or SECRET_HINT.search(f.get("rule") or "")):
            continue
        try:
            line = (Path(root) / f["file"]).read_text(encoding="utf-8", errors="ignore").splitlines()[f["line"] - 1]
        except (OSError, IndexError):
            continue
        # Skip routes, paths and prose so the report stays readable.
        values |= {v for v in re.findall(r"""["'`]([^"'`\s]{3,})["'`]""", line) if not v.startswith(("/", ".", "http"))}
    return values


def redact(value, secrets):
    if isinstance(value, dict):
        return {k: redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for s in sorted(secrets, key=len, reverse=True):
            value = re.sub(rf"(?<!\w){re.escape(s)}(?!\w)", "[redacted]", value)
    return value


def cmd_report(a):
    d = Path(a.dir).resolve()
    scan = json.loads((d / "scan.json").read_text())
    review = json.loads((d / "review.json").read_text()) if (d / "review.json").exists() else {}
    merged = merge(scan, review)  # fills defaults such as source="ai" on findings the review added
    secrets = secret_literals(scan["meta"]["root"], merged)
    review = redact(review, secrets)
    findings = redact(merged, secrets)
    (d / "report.html").write_text(render(scan, review, findings), encoding="utf-8")
    shown = [f for f in findings if f["status"] in ("confirmed", "suspicion", "unverified")
             and f.get("category", "security") == "security"]
    print(f"report: {d / 'report.html'}\noverall risk: {rating(findings)}")
    for f in shown[:60]:
        loc = f"{f['file']}:{f['line']}" if f.get("file") else "dependency"
        tag = "" if f["status"] == "confirmed" else f" ({f['status']})"
        print(f"[{f['severity'].upper()}]{tag} {loc} - {f['title']} - {f.get('fix') or ''}"[:300])
    if len(shown) > 60:
        print(f"... {len(shown) - 60} more in the report")


# ---- self-check -----------------------------------------------------------

def cmd_selftest(_):
    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        (root / "web").mkdir()
        (root / "package.json").write_text('{"private":true,"workspaces":["web"]}')
        (root / "web/package.json").write_text('{"dependencies":{"next":"15.0.0","react-native":"0.76"}}')
        (root / "api").mkdir()
        (root / "api/requirements.txt").write_text("Django==4.2\n")
        (root / "node_modules/x").mkdir(parents=True)
        (root / "node_modules/x/package.json").write_text('{"dependencies":{"express":"4"}}')
        for d, f in (("cms", "composer.json"), ("web/ios", "Podfile"), ("svc", "Makefile")):
            (root / d).mkdir(exist_ok=True)
            (root / d / f).write_text("")
        got = {p["path"]: p["stacks"] for p in detect(root)}
        assert got == {"web": ["next", "node", "react", "react-native"], "api": ["django", "python"], "cms": ["php"],
                       "web/ios": ["ios"]}, got

    osv = {"results": [{"source": {"path": "/r/php/composer.lock"}, "packages": [
        {"package": {"name": "guzzlehttp/guzzle", "version": "7.4.0", "ecosystem": "Packagist"},
         "groups": [{"max_severity": "7.7"}, {"max_severity": "9.1"}],
         "vulnerabilities": [{"id": "GHSA-1", "aliases": ["CVE-2022-1"], "affected": [{"ranges": [{"events": [
             {"introduced": "0"}, {"fixed": "6.5.8"}]}, {"events": [{"introduced": "7.0.0"}, {"fixed": "7.4.5"}]}]}]},
             {"id": "GHSA-2", "aliases": [], "affected": [{"ranges": [{"events": [{"fixed": "7.4.3"}]}]}]}]},
        {"package": {"name": "left-pad", "version": "1.0.0", "ecosystem": "npm"},
         "vulnerabilities": [{"id": "x"}]}]}]}
    (f,) = norm_osv(osv, "/r")
    assert (f["severity"], f["file"]) == ("critical", None) and "to 7.4.5 or later" in f["fix"], f
    assert "php/composer.lock" in f["fix"] and "CVE-2022-1" in f["detail"] and "(2 advisories)" in f["title"], f
    assert MANIFESTS.search("cms/composer.lock") and MANIFESTS.search("ios/App/Podfile.lock")

    wsv = {"results": [{"scanner": "code-security", "issues": [
        {"id": "code-security-eval-usage-src/a.ts-2", "title": "Use of eval()", "severity": "critical",
         "file": "src/a.ts", "line": 2, "fix": "x", "description": 'Entropy 4.9. Value starts with: "ghp_aB3d..."'}]},
        {"scanner": "outdated", "issues": [{"id": "outdated-next", "title": "Outdated", "severity": "medium"}]}]}
    a, b = norm_wsv(wsv, "web")
    assert (a["file"], a["rule"], a["owasp"], a["category"]) == ("web/src/a.ts", "code-security:code-security-eval-usage", "A03", "security"), a
    assert "ghp_" not in a["detail"] and "redacted" in a["detail"], a
    assert (b["file"], b["category"]) == (None, "quality"), b
    assert version_at_least("8.30.1", (8, 19)) and not version_at_least("v8.18.4", (8, 19))

    bandit = {"results": [{"filename": "./app.py", "line_number": 4, "test_id": "B602", "issue_severity": "HIGH",
                           "issue_confidence": "LOW", "issue_cwe": {"id": 78}, "issue_text": "shell=True"}]}
    (f,) = norm_bandit(bandit, ".")
    assert (f["file"], f["severity"], f["owasp"], f["cwe"]) == ("app.py", "low", "A03", "CWE-78"), f

    pa = {"dependencies": [{"name": "django", "version": "3.2", "vulns": [
        {"id": "PYSEC-1", "fix_versions": ["3.2.2", "2.2.22"], "aliases": ["CVE-1"]},
        {"id": "PYSEC-2", "fix_versions": ["3.2.10"], "aliases": []}]}, {"name": "ok", "version": "1", "vulns": []}]}
    (f,) = norm_pip_audit(pa, "api", "requirements.txt")
    assert f["owasp"] == "A06" and "to 3.2.10 or later" in f["fix"] and "CVE-1" in f["detail"], f
    assert "(2 advisories)" in f["title"] and f["rule"] == "django", f

    sg = {"results": [{"check_id": "r", "path": "a.js", "start": {"line": 3}, "extra": {
        "severity": "ERROR", "message": "m", "metadata": {"owasp": ["A01:2017 - x", "A03:2021 - Injection"],
                                                         "cwe": ["CWE-79: XSS"]}}}]}
    (f,) = norm_semgrep(sg)
    assert (f["severity"], f["owasp"], f["cwe"]) == ("high", "A03", "CWE-79"), f

    (f,) = norm_gitleaks([{"RuleID": "aws", "Description": "AWS", "File": "/tmp/x/src/k.py", "StartLine": 1,
                           "Secret": "REDACTED"}], "/tmp/x")
    assert (f["file"], f["severity"]) == ("src/k.py", "critical"), f

    assert tail("Collecting x\nERROR: No matching distribution\nERROR:cli: ['/tmp/py', '-m']") == "ERROR: No matching distribution"
    assert tail("") == "no output" and tail("a\nb") == "b"

    changed = {"src/a.ts"}
    assert in_scope({"file": "src/a.ts"}, changed, False) and not in_scope({"file": "src/b.ts"}, changed, False)
    assert in_scope({"file": "gone.js", "source": "gitleaks", "detail": "Committed in abc12345."}, changed, False)
    assert not in_scope({"file": None}, changed, False) and in_scope({"file": None}, changed, True)
    assert MANIFESTS.search("apps/web/package.json") and not MANIFESTS.search("src/package.ts")

    scan = {"meta": {"project": "<p>", "date": "d", "mode": "full", "base": None, "changedFiles": None,
                     "stacks": [], "outOfScope": 0}, "tools": [],
            "findings": [{**finding("x", "r", "high", "<script>alert(1)</script>"), "id": "F001"},
                         {**finding("x", "r2", "low", "noise"), "id": "F002"}]}
    review = {"verdicts": {"F001": {"status": "confirmed", "title": "<script>alert(2)</script>", "fix": "Do X"}}, "rules": {"x:r2": {"status": "false-positive"}},
              "added": [finding("ai", "idor", "critical", "IDOR on /api/orders/[id]", "a.ts", 9, owasp="A01")]}
    merged = merge(scan, review)
    assert [(m["id"], m["status"]) for m in merged] == [
        ("A001", "confirmed"), ("F001", "confirmed"), ("F002", "false-positive")], merged
    assert (merged[1]["title"], merged[1]["fix"]) == ("<script>alert(2)</script>", "Do X"), merged[1]
    page = render(scan, review, merged)
    assert "<script>alert" not in page and "&lt;script&gt;" in page and "Overall risk: Critical" in page

    (f,) = norm_bandit({"results": [{"filename": "s.py", "line_number": 3, "test_id": "B105", "issue_severity": "LOW",
                                     "issue_text": "Possible hardcoded password: 'hunter22'", "code": "PW = 'hunter22'"}]}, ".")
    assert "hunter22" not in json.dumps(f), f
    with tempfile.TemporaryDirectory() as t:
        Path(t, "server.js").write_text('app.post("/login", (q, r) => jwt.sign(u, "secret123"));\n'
                                        'localStorage.setItem("accessToken", token);\n')
        found = [{**finding("semgrep", "hardcoded-credential", "high", "Hard-coded credential"), "file": "server.js", "line": 1},
                 {**finding("ai", "token-storage", "high", "Auth token in localStorage"), "file": "server.js", "line": 2}]
        secrets = secret_literals(t, found)
        assert secrets == {"secret123"}, secrets
        assert redact({"note": ["signed with 'secret123' via POST /login"]}, secrets) == \
            {"note": ["signed with '[redacted]' via POST /login"]}
    t = []
    assert guarded("x", ".", t, lambda: 1 / 0) == [] and t[0]["status"] == "failed" and "ZeroDivisionError" in t[0]["note"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--root", default=".")
    s.add_argument("--mode", choices=["diff", "full", "deps"], default="diff")
    s.add_argument("--base")
    s.add_argument("--out")
    r = sub.add_parser("report")
    r.add_argument("--dir", required=True)
    sub.add_parser("selftest")
    a = ap.parse_args()
    {"scan": cmd_scan, "report": cmd_report, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
