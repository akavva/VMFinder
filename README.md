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

No Python install and no `pip install` needed. Download `vmfinder.exe`, place it next to a `.env` file configured as described in [Application Configuration](#3-application-configuration) below, and run it (double-click, or from a terminal).

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

Open `VMFinder.py` and configure your cluster target matrix inside the `vcenter_servers` block:

```python
vcenter_servers = [
    {
        'name': 'Production-vCenter-01', # Your actual VCENTER name or mnemonic
        'hostname': '192.168.1.100', # Your vCenter IP or FQDN
        'username': 'VCENTER_account', # Administartor or other account with adequate priliveges
        'password': 'VCENTER_PASSWORD',
        'port': 443
    }
]

```

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
| **`POST`** | `/validate_password` | Evaluates client authentication sequences using constant-time evaluation mechanisms. | **Yes** |

---

## ⚠️ Notes & Security Considerations

* **SSL Handshake Overrides:** By design, the script uses `ssl._create_unverified_context()` to handle self-signed internal corporate vCenter certificates without crashing execution chains.
* **Network Isolation Deployment:** If hosting this tool to a wide infrastructure management team, it is highly recommended to run the app behind a secure reverse proxy (like Nginx) wrapping the session inside **HTTPS** to encrypt client authentication payloads across the wire.

---

## 🤝 Contributing

Contributions are welcome! If you want to build out the UI layout badges, or improve detection parameters, please open an Issue or submit a Pull Request
