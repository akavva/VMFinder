import ssl
import threading
import time
import pyVmomi
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
        'hostname': 'VCENTERS_IP_ADDRESS',
        'username': 'ADMIN_USERNAME',
        'password': 'ADMIN_PASSWORD',
        'port': 443
    },
    {
        'name': 'VCENTER_FQDN',
        'hostname': 'VCENTERS_IP_ADDRESS',
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
        self.name = "ServiceInstance-KeepAlive-{:d}".format(KeepAlive.object_count)
        KeepAlive.object_count += 1

    def run(self):
        while True:
            try:
                self.service_instance.RetrieveContent()
            except pyVmomi.vim.fault.NotAuthenticated:
                print("\nSession not authenticated, attempting to reconnect...")
                self.reconnect_to_vcenter()
            except Exception as e:
                print(f"\nAn unexpected error occurred in KeepAlive: {str(e)}")

            time.sleep(self.sleep_time_seconds)

    def reconnect_to_vcenter(self):
        global vm_cache
        for vcenter_info in vcenter_servers:
            if vcenter_info['hostname'] == self.service_instance._host:
                new_connection, updated_info = connect_to_vcenter(vcenter_info)
                if new_connection:
                    self.service_instance = new_connection
                    vm_cache[vcenter_info['name']] = cache_vm_info(new_connection, vcenter_info['name'])
                    print(f"\nReconnected to vCenter: {vcenter_info['hostname']}")
                    return
        print(f"\nFailed to reconnect to vCenter for host: {self.service_instance._host}")


def connect_to_vcenter(vcenter_info):
    try:
        service_instance = SmartConnect(
            host=vcenter_info['hostname'],
            user=vcenter_info['username'],
            pwd=vcenter_info['password'],
            port=vcenter_info['port']
        )
        print("Connected to vCenter:", vcenter_info['hostname'])

        keep_alive_thread = KeepAlive(service_instance)
        keep_alive_thread.start()

        vcenter_info['connection'] = service_instance
        return service_instance, vcenter_info
    except Exception as e:
        print("Error connecting to vCenter:", str(e))
        return None, vcenter_info


def cache_vm_info(service_instance, vcenter_name):
    try:
        content = service_instance.RetrieveContent()
        if content is None:
            print(f"Failed to retrieve content from vCenter: {vcenter_name}")
            return {}

        container = content.rootFolder
        view_type = [vim.VirtualMachine]
        recursive = True
        containerView = content.viewManager.CreateContainerView(container, view_type, recursive)

        print(f"Optimizing query matrix... Bulk fetching properties for inventory.")

        # Create a Property Spec to define exactly what properties we need collected
        property_spec = vim.PropertySpec()
        property_spec.type = vim.VirtualMachine
        property_spec.pathSet = ["name", "guest.net", "config.hardware.device"]

        # Create an Object Spec to tell vCenter where to look (using our container view)
        object_spec = vim.ObjectSpec()
        object_spec.obj = containerView
        object_spec.skip = True

        # Define traversal specs to navigate the container view entries
        traversal_spec = vim.TraversalSpec()
        traversal_spec.name = "traverseEntities"
        traversal_spec.path = "view"
        traversal_spec.skip = False
        traversal_spec.type = vim.ContainerView
        object_spec.selectSet = [traversal_spec]

        # Combine into a single FilterSpec
        filter_spec = vim.PropertyFilterSpec()
        filter_spec.propSet = [property_spec]
        filter_spec.objectSet = [object_spec]

        vm_data = {}

        try:
            # Added the required RetrieveOptions argument to satisfy the vCenter API schema constraint
            options = vim.RetrieveOptions()
            props = content.propertyCollector.RetrievePropertiesEx(specSet=[filter_spec], options=options)

            # Parse the data directly out of local memory cache instead of hitting the API network stream
            while props:
                for obj_content in props.objects:
                    vm = obj_content.obj
                    vm_name = None
                    ip_addresses = []
                    mac_addresses = []

                    # Extract retrieved properties from the local object model payload
                    for prop in obj_content.propSet:
                        if prop.name == "name":
                            vm_name = prop.val
                        elif prop.name == "guest.net" and prop.val:
                            for network_info in prop.val:
                                if hasattr(network_info, 'ipConfig') and hasattr(network_info.ipConfig, 'ipAddress') and network_info.ipConfig.ipAddress:
                                    for ip_info in network_info.ipConfig.ipAddress:
                                        ip_address = ip_info.ipAddress
                                        if ip_address and not ip_address.startswith('169.254.'):
                                            ip_addresses.append(ip_address)
                        elif prop.name == "config.hardware.device" and prop.val:
                            for device in prop.val:
                                if isinstance(device, vim.vm.device.VirtualEthernetCard) and hasattr(device, 'macAddress'):
                                    mac_addresses.append(device.macAddress)

                    if vm_name:
                        vm_data[vm_name] = {'vm': vm, 'ip_addresses': ip_addresses, 'mac_addresses': mac_addresses}

                # Check if there are more results to page through
                if hasattr(props, 'token') and props.token:
                    props = content.propertyCollector.ContinueRetrievePropertiesEx(token=props.token)
                else:
                    break

        except Exception as api_ex:
            print(f"Fast collector failed ({str(api_ex)}). Engaging legacy parsing engine safe-mode fallback...")
            # Emergency automated fallback if property collector fails on older legacy ESXi builds
            vm_list = containerView.view
            for vm in vm_list:
                try:
                    v_name = vm.name
                    ips = []
                    macs = []
                    if hasattr(vm, 'guest') and vm.guest.net:
                        for net_info in vm.guest.net:
                            if hasattr(net_info, 'ipConfig') and net_info.ipConfig.ipAddress:
                                for ip_inf in net_info.ipConfig.ipAddress:
                                    if ip_inf.ipAddress and not ip_inf.ipAddress.startswith('169.254.'):
                                        ips.append(ip_inf.ipAddress)
                    if hasattr(vm, 'config') and vm.config.hardware.device:
                        for dev in vm.config.hardware.device:
                            if isinstance(dev, vim.vm.device.VirtualEthernetCard):
                                macs.append(dev.macAddress)
                    vm_data[v_name] = {'vm': vm, 'ip_addresses': ips, 'mac_addresses': macs}
                except Exception:
                    continue

        print(f"Successfully cached {len(vm_data)} VMs into memory.")
        return vm_data
    except Exception as e:
        print(f"\nError while building optimized VM cache matrix: {str(e)}")
        return {}


print("Initializing connections and building memory cache maps...")
for vcenter_info in vcenter_servers:
    connection, updated_info = connect_to_vcenter(vcenter_info)
    if connection:
        vm_cache[vcenter_info['name']] = cache_vm_info(connection, vcenter_info['name'])
    else:
        print(f"Failed to connect to vCenter: {vcenter_info['hostname']}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/search', methods=['GET'])
def search_vms():
    search_query = request.args.get('query', '').strip().lower()
    results = perform_search(search_query)
    return jsonify(results)


def perform_search(search_query):
    results = []
    for vcenter_name, vm_data in vm_cache.items():
        for vm_name, vm_info in vm_data.items():
            ip_addresses = vm_info.get('ip_addresses', [])

            if (
                    search_query.lower() in vm_name.lower() or
                    any(search_query in ip.lower() for ip in ip_addresses) or
                    any(search_query.lower() in (mac.lower() if mac else "") for mac in vm_info.get('mac_addresses', []))
            ):
                vm = vm_info['vm']
                network_info = get_vm_network_info(vm)
                network_details = []

                for adapter_name, adapter_info in network_info.items():
                    network_details.append({
                        'adapter_name': adapter_name,
                        'network_name': adapter_info['network_name'],
                        'mac_address': adapter_info['mac_address']
                    })

                result = {
                    'vcenter_name': vcenter_name,
                    'vm_name': vm.name,
                    'ip_addresses': ip_addresses,
                    'network_details': network_details
                }
                results.append(result)
    return results


def get_vm_network_info(vm):
    if not hasattr(vm, 'config'):
        print(f"VM '{vm.name}' does not have config information. Check session authentication.")
        return {}
    network_info = {}
    for device in vm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualEthernetCard):
            adapter_name = device.deviceInfo.label
            network_name = device.backing.network.name if hasattr(device.backing, 'network') and hasattr(device.backing.network, 'name') else None
            mac_address = device.macAddress if hasattr(device, 'macAddress') else None
            network_info[adapter_name] = {'network_name': network_name, 'mac_address': mac_address}
    return network_info


@app.route('/disconnect', methods=['POST'])
def disconnect_network_adapter_route():
    data = request.get_json() or {}
    vm_name = data.get('vm_name')
    adapter_name = data.get('adapter_name')
    password = data.get('password')

    if not password or password != ADMIN_PASSWORD_HASH:
        return jsonify({'message': 'Unauthorized: Invalid or missing administrative password.'}), 401

    if not vm_name or not adapter_name:
        return jsonify({'message': 'Invalid request parameters'}), 400

    vm_to_disconnect = None
    for vcenter_name, vm_data in vm_cache.items():
        if vm_name in vm_data:
            vm_to_disconnect = vm_data[vm_name]['vm']
            break

    if vm_to_disconnect is None:
        return jsonify({'message': f'VM {vm_name} not found'}), 404

    success = disconnect_network_adapter(vm_to_disconnect, adapter_name)
    if success:
        return jsonify({'message': f'Network adapter {adapter_name} disconnected successfully'}), 200
    else:
        return jsonify({'message': f'Failed to disconnect network adapter {adapter_name}'}), 500


def disconnect_network_adapter(vm, adapter_name):
    for device in vm.config.hardware.device:
        if isinstance(device, vim.vm.device.VirtualEthernetCard) and device.deviceInfo.label == adapter_name:
            try:
                spec = vim.vm.ConfigSpec()
                nic_change = vim.vm.device.VirtualDeviceSpec()
                nic_change.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
                nic_change.device = device
                nic_change.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nic_change.device.connectable.connected = False
                spec.deviceChange = [nic_change]
                task = vm.ReconfigVM_Task(spec=spec)

                if hasattr(task, 'wait'):
                    task.wait()

                print(f"Network adapter '{adapter_name}' of VM '{vm.name}' disconnected.")
                return True
            except Exception as e:
                print(f"Error disconnecting network adapter '{adapter_name}' of VM '{vm.name}': {str(e)}")
                return False
    return False


def power_on_vm(vm):
    try:
        task = vm.PowerOn()
        if hasattr(task, 'wait'):
            task.wait()
        print(f"VM '{vm.name}' powered on.")
        return True
    except Exception as e:
        print(f"Error powering on VM '{vm.name}': {str(e)}")
        return False


def reboot_vm(vm):
    try:
        vm.RebootGuest()
        print(f"VM '{vm.name}' rebooted.")
        return True
    except Exception as e:
        print(f"Error rebooting VM '{vm.name}': {str(e)}")
        return False


def shutdown_vm(vm):
    try:
        vm.ShutdownGuest()
        print(f"VM '{vm.name}' shut down.")
        return True
    except Exception as e:
        print(f"Error shutting down VM '{vm.name}': {str(e)}")
        return False


@app.route('/control_vm', methods=['POST'])
def control_vm():
    data = request.get_json() or {}
    action = data.get('action')
    vm_name = data.get('vm_name')
    password = data.get('password')

    if not password or password != ADMIN_PASSWORD_HASH:
        return jsonify({'message': 'Unauthorized: Invalid or missing administrative password.'}), 401

    if not vm_name or not action:
        return jsonify({'message': "Missing 'vm_name' or 'action' parameter."}), 400

    target_vm = None
    for vcenter_name, vm_data in vm_cache.items():
        if vm_name in vm_data:
            target_vm = vm_data[vm_name]['vm']
            break

    if target_vm is None:
        return jsonify({'message': f'VM {vm_name} not found'}), 404

    action_functions = {
        'power_on': power_on_vm,
        'reboot': reboot_vm,
        'shutdown': shutdown_vm
    }

    if action not in action_functions:
        return jsonify({'message': 'Invalid action'}), 400

    success = action_functions[action](target_vm)
    if success:
        return jsonify({'message': f'Action {action} completed successfully for VM {vm_name}'}), 200
    else:
        return jsonify({'message': f'Failed to {action} VM {vm_name}'}), 500


@app.route('/validate_password', methods=['POST'])
def validate_password():
    data = request.get_json() or {}
    user_password = data.get('password')

    if user_password and user_password == ADMIN_PASSWORD_HASH:
        return jsonify({'valid': True}), 200
    return jsonify({'valid': False}), 401


if __name__ == "__main__":
    vcenter_instances = list(vm_cache.keys())
    print("Connected to vCenters:", ", ".join(vcenter_instances) if vcenter_instances else "None")

    print("Starting Flask web server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)