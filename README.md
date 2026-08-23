# 🌐 VMFinder

VMFinder is a high-performance, lightweight Flask web application designed for system administrators and security incident responders. It provides a unified dashboard to instantly locate, inspect, and manage virtual machines across multiple VMware vCenter instances simultaneously.

During active security incidents, VMFinder enables authorized personnel to instantly isolate compromised infrastructure by safely disconnecting virtual network adapters (NICs) or managing power states straight from the browser UI.

---

## ✨ Features

* **⚡ Ultra-Fast Search Matrix:** Instantly search through thousands of assets by:
  * Full or partial **VM Name**
  * Full or partial **IP Address**
  * Full or partial **MAC Address**
* **🌐 Multi-vCenter Aggregation:** Query multiple vCenter environments simultaneously into a single search grid.
* **🚀 Server-Side API Property Collection:** Utilizes highly optimized VMware `PropertyCollector` batching to index hundreds of VMs in seconds instead of sequential polling.
* **🛡️ Rapid Incident Isolation:** Disconnect virtual network adapters instantly to quarantine infected machines from the rest of the corporate network.
* **🔌 Power State Control:** Issue execution signals (`Power On`, `Reboot`, `Shutdown`) directly from the search cards.
* **🔒 Obfuscated Access Safeguards:** Critical operational infrastructure endpoints require explicit administrative authentication verified securely on the backend server.

---

## 📋 Prerequisites & Requirements

* **VMware vSphere Environment** (vCenter access credentials)
* Either:
  * **Windows:** no prerequisites — just the standalone `vmfinder.exe` (see below), or
  * **Python 3.8+** if running from source, with:
    * `pyvmomi` (Official VMware vSphere SDK for Python)
    * `Flask`
    * `flask-cors`

---

## 💻 Windows: Standalone Executable

No Python install, no `pip install`, no manual config file editing. Download `vmfinder.exe` and double-click it (or run it from a terminal).

On first run it launches an interactive setup wizard that asks for an admin password and your vCenter(s) (name, IP/FQDN, username, password, port), then saves that configuration to `%USERPROFILE%\.config\vmfinder\config.env` so future launches start up silently.

To change the saved vCenters or admin password later, run:
```powershell
vmfinder.exe --reconfigure
```

Once running, open **`http://localhost:5000`** in a browser.

> Building `vmfinder.exe` yourself: run `build.bat` on a Windows machine (PyInstaller does not cross-compile, so this can't be built from Linux/macOS). It bundles Python, Flask and pyVmomi into a single `dist\vmfinder.exe` — see [`build.bat`](build.bat).

---

## 🛠️ Installation & Setup (running from source)

### 1. Clone the Repository
```bash
git clone https://github.com/akavva/VMFinder.git
cd VMFinder

```

### 2. Configure Virtual Environment & Dependencies

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment (Windows)
.venv\Scripts\activate

# Install required dependencies
pip install -r requirements.txt

```

### 3. Application Configuration

Configuration is not hardcoded — it's resolved from environment variables, a saved config file, or an interactive setup wizard (in that order). The wizard runs automatically the first time you start the app if no configuration is found:

```bash
python VMFinder.py                 # first run launches the setup wizard
python VMFinder.py --reconfigure   # re-run the wizard, replacing saved config
```

It asks for an admin password (required to confirm VM power actions / cache refresh) and one or more vCenters (name, IP/FQDN, username, password, port), then saves them to `~/.config/vmfinder/config.env`.

To configure non-interactively instead (e.g. for automated deployments), set these environment variables directly: `VMFINDER_ADMIN_HASH` (sha256 hash of the admin password — generate with `python -c "import hashlib; print(hashlib.sha256(b'mypassword').hexdigest())"`), then `VC1_NAME`, `VC1_IP`, `VC1_USER`, `VC1_PASS`, `VC1_PORT` for each vCenter (`VC2_*`, `VC3_*`, ... for additional ones).

> 💡 **Security Best Practice:** Ensure the vCenter service account is configured with the *Principle of Least Privilege* (only allow VM interaction power states and device modification roles).

---

## 🚀 Usage

1. **Launch the Flask Web App Server:**
```bash
python VMFinder.py

```


2. **Access the Application Interface:**
Open your preferred browser and navigate to:
👉 **`http://localhost:5000`** *(or your host's external network IP address on Port 5000)*

---

## 🔍 API Architecture Reference

| Method | Endpoint | Description | Auth Required |
| --- | --- | --- | --- |
| **`GET`** | `/` | Renders the primary search dashboard interface. | No |
| **`GET`** | `/search?query=<text>` | Queries the memory cache map array for matching string patterns. | No |
| **`POST`** | `/disconnect` | Payload: `{ "vm_name": "x", "adapter_name": "y", "password": "z" }` — Disconnects network device cards. | **Yes** |
| **`POST`** | `/control_vm` | Payload: `{ "vm_name": "x", "action": "power_on|reboot|shutdown", "password": "z" }` | **Yes** |
| **`POST`** | `/refresh_cache` | Payload: `{ "password": "z" }` — Rebuilds the in-memory VM cache from all connected vCenters. | **Yes** |

---

## ⚠️ Notes & Security Considerations

* **SSL Handshake Overrides:** By design, the script uses `ssl._create_unverified_context()` to handle self-signed internal corporate vCenter certificates without crashing execution chains.
* **Network Isolation Deployment:** If hosting this tool to a wide infrastructure management team, it is highly recommended to run the app behind a secure reverse proxy (like Nginx) wrapping the session inside **HTTPS** to encrypt client authentication payloads across the wire.

---

## 🤝 Contributing

Contributions are welcome! If you want to build out the UI layout badges, or improve detection parameters, please open an Issue or submit a Pull Request
