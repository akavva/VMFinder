# VMFinder

VMFinder is a lightweight Flask app for locating and managing VMs across multiple VMware vCenter instances at once. Search by VM name, IP, or MAC across all connected vCenters, then disconnect a NIC or change power state straight from the browser — built for incident responders who need to isolate a compromised machine fast.

---

## Requirements

* Access credentials for one or more vCenter servers.
* **Windows:** nothing — just the `vmfinder.exe` from [Releases](https://github.com/akavva/VMFinder/releases).
* **Linux/macOS:** Python 3.8+ to run from source.

---

## Windows quick start

1. Download `vmfinder.exe` from the [Releases page](https://github.com/akavva/VMFinder/releases/latest) and run it.
2. On first run it walks you through a setup wizard — admin password, then your vCenter(s) (name, IP/FQDN, username, password, port). It tests each vCenter connection live and lets you fix any typos before saving.
3. **Allow the app through Windows Firewall.** Windows may prompt you to allow it automatically the first time it runs — click **Allow**. If it doesn't prompt (e.g. a locked-down machine), add the rule yourself in an elevated PowerShell:
   ```powershell
   netsh advfirewall firewall add rule name="VMFinder" dir=in action=allow protocol=TCP localport=5000
   ```
4. Open **http://localhost:5000** in a browser.

To change the saved vCenters or admin password later: `vmfinder.exe --reconfigure`.

> Prefer to build it yourself instead of using the release binary? Install [Python 3.8+](https://www.python.org/downloads/windows/) (check "Add python.exe to PATH"), clone this repo, and run `build.bat` — it creates a virtual environment, installs dependencies, and produces `dist\vmfinder.exe`. PyInstaller doesn't cross-compile, so this has to run on Windows.

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
