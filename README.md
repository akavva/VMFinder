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
- 🌐 **Connect to any number of vCenters** simultaneously (1 to many, configured via `.env`)
- 🛡️ **Disconnect NICs** (network adapters) from VMs for quick isolation during attacks
- ⚡ **Control VMs**: Power On, Reboot, Shutdown
- 🖥️ **User-friendly Web UI** (HTML + JavaScript + Flask API)
- 🔒 **Password-protected critical actions** using SHA-256 hashed credentials
- 📋 **Audit logging** — all destructive actions are logged to `vmfinder_audit.log`
- ♻️ **Live cache refresh** — rebuild VM inventory without restarting the server
- 📄 **Pagination** — handles large inventories cleanly (25 results per page)
- 🔋 **VM power state badges** — see Powered On / Off / Suspended at a glance

---

## 📋 Requirements

- Python 3.x
- `pyVmomi` (VMware vSphere SDK for Python)
- `Flask`
- `flask_cors`
- `python-dotenv`
- Access credentials for your vCenters

---

## 🛠️ Installation

```bash
git clone https://github.com/akavva/VMFinder.git
cd VMFinder
pip install -r requirements.txt
```

---

## ⚙️ Configuration

### 1. Create your `.env` file

Create a file named `.env` in the same directory as `VMFinder.py`. Add one block per vCenter, numbered sequentially starting from 1. There is no upper limit — add as many as you need.

```env
VC1_NAME=vcenter1.yourdomain.local
VC1_IP=10.0.0.1
VC1_USER=administrator@vsphere.local
VC1_PASS=yourpassword
VC1_PORT=443

VC2_NAME=vcenter2.yourdomain.local
VC2_IP=10.0.0.2
VC2_USER=administrator@vsphere.local
VC2_PASS=yourpassword
VC2_PORT=443

VC3_NAME=vcenter3.yourdomain.local
VC3_IP=10.0.0.3
VC3_USER=administrator@vsphere.local
VC3_PASS=yourpassword
VC3_PORT=443
```

> The app reads `VC1_IP`, `VC2_IP`, `VC3_IP`... and stops at the first missing index. Keep numbering sequential with no gaps.

**Never commit your `.env` file to source control.** Add it to `.gitignore`:
```
.env
```

### 2. Set the admin password hash

VMFinder does not store your password in plaintext. Generate a SHA-256 hash of your chosen password by running this once in any terminal:

```bash
python -c "import hashlib; print(hashlib.sha256(b'yourpassword').hexdigest())"
```

Copy the output and set it as an environment variable in your `.env`:

```env
VMFINDER_ADMIN_HASH=paste_your_hash_here
```

This hash is used to authenticate all protected actions (NIC isolation, VM power control, cache refresh).

---

## 🚀 Usage

Start the Flask app:

```bash
python VMFinder.py
```

By default it runs on `http://0.0.0.0:5000`. Open your browser and navigate to the VMFinder web interface.

---

## 🔍 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/search?query=<text>&page=<n>&per_page=<n>` | Search VMs by partial/full IP, MAC, or name |
| `POST` | `/disconnect` | Isolate a NIC from a VM (password-protected) |
| `POST` | `/control_vm` | Power on, reboot, or shut down a VM (password-protected) |
| `POST` | `/refresh_cache` | Rebuild the VM inventory cache from all vCenters (password-protected) |

---

## 📁 Project Structure

```
VMFinder/
├── VMFinder.py          # Flask backend
├── .env                 # Your credentials (never commit this)
├── vmfinder_audit.log   # Created automatically on first run
└── templates/
    ├── index.html       # Web UI
    └── static/
        └── favicon.ico
```

---

## ⚠️ Notes

- **SSL verification** is disabled (`ssl._create_unverified_context()`) to support self-signed vCenter certificates. Review this for production use.
- **CORS** is enabled for all routes.
- All destructive actions are **rate-limited** to 10 requests per minute per IP.
- Audit logs are written to `vmfinder_audit.log` in the app directory.
- This uses Flask's built-in development server. For production, run behind a proper WSGI server (e.g. `gunicorn` or `waitress`).

---

## 🤝 Contributing

Contributions are welcome!  
Please open an issue or a pull request to improve detection accuracy, code quality, or security.