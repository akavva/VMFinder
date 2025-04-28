# VMFinder

**VMFinder** is a lightweight Flask-based tool that allows administrators to search, locate, and manage virtual machines across multiple vCenters.  
You can search VMs by **full or partial** IP address, MAC address, or VM name, and **securely disconnect** network adapters to quickly isolate compromised systems during security incidents.  

A simple web interface is provided to make searches and operations fast and intuitive.

---

## ✨ Features
- 🔍 **Search VMs** by:
  - Full or partial **IP address**
  - Full or partial **MAC address**
  - Full or partial **VM name**
- 🌐 **Connect to multiple vCenters** simultaneously
- 🛡️ **Disconnect NICs** (network adapters) from VMs for quick isolation during attacks
- ⚡ **Control VMs**:
  - Power On
  - Reboot
  - Shutdown
- 🖥️ **User-friendly Web UI** (HTML + JavaScript + Flask API)
- 🔒 **Password-protected critical actions** (disconnecting NICs or controlling VMs)

---

## 📋 Requirements
- Python 3.x
- `pyVmomi` (VMware vSphere SDK for Python)
- `Flask`
- `flask_cors`
- Access credentials for the vCenters

---

## 🛠️ Installation

```bash
git clone https://github.com/akavva/VMFinder.git
cd vmfinder
pip install -r requirements.txt
```

> Update the Flask app paths app = Flask(__name__, template_folder=r'PATH_TO_TEMPLATES_FOLDER', static_folder=r'PATH_TO_STATIC_FOLDER')
> **Note:** Adjust the `vcenter_servers` list inside `VMFinder.py` with your real vCenter IPs/FQDNs and credentials.  
> Also, replace `<your_password_here>` in the code with your real authorization password in both .py and index files.

---

## 🚀 Usage

Start the Flask app:

```bash
python VMFinder.py
```

By default, it runs on `http://0.0.0.0:80/`.

Then open your browser and access the **VMFinder** web interface.

---

## 🔍 API Endpoints

- `GET /search?query=<text>`  
  Search for VMs using partial/full IP, MAC, or VM name.

- `POST /disconnect?vm_name=<name>&adapter_name=<adapter>`  
  Disconnect the specified network adapter from a VM (password-protected).

- `POST /control_vm`  
  Control the VM (power on, reboot, shutdown) (password-protected).

---

## 📷 Screenshots

| Search VM | Disconnect NIC | Power Controls |
|:----------|:---------------|:--------------|
| ![Search Example](https://via.placeholder.com/300x150?text=Search+VM) | ![Disconnect Example](https://via.placeholder.com/300x150?text=Disconnect+NIC) | ![Control Example](https://via.placeholder.com/300x150?text=Control+VM) |

> *You can replace these placeholders with your real screenshots.*

---

## ⚠️ Notes
- **CORS** is enabled for all routes.
- **SSL verification** is disabled (`ssl._create_unverified_context()` is used).
- Ensure your firewall allows connections to port 80 if you access the server externally.
- Use **strong passwords** when setting up access control.
- Review security best practices if deploying in production environments.
