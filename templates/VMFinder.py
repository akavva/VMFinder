import ssl
import threading
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from pyVim.connect import SmartConnect
from pyVmomi import vim

app = Flask(__name__, template_folder=r'C:\Users\Administrator\IdeaProjects\VMFinder\templates', static_folder=r'C:\Users\Administrator\IdeaProjects\VMFinder\templates\static')

ssl._create_default_https_context = ssl._create_unverified_context
CORS(app)

# Simplified plain-text password for testing UI actions
ADMIN_PASSWORD_HASH = "your_password_here"

vcenter_servers = [
    {
        'name': 'VCENTER_FQDN',
        'IP': 'VCENTERS_IP_ADDRESS',
        'username': 'ADMIN_USERNAME',
        'password': 'ADMIN_PASSWORD',
        'port': 443
    },
    {
        'name': 'VCENTER_FQDN',
        'IP': 'VCENTERS_IP_ADDRESS',
        'username': 'ADMIN_USERNAME',
        'password': 'ADMIN_PASSWORD',
        'port': 443
    }
]

vm_cache = {}

class KeepAlive(threading.Thread):
    object_count = 1

    def __init__(self, service_instance, sleep_time_seconds: int = 600):
        super().__init__()
        self.service_instance = service_instance
        self.sleep_time_seconds = sleep_time_seconds
        self.daemon = True
        self.name = f"ServiceInstance-KeepAlive-{KeepAlive.object_count}"
        KeepAlive.object_count += 1

    def run(self):
        import time
        while True:
            try:
                self.service_instance.RetrieveContent()
            except Exception:
                self.reconnect_to_vcenter()
            time.sleep(self.sleep_time_seconds)

    def reconnect_to_vcenter(self):
        global vm_cache
        for vcenter_info in vcenter_servers:
            if vcenter_info['IP'] == self.service_instance._host:
                new_connection, _ = connect_to_vcenter(vcenter_info, silent=True)
                if new_connection:
                    self.service_instance = new_connection
                    vm_cache[vcenter_info['name']] = cache_vm_info(new_connection, vcenter_info['name'], silent=True)
                    return


def connect_to_vcenter(vcenter_info, silent=False):
    try:
        service_instance = SmartConnect(
            host=vcenter_info['IP'],
            user=vcenter_info['username'],
            pwd=vcenter_info['password'],
            port=vcenter_info['port']
        )
        if not silent:
            print(f"Connected to vCenter: {vcenter_info['IP']}")

        keep_alive_thread = KeepAlive(service_instance)
        keep_alive_thread.start()
        vcenter_info['connection'] = service_instance
        return service_instance, vcenter_info
    except Exception as e:
        print(f"Error connecting to vCenter {vcenter_info['IP']}: {str(e)}")
        return None, vcenter_info


def cache_vm_info(service_instance, vcenter_name, silent=False):
    try:
        content = service_instance.RetrieveContent()
        if not content:
            return {}

        if not silent:
            print("Optimizing query matrix... Bulk fetching properties for inventory.")

        container_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

        property_spec = vim.PropertySpec(type=vim.VirtualMachine, pathSet=["name", "guest.net", "config.hardware.device"])
        object_spec = vim.ObjectSpec(obj=container_view, skip=True, selectSet=[
            vim.TraversalSpec(name="traverseEntities", path="view", skip=False, type=vim.ContainerView)
        ])

        filter_spec = vim.PropertyFilterSpec(propSet=[property_spec], objectSet=[object_spec])
        vm_data = {}

        props = content.propertyCollector.RetrievePropertiesEx(specSet=[filter_spec], options=vim.RetrieveOptions())

        while props:
            for obj_content in props.objects:
                vm = obj_content.obj
                vm_name, ip_addresses, mac_addresses = None, [], []

                for prop in obj_content.propSet:
                    if prop.name == "name":
                        vm_name = prop.val
                    elif prop.name == "guest.net" and prop.val:
                        for net in prop.val:
                            if hasattr(net, 'ipConfig') and net.ipConfig:
                                ip_addresses.extend([ip.ipAddress for ip in net.ipConfig.ipAddress if ip.ipAddress and not ip.ipAddress.startswith('169.254.')])
                    elif prop.name == "config.hardware.device" and prop.val:
                        mac_addresses.extend([d.macAddress for d in prop.val if isinstance(d, vim.vm.device.VirtualEthernetCard) and hasattr(d, 'macAddress')])

                if vm_name:
                    vm_data[vm_name] = {'vm': vm, 'ip_addresses': ip_addresses, 'mac_addresses': mac_addresses}

            if hasattr(props, 'token') and props.token:
                props = content.propertyCollector.ContinueRetrievePropertiesEx(token=props.token)
            else:
                break

        if not silent:
            print(f"Successfully cached {len(vm_data)} VMs into memory.")

        return vm_data
    except Exception as e:
        print(f"Error building optimized VM cache matrix: {str(e)}")
        return {}


# Executing boot sequence print mappings
print("Initializing connections and building memory cache maps...")
connected_vcenter_names = []

for srv in vcenter_servers:
    conn, _ = connect_to_vcenter(srv)
    if conn:
        vm_cache[srv['name']] = cache_vm_info(conn, srv['name'])
        connected_vcenter_names.append(srv['name'])

if connected_vcenter_names:
    print(f"Connected to vCenters: {', '.join(connected_vcenter_names)}")
    print("Starting Flask web server on port 80...")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search_vms():
    query = request.args.get('query', '').strip().lower()
    results = []

    for vc_name, data in vm_cache.items():
        for name, info in data.items():
            if query in name.lower() or any(query in ip.lower() for ip in info['ip_addresses']) or any(query in mac.lower() for mac in info['mac_addresses']):
                vm = info['vm']
                net_details = []

                if hasattr(vm, 'config') and vm.config.hardware.device:
                    for dev in vm.config.hardware.device:
                        if isinstance(dev, vim.vm.device.VirtualEthernetCard):
                            net_details.append({
                                'adapter_name': dev.deviceInfo.label,
                                'network_name': dev.backing.network.name if hasattr(dev.backing, 'network') else None,
                                'mac_address': dev.macAddress
                            })

                results.append({
                    'vcenter_name': vc_name,
                    'vm_name': name,
                    'ip_addresses': info['ip_addresses'],
                    'network_details': net_details
                })
    return jsonify(results)


@app.route('/disconnect', methods=['POST'])
def disconnect_network_adapter_route():
    data = request.get_json() or {}
    password = data.get('password')

    if not password or password != ADMIN_PASSWORD_HASH:
        return jsonify({'message': 'Unauthorized: Invalid credentials.'}), 401

    vm_name, adapter_name = data.get('vm_name'), data.get('adapter_name')
    target_vm = next((vms[vm_name]['vm'] for vc, vms in vm_cache.items() if vm_name in vms), None)

    if not target_vm:
        return jsonify({'message': 'VM Asset not found'}), 404

    for dev in target_vm.config.hardware.device:
        if isinstance(dev, vim.vm.device.VirtualEthernetCard) and dev.deviceInfo.label == adapter_name:
            try:
                spec = vim.vm.ConfigSpec()
                change = vim.vm.device.VirtualDeviceSpec(operation="edit", device=dev)
                change.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo(connected=False, startConnected=False)
                spec.deviceChange = [change]
                target_vm.ReconfigVM_Task(spec=spec)
                return jsonify({'message': f'Interface {adapter_name} completely isolated.'}), 200
            except Exception as e:
                return jsonify({'message': f'Reconfiguration failure: {str(e)}'}), 500
    return jsonify({'message': 'Adapter not found'}), 400


@app.route('/control_vm', methods=['POST'])
def control_vm():
    data = request.get_json() or {}
    password = data.get('password')

    if not password or password != ADMIN_PASSWORD_HASH:
        return jsonify({'message': 'Unauthorized: Invalid credentials.'}), 401

    vm_name, action = data.get('vm_name'), data.get('action')
    target_vm = next((vms[vm_name]['vm'] for vc, vms in vm_cache.items() if vm_name in vms), None)

    if not target_vm:
        return jsonify({'message': 'VM Asset not found'}), 404

    try:
        if action == 'power_on':
            target_vm.PowerOn()
        elif action == 'reboot':
            target_vm.RebootGuest()
        elif action == 'shutdown':
            target_vm.ShutdownGuest()
        else:
            return jsonify({'message': 'Invalid power state parameter.'}), 400
        return jsonify({'message': f'Power state command [{action}] sent successfully.'}), 200
    except Exception as e:
        return jsonify({'message': f'Power adjustment exception: {str(e)}'}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)