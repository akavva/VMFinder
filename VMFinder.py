from dotenv import load_dotenv, dotenv_values
load_dotenv()
import os
import sys
import ssl
import argparse
import getpass
import threading
import hashlib
import secrets
import time
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from functools import wraps
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from _version import VERSION

# ---------------------------------------------------------------------------
# Paths — when run as a PyInstaller onefile binary, bundled data (templates/)
# lives in the extracted temp dir (sys._MEIPASS); persistent files (config,
# audit log) live in the user's config dir so they survive across runs
# regardless of where the binary is launched from or that its bundle dir is
# ephemeral.
# ---------------------------------------------------------------------------
BASE_DIR    = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR  = os.environ.get('VMFINDER_HOME', os.path.join(os.path.expanduser('~'), '.config', 'vmfinder'))
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.env')
os.makedirs(CONFIG_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(CONFIG_DIR, 'vmfinder_audit.log'))
    ]
)
log = logging.getLogger('VMFinder')

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'templates', 'static')
)
ssl._create_default_https_context = ssl._create_unverified_context
CORS(app)

# ---------------------------------------------------------------------------
# Interactive first-run setup wizard — prompts for the admin password and
# vCenter details when no configuration is found, and saves them to
# CONFIG_FILE so future runs start up silently.
# ---------------------------------------------------------------------------
def _prompt_admin_password() -> str:
    while True:
        pw1 = getpass.getpass('Set an admin password (required to confirm VM power actions / cache refresh): ')
        if len(pw1) < 4:
            print('Password must be at least 4 characters.\n')
            continue
        pw2 = getpass.getpass('Confirm admin password: ')
        if pw1 != pw2:
            print('Passwords did not match, try again.\n')
            continue
        return hashlib.sha256(pw1.encode()).hexdigest()


def _test_vcenter_connection(ip: str, user: str, pw: str, port: int, timeout: int = 8):
    """Best-effort live check that these vCenter details actually work. Runs the
    connect attempt in a background thread so a wrong IP/unreachable host can't
    hang the wizard — pyVmomi's SmartConnect has no built-in connect timeout."""
    pool = ThreadPoolExecutor(max_workers=1)

    def _attempt():
        si = SmartConnect(host=ip, user=user, pwd=pw, port=port)
        Disconnect(si)

    future = pool.submit(_attempt)
    try:
        future.result(timeout=timeout)
        return True, None
    except FutureTimeoutError:
        return False, f'no response after {timeout}s — check the IP/FQDN and port'
    except Exception as e:
        return False, str(e)
    finally:
        pool.shutdown(wait=False)


def _prompt_vcenters() -> list:
    servers = []
    idx = 1
    print('\nNow add the vCenter(s) VMFinder should connect to.')
    while True:
        ans = input(f'Add vCenter #{idx}? [y/N]: ').strip().lower()
        if ans not in ('y', 'yes'):
            break

        while True:
            name = input('  Display name (e.g. DC-East): ').strip() or f'VCENTER{idx}'
            ip = input('  IP address or FQDN: ').strip()
            if not ip:
                print('  IP/FQDN is required, try again.\n')
                continue
            user = input('  Username: ').strip()
            pw = getpass.getpass('  Password: ')
            port_raw = input('  Port [443]: ').strip()
            try:
                port = int(port_raw) if port_raw else 443
            except ValueError:
                print(f'  {port_raw!r} is not a valid port number, defaulting to 443.')
                port = 443

            print('  Testing connection...')
            ok, err = _test_vcenter_connection(ip, user, pw, port)
            entry = {'name': name, 'ip': ip, 'user': user, 'pass': pw, 'port': port}
            if ok:
                print('  Connected successfully.\n')
                servers.append(entry)
                break

            print(f'  Could not connect: {err}')
            retry = input('  Re-enter these details? [Y/n] (n keeps them anyway): ').strip().lower()
            if retry in ('n', 'no'):
                servers.append(entry)
                break
            print()

        idx += 1
    return servers


def run_setup_wizard(config_path: str) -> None:
    existing = dotenv_values(config_path) if os.path.exists(config_path) else {}
    existing_admin_hash = existing.get('VMFINDER_ADMIN_HASH')
    existing_vc_lines = {k: v for k, v in existing.items() if k.startswith('VC')}

    print('=' * 60)
    print(' VMFinder — setup' if existing else ' VMFinder — first-run setup')
    print('=' * 60)

    if existing_admin_hash:
        change = input('Change the admin password? [y/N]: ').strip().lower()
        admin_hash = _prompt_admin_password() if change in ('y', 'yes') else existing_admin_hash
    else:
        admin_hash = _prompt_admin_password()

    if existing_vc_lines:
        change = input('Reconfigure vCenters? [y/N] (N keeps the existing list): ').strip().lower()
        vc_lines = [f'{k}={v}' for k, v in existing_vc_lines.items()] if change not in ('y', 'yes') else None
    else:
        vc_lines = None

    if vc_lines is None:
        servers = _prompt_vcenters()
        vc_lines = []
        for n, s in enumerate(servers, start=1):
            vc_lines += [
                f"VC{n}_NAME={s['name']}",
                f"VC{n}_IP={s['ip']}",
                f"VC{n}_USER={s['user']}",
                f"VC{n}_PASS={s['pass']}",
                f"VC{n}_PORT={s['port']}",
            ]

    lines = [f'VMFINDER_ADMIN_HASH={admin_hash}'] + vc_lines

    with open(config_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    os.chmod(config_path, 0o600)
    print(f'\nSaved configuration to {config_path}')
    print('(Run with --reconfigure to change these settings later.)\n')


def _input_with_timeout(prompt: str, timeout: float, default: str) -> str:
    """input() that falls back to `default` if nobody answers within
    `timeout` seconds — a double-clicked exe has no one watching the console."""
    print(f'{prompt} ', end='', flush=True)
    if os.name == 'nt':
        import msvcrt
        deadline = time.time() + timeout
        buf = ''
        while time.time() < deadline:
            if msvcrt.kbhit():
                ch = msvcrt.getwche()
                if ch in ('\r', '\n'):
                    print()
                    return buf.strip() or default
                buf += ch
            time.sleep(0.05)
        print(default)
        return default
    else:
        import select
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.readline().strip() or default
        print(default)
        return default


def _is_configured() -> bool:
    return bool(os.environ.get('VMFINDER_ADMIN_HASH')) and bool(os.environ.get('VC1_IP'))


def ensure_configured(force: bool = False) -> None:
    if not force and _is_configured():
        return
    if not force and os.path.exists(CONFIG_FILE):
        # override=True: the wizard-saved config is authoritative over any
        # stray local .env (e.g. leftover placeholder values from a git clone)
        load_dotenv(CONFIG_FILE, override=True)
        if _is_configured():
            if not sys.stdin.isatty():
                return
            # FIX: a double-clicked exe has no way to pass --reconfigure, so
            # offer the choice here too whenever a saved config is found.
            use_existing = _input_with_timeout(
                'Existing configuration found. Use it? [Y/n] (defaults to Y in 5s):', 5, 'y'
            ).strip().lower()
            if use_existing not in ('n', 'no'):
                return
            # falls through to run_setup_wizard below, which will offer to
            # keep/change the admin password and vCenters independently
    if not sys.stdin.isatty():
        log.warning(
            "VMFinder is not configured (missing VMFINDER_ADMIN_HASH / VC1_IP) and no "
            "interactive terminal is available to run the setup wizard. Set environment "
            "variables or create %s manually.", CONFIG_FILE
        )
        return
    run_setup_wizard(CONFIG_FILE)
    load_dotenv(CONFIG_FILE, override=True)


_arg_parser = argparse.ArgumentParser(description='VMFinder')
_arg_parser.add_argument('--reconfigure', action='store_true',
                          help='Re-run the interactive setup wizard, replacing any saved configuration')
_arg_parser.add_argument('--version', action='store_true', help='Print the version and exit')
cli_args, _ = _arg_parser.parse_known_args()

if cli_args.version:
    print(f'VMFinder {VERSION}')
    sys.exit(0)

log.info(f'VMFinder {VERSION} starting...')
ensure_configured(force=cli_args.reconfigure)

# ---------------------------------------------------------------------------
# Configuration  –  loaded from real environment variables, CONFIG_FILE, or
# the setup wizard above (in that priority order).
# ---------------------------------------------------------------------------
ADMIN_PASSWORD_SHA256 = os.environ.get(
    'VMFINDER_ADMIN_HASH',
    'YOUR_SHA256_HASH_HERE'   # replace with sha256 of your chosen password
)

# Dynamically load as many vCenters as defined in the environment (VC1_IP, VC2_IP, VC3_IP, ...)
# Stops at the first index where VC{n}_IP is not set. No upper limit.
vcenter_servers = []
i = 1
while True:
    ip = os.environ.get(f'VC{i}_IP')
    if not ip:
        break
    port_raw = os.environ.get(f'VC{i}_PORT', '443')
    try:
        port = int(port_raw)
    except ValueError:
        log.warning("VC%d_PORT=%r is not a valid port number, defaulting to 443.", i, port_raw)
        port = 443
    vcenter_servers.append({
        'name':     os.environ.get(f'VC{i}_NAME',  f'VCENTER{i}'),
        'IP':       ip,
        'username': os.environ.get(f'VC{i}_USER',  ''),
        'password': os.environ.get(f'VC{i}_PASS',  ''),
        'port':     port
    })
    i += 1

if not vcenter_servers:
    log.warning("No vCenter servers configured. Run with --reconfigure to set one up.")

# FIX: use a Lock to prevent race conditions on vm_cache between threads
vm_cache: dict = {}
cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Rate limiter (simple in-memory per-IP token bucket for destructive routes)
# ---------------------------------------------------------------------------
_rate_buckets: dict = {}
_rate_lock = threading.Lock()
RATE_LIMIT_WINDOW = 60   # seconds
RATE_LIMIT_MAX    = 10   # requests per window per IP


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets.get(ip, [])
        bucket = [t for t in bucket if now - t < RATE_LIMIT_WINDOW]
        if len(bucket) >= RATE_LIMIT_MAX:
            _rate_buckets[ip] = bucket
            return True
        bucket.append(now)
        _rate_buckets[ip] = bucket
        return False


def rate_limited(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr
        if _is_rate_limited(ip):
            log.warning(f"Rate limit hit from {ip} on {request.path}")
            return jsonify({'message': 'Too many requests. Please slow down.'}), 429
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
def check_password(password: str) -> bool:
    """Constant-time comparison of sha256 hash to avoid timing attacks."""
    if not password:
        return False
    attempt_hash = hashlib.sha256(password.encode()).hexdigest()
    return secrets.compare_digest(attempt_hash, ADMIN_PASSWORD_SHA256)


# ---------------------------------------------------------------------------
# Task helper
# ---------------------------------------------------------------------------
def wait_for_task(task, timeout: int = 30):
    """Block until a vCenter Task reaches a terminal state. ReconfigVM_Task /
    PowerOn etc. return immediately with a pending Task — without this, a
    route can report success before vCenter has actually applied the change,
    so a cache refresh run right after can still read the pre-change state."""
    start = time.time()
    while task.info.state not in (vim.TaskInfo.State.success, vim.TaskInfo.State.error):
        if time.time() - start > timeout:
            raise TimeoutError(f'Task did not complete within {timeout}s')
        time.sleep(0.5)
    if task.info.state == vim.TaskInfo.State.error:
        raise Exception(task.info.error.msg if task.info.error else 'Task failed')


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------
def audit(action: str, vm_name: str, detail: str = '', success: bool = True):
    status = 'SUCCESS' if success else 'FAILURE'
    ip = request.remote_addr if request else 'system'
    log.info(f"[AUDIT] [{status}] ip={ip} action={action} vm={vm_name} detail={detail}")


# ---------------------------------------------------------------------------
# KeepAlive thread
# ---------------------------------------------------------------------------
class KeepAlive(threading.Thread):
    object_count = 1

    def __init__(self, service_instance, vcenter_info: dict, sleep_time_seconds: int = 600):
        super().__init__()
        self.service_instance = service_instance
        # FIX: store host explicitly instead of relying on private _host attribute
        self.vcenter_info = vcenter_info
        self.sleep_time_seconds = sleep_time_seconds
        self.daemon = True
        self.name = f"ServiceInstance-KeepAlive-{KeepAlive.object_count}"
        KeepAlive.object_count += 1

    def run(self):
        while True:
            try:
                self.service_instance.RetrieveContent()
            except Exception:
                self._reconnect()
            time.sleep(self.sleep_time_seconds)

    def _reconnect(self):
        log.warning(f"KeepAlive: lost connection to {self.vcenter_info['IP']}, reconnecting...")
        new_conn, _ = connect_to_vcenter(self.vcenter_info, silent=True)
        if new_conn:
            self.service_instance = new_conn
            new_data = cache_vm_info(new_conn, self.vcenter_info['name'], silent=True)
            with cache_lock:
                vm_cache[self.vcenter_info['name']] = new_data
            log.info(f"KeepAlive: reconnected to {self.vcenter_info['IP']}")


# ---------------------------------------------------------------------------
# vCenter connection
# ---------------------------------------------------------------------------
def connect_to_vcenter(vcenter_info: dict, silent: bool = False):
    try:
        service_instance = SmartConnect(
            host=vcenter_info['IP'],
            user=vcenter_info['username'],
            pwd=vcenter_info['password'],
            port=vcenter_info['port']
        )
        if not silent:
            log.info(f"Connected to vCenter: {vcenter_info['IP']}")

        keep_alive = KeepAlive(service_instance, vcenter_info)
        keep_alive.start()
        vcenter_info['connection'] = service_instance
        return service_instance, vcenter_info
    except Exception as e:
        log.error(f"Error connecting to vCenter {vcenter_info['IP']}: {e}")
        return None, vcenter_info


# ---------------------------------------------------------------------------
# VM cache builder
# ---------------------------------------------------------------------------
def cache_vm_info(service_instance, vcenter_name: str, silent: bool = False) -> dict:
    try:
        content = service_instance.RetrieveContent()
        if not content:
            return {}

        if not silent:
            log.info("Bulk-fetching VM properties from inventory...")

        container_view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )

        # FIX: added runtime.powerState to pathSet so power state is available
        # FIX: added guest.ipAddress + guest.ipStack as fallbacks for VMs where
        # guest.net is empty (e.g. VMware Tools not fully running)
        property_spec = vim.PropertySpec(
            type=vim.VirtualMachine,
            pathSet=["name", "guest.net", "guest.ipAddress", "guest.ipStack",
                     "config.hardware.device", "runtime.powerState"]
        )
        object_spec = vim.ObjectSpec(
            obj=container_view,
            skip=True,
            selectSet=[vim.TraversalSpec(
                name="traverseEntities", path="view", skip=False, type=vim.ContainerView
            )]
        )
        filter_spec = vim.PropertyFilterSpec(propSet=[property_spec], objectSet=[object_spec])
        vm_data = {}

        props = content.propertyCollector.RetrievePropertiesEx(
            specSet=[filter_spec], options=vim.RetrieveOptions()
        )

        while props:
            for obj_content in props.objects:
                vm = obj_content.obj
                vm_name, ip_addresses, mac_addresses, power_state = None, [], [], 'unknown'

                for prop in obj_content.propSet:
                    if prop.name == "name":
                        vm_name = prop.val
                    elif prop.name == "runtime.powerState":
                        power_state = str(prop.val)
                    elif prop.name == "guest.net" and prop.val:
                        for net in prop.val:
                            if hasattr(net, 'ipConfig') and net.ipConfig:
                                ip_addresses.extend([
                                    ip.ipAddress for ip in net.ipConfig.ipAddress
                                    if ip.ipAddress and not ip.ipAddress.startswith('169.254.')
                                ])
                    elif prop.name == "guest.ipAddress" and prop.val:
                        # Primary IP reported by VMware Tools — use as fallback
                        if prop.val and not prop.val.startswith('169.254.'):
                            ip_addresses.append(prop.val)
                    elif prop.name == "guest.ipStack" and prop.val:
                        # ipStack contains per-NIC IP info as another fallback
                        for stack in prop.val:
                            if hasattr(stack, 'ipConfig') and stack.ipConfig:
                                ip_addresses.extend([
                                    ip.ipAddress for ip in stack.ipConfig.ipAddress
                                    if ip.ipAddress and not ip.ipAddress.startswith('169.254.')
                                ])
                    elif prop.name == "config.hardware.device" and prop.val:
                        mac_addresses.extend([
                            d.macAddress for d in prop.val
                            if isinstance(d, vim.vm.device.VirtualEthernetCard)
                               and hasattr(d, 'macAddress')
                        ])

                if vm_name:
                    # Deduplicate IPs while preserving order
                    seen = set()
                    unique_ips = []
                    for ip in ip_addresses:
                        if ip not in seen:
                            seen.add(ip)
                            unique_ips.append(ip)
                    vm_data[vm_name] = {
                        'vm': vm,
                        'ip_addresses': unique_ips,
                        'mac_addresses': mac_addresses,
                        'power_state': power_state
                    }

            if hasattr(props, 'token') and props.token:
                props = content.propertyCollector.ContinueRetrievePropertiesEx(token=props.token)
            else:
                break

        if not silent:
            log.info(f"Cached {len(vm_data)} VMs from {vcenter_name}.")

        return vm_data
    except Exception as e:
        log.error(f"Error building VM cache for {vcenter_name}: {e}")
        return {}


# ---------------------------------------------------------------------------
# Boot sequence
# ---------------------------------------------------------------------------
log.info("Initializing connections and building memory cache maps...")
connected_vcenter_names = []

for srv in vcenter_servers:
    conn, _ = connect_to_vcenter(srv)
    if conn:
        with cache_lock:
            vm_cache[srv['name']] = cache_vm_info(conn, srv['name'])
        connected_vcenter_names.append(srv['name'])

if connected_vcenter_names:
    log.info(f"Connected to vCenters: {', '.join(connected_vcenter_names)}")
    log.info("Starting Flask web server on port 5000...")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html', version=VERSION)


@app.route('/search', methods=['GET'])
def search_vms():
    query = request.args.get('query', '').strip().lower()

    # FIX: reject empty / too-short queries — prevents full inventory dump
    if len(query) < 3:
        return jsonify({'error': 'Query must be at least 3 characters.'}), 400

    # Optional pagination
    try:
        page     = max(1, int(request.args.get('page', 1)))
        per_page = min(50, max(1, int(request.args.get('per_page', 25))))
    except ValueError:
        page, per_page = 1, 25

    results = []

    with cache_lock:
        snapshot = {vc: dict(data) for vc, data in vm_cache.items()}

    for vc_name, data in snapshot.items():
        for name, info in data.items():
            if (query in name.lower()
                    or any(query in ip.lower() for ip in info['ip_addresses'])
                    or any(query in mac.lower() for mac in info['mac_addresses'])):

                vm = info['vm']
                net_details = []

                if hasattr(vm, 'config') and vm.config and vm.config.hardware.device:
                    for dev in vm.config.hardware.device:
                        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
                            net_details.append({
                                'adapter_name':  dev.deviceInfo.label,
                                'network_name':  dev.backing.network.name
                                if hasattr(dev.backing, 'network') and dev.backing.network
                                else None,
                                'mac_address':   dev.macAddress,
                                # FIX: report the actual live connection state — the
                                # network/port-group assignment (network_name) stays
                                # in place after /disconnect, only connectable.connected
                                # flips, so the UI must key off this, not network_name.
                                'connected':     bool(dev.connectable and dev.connectable.connected)
                            })

                results.append({
                    'vcenter_name':   vc_name,
                    'vm_name':        name,
                    'ip_addresses':   info['ip_addresses'],
                    'network_details': net_details,
                    'power_state':    info.get('power_state', 'unknown')
                })

    total = len(results)
    start = (page - 1) * per_page
    page_results = results[start:start + per_page]

    return jsonify({
        'results':   page_results,
        'total':     total,
        'page':      page,
        'per_page':  per_page,
        'pages':     max(1, -(-total // per_page))   # ceiling division
    })


@app.route('/disconnect', methods=['POST'])
@rate_limited
def disconnect_network_adapter_route():
    data     = request.get_json() or {}
    password = data.get('password')

    # FIX: constant-time hash comparison
    if not check_password(password):
        audit('disconnect', data.get('vm_name', '?'), 'bad password', success=False)
        return jsonify({'message': 'Unauthorized: Invalid credentials.'}), 401

    vm_name      = data.get('vm_name')
    adapter_name = data.get('adapter_name')

    with cache_lock:
        target_vm = next(
            (vms[vm_name]['vm'] for vc, vms in vm_cache.items() if vm_name in vms),
            None
        )

    if not target_vm:
        return jsonify({'message': 'VM Asset not found'}), 404

    for dev in target_vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard) \
                and dev.deviceInfo.label == adapter_name:
            try:
                spec   = vim.vm.ConfigSpec()
                change = vim.vm.device.VirtualDeviceSpec(operation="edit", device=dev)
                change.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo(
                    connected=False, startConnected=False
                )
                spec.deviceChange = [change]
                wait_for_task(target_vm.ReconfigVM_Task(spec=spec))
                audit('disconnect', vm_name, f'adapter={adapter_name}')
                return jsonify({'message': f'Interface {adapter_name} completely isolated.'}), 200
            except Exception as e:
                audit('disconnect', vm_name, f'adapter={adapter_name} error={e}', success=False)
                return jsonify({'message': f'Reconfiguration failure: {str(e)}'}), 500

    return jsonify({'message': 'Adapter not found'}), 400


@app.route('/control_vm', methods=['POST'])
@rate_limited
def control_vm():
    data     = request.get_json() or {}
    password = data.get('password')

    # FIX: constant-time hash comparison
    if not check_password(password):
        audit('control_vm', data.get('vm_name', '?'), 'bad password', success=False)
        return jsonify({'message': 'Unauthorized: Invalid credentials.'}), 401

    vm_name = data.get('vm_name')
    action  = data.get('action')

    with cache_lock:
        target_vm = next(
            (vms[vm_name]['vm'] for vc, vms in vm_cache.items() if vm_name in vms),
            None
        )

    if not target_vm:
        return jsonify({'message': 'VM Asset not found'}), 404

    try:
        if action == 'power_on':
            wait_for_task(target_vm.PowerOn())
        elif action == 'reboot':
            target_vm.RebootGuest()
        elif action == 'shutdown':
            target_vm.ShutdownGuest()
        else:
            return jsonify({'message': 'Invalid power state parameter.'}), 400

        audit('control_vm', vm_name, f'action={action}')
        return jsonify({'message': f'Power state command [{action}] sent successfully.'}), 200
    except Exception as e:
        audit('control_vm', vm_name, f'action={action} error={e}', success=False)
        return jsonify({'message': f'Power adjustment exception: {str(e)}'}), 500


# FIX: manual cache refresh endpoint (admin-only) — no restart needed after VM changes
@app.route('/refresh_cache', methods=['POST'])
@rate_limited
def refresh_cache():
    data     = request.get_json() or {}
    password = data.get('password')

    if not check_password(password):
        return jsonify({'message': 'Unauthorized: Invalid credentials.'}), 401

    refreshed = []
    for srv in vcenter_servers:
        conn = srv.get('connection')
        if conn:
            new_data = cache_vm_info(conn, srv['name'])
            with cache_lock:
                vm_cache[srv['name']] = new_data
            refreshed.append(srv['name'])
            log.info(f"Cache refreshed for {srv['name']} ({len(new_data)} VMs)")

    return jsonify({'message': f"Cache refreshed for: {', '.join(refreshed)}"}), 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)