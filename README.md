# VMFinder

VMFinder is a lightweight Flask app for locating and managing VMs across multiple VMware vCenter instances at once. Search by VM name, IP, or MAC across all connected vCenters, then disconnect a NIC or change power state straight from the browser — built for incident responders who need to isolate a compromised machine fast.

---

## Requirements

* Access credentials for one or more vCenter servers.
* **Windows:** the `.exe` from [Releases](https://github.com/akavva/VMFinder/releases/latest) — nothing else to install.
* **Linux:** the `-linux-x86_64` binary from [Releases](https://github.com/akavva/VMFinder/releases/latest). Needs glibc 2.28+ (RHEL/Rocky/Alma 8+, Ubuntu 20.04+, Debian 10+).

---

## Quick start

1. Download the binary for your OS from the [latest release](https://github.com/akavva/VMFinder/releases/latest).
2. **Windows:** just run it. Allow it through Windows Firewall when prompted (or add the rule yourself: `netsh advfirewall firewall add rule name="VMFinder" dir=in action=allow protocol=TCP localport=5000`).
   **Linux:** `chmod +x vmfinder-*-linux-x86_64 && ./vmfinder-*-linux-x86_64`. Open port 5000 if you need to reach it from another machine: `sudo firewall-cmd --add-port=5000/tcp --permanent && sudo firewall-cmd --reload` (RHEL/Rocky) or `sudo ufw allow 5000/tcp` (Debian/Ubuntu).
3. First run walks you through a setup wizard — admin password, then your vCenter(s) (name, IP/FQDN, username, password, port). It tests each connection live before saving.
4. Open **http://localhost:5000** in a browser.

Re-run with `--reconfigure` to change the saved vCenters or admin password later.

Prefer to build it yourself? `build.bat` (Windows) or `./build.sh` (Linux) — see [Running from source](#running-from-source).

---

## Running from source

```bash
git clone https://github.com/akavva/VMFinder.git
cd VMFinder
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python VMFinder.py             # first run launches the setup wizard
```

`python VMFinder.py --reconfigure` re-runs the wizard and replaces the saved config.

For non-interactive/automated deployments, skip the wizard by setting environment variables directly: `VMFINDER_ADMIN_HASH` (sha256 of the admin password — generate with `python -c "import hashlib; print(hashlib.sha256(b'mypassword').hexdigest())"`), then `VC1_NAME`, `VC1_IP`, `VC1_USER`, `VC1_PASS`, `VC1_PORT` per vCenter (`VC2_*`, `VC3_*`, ... for more).

Open **http://localhost:5000** in a browser once it's running.

---

## API Reference

| Method | Endpoint | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/` | Search dashboard. | No |
| `GET` | `/search?query=<text>` | Search the cached VM data by name/IP/MAC. | No |
| `POST` | `/disconnect` | `{ "vm_name", "adapter_name", "password" }` — disconnects a NIC. | Yes |
| `POST` | `/control_vm` | `{ "vm_name", "action": "power_on\|reboot\|shutdown", "password" }` | Yes |
| `POST` | `/refresh_cache` | `{ "password" }` — rebuilds the VM cache from all connected vCenters. | Yes |

---

## Security notes

* The app disables SSL certificate verification (`ssl._create_unverified_context`) to tolerate self-signed internal vCenter certs — this affects the whole process.
* The admin password is a single shared secret gating all mutating actions, not per-user auth. If exposing this beyond localhost, put it behind a reverse proxy with HTTPS.

---

## Contributing

Issues and pull requests welcome.
