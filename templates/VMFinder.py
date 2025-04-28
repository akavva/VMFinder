import pyVmomi
from flask import Flask, request, jsonify, render_template
from pyVim.connect import SmartConnect
from pyVmomi import vim
import ssl
import threading
from flask_cors import CORS
import time

#set the template path and static folder according to yours
app = Flask(__name__, template_folder=r'C:\Users\Administrator\IdeaProjects\VMFinder\templates', static_folder=r'C:\Users\Administrator\IdeaProjects\VMFinder\templates\static')

ssl._create_default_https_context = ssl._create_unverified_context

CORS(app)  # Enable CORS for all routes in the app

# Define vcenter_servers as a list of dictionaries containing vCenter server information
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

# Define the KeepAlive class after your existing code
class KeepAlive(threading.Thread):
    object_count = 1  # Counter for generating thread names

    def __init__(self, service_instance, sleep_time_seconds: int = 600):
        """Create daemon thread to keep vCenter session alive
        @param service_instance: ServiceInstance object
        @param sleep_time_seconds: how long to wait between keep-alive accesses
        """
        super().__init__()
        self.service_instance = service_instance
        self.sleep_time_seconds = sleep_time_seconds
        self.daemon = True
        self.name = "ServiceInstance-KeepAlive-{:d}".format(KeepAlive.object_count)
        KeepAlive.object_count += 1

    def run(self):
        while True:
            try:
                self.service_instance.RetrieveContent()  # Refresh the session
            except pyVmomi.vim.fault.NotAuthenticated:
                print("Session not authenticated, attempting to reconnect...")
                self.reconnect_to_vcenter()
            except Exception as e:
                print(f"An unexpected error occurred: {str(e)}")
                # Handle other exceptions as needed

            time.sleep(self.sleep_time_seconds)

def reconnect_to_vcenter(self):
    for vcenter_info in vcenter_servers:
        if vcenter_info['hostname'] == self.service_instance._host:
            new_connection, updated_info = connect_to_vcenter(vcenter_info)
            if new_connection:
                self.service_instance = new_connection
                vm_cache[vcenter_info['name']] = cache_vm_info(new_connection, vcenter_info['name'])
                print(f"Reconnected to vCenter: {vcenter_info['hostname']}")
                return
    print(f"Failed to reconnect to vCenter for host: {self.service_instance._host}")

def connect_to_vcenter(vcenter_info):
    try:
        service_instance = SmartConnect(
            host=vcenter_info['hostname'],
            user=vcenter_info['username'],
            pwd=vcenter_info['password'],
            port=vcenter_info['port']
        )
        print("Connected to vCenter:", vcenter_info['hostname'])

        # Create and start the KeepAlive thread
        keep_alive_thread = KeepAlive(service_instance)
        keep_alive_thread.start()

        # Update the 'vcenter_info' dictionary with the 'connection'
        vcenter_info['connection'] = service_instance

        return service_instance, vcenter_info
    except Exception as e:
        print("Error connecting to vCenter:", str(e))
        return None, vcenter_info


# Handle multiple IP addresses
def cache_vm_info(service_instance, vcenter_name):
    content = service_instance.RetrieveContent()
    if content is None:
        print(f"Failed to retrieve content from vCenter: {vcenter_name}")
        return {}

    container = content.rootFolder
    view_type = [vim.VirtualMachine]
    recursive = True
    containerView = content.viewManager.CreateContainerView(container, view_type, recursive)
    vm_list = containerView.view

    vm_data = {}
    for vm in vm_list:
        vm_name = vm.name
        ip_addresses = []

        if hasattr(vm.guest, 'net'):
            for network_info in vm.guest.net:
                if hasattr(network_info, 'ipConfig') and hasattr(network_info.ipConfig, 'ipAddress'):
                    for ip_info in network_info.ipConfig.ipAddress:
                        ip_address = ip_info.ipAddress
                        if ip_address and not ip_address.startswith('169.254.'):
                            ip_addresses.append(ip_address)

        # Collect MAC addresses
        mac_addresses = []
        if hasattr(vm.config, 'hardware') and hasattr(vm.config.hardware, 'device'):
            for device in vm.config.hardware.device:
                if isinstance(device, vim.vm.device.VirtualEthernetCard) and hasattr(device, 'macAddress'):
                    mac_addresses.append(device.macAddress)

        vm_data[vm_name] = {'vm': vm, 'ip_addresses': ip_addresses, 'mac_addresses': mac_addresses}

    return vm_data

def cache_all_vms():
    vm_cache = {}
    for vcenter_info in vcenter_servers:
        connection, vcenter_info = connect_to_vcenter(vcenter_info)
        if connection:
            vm_data = cache_vm_info(connection, vcenter_info['name'])
            vm_cache[vcenter_info['name']] = vm_data
    return vm_cache

# Cache all VMs on app launch
vm_cache = {}
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

# Modify the perform_search function to search by MAC address
def perform_search(search_query):
    results = []

    for vcenter_name, vm_data in vm_cache.items():
        for vm_name, vm_info in vm_data.items():
            ip_addresses = vm_info.get('ip_addresses', [])

            if (
                    search_query.lower() in vm_name.lower() or
                    any(search_query in ip.lower() for ip in ip_addresses) or
                    any(search_query.lower() in (mac.lower() if mac else "") for mac in vm_info['mac_addresses'])
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
                    'ip_addresses': ip_addresses,  # Include all IP addresses
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
            network_name = device.backing.network.name if hasattr(device.backing, 'network') else None
            mac_address = device.macAddress if hasattr(device, 'macAddress') else None
            network_info[adapter_name] = {'network_name': network_name, 'mac_address': mac_address}
    return network_info

# Add the /disconnect route
@app.route('/disconnect', methods=['POST'])
def disconnect_network_adapter_route():
    if request.method == 'OPTIONS':
        # This handles the preflight request by providing the required CORS headers.
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    vm_name = request.args.get('vm_name')
    adapter_name = request.args.get('adapter_name')

    if not vm_name or not adapter_name:
        return jsonify({'message': 'Invalid request parameters'}), 400

    # Find the VM in the vm_cache
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
    data = request.get_json()
    action = data.get('action')
    vm_name = data.get('vm_name')

    if not vm_name:
        return jsonify({'message': "Missing 'vm_name' parameter."}), 400

    if not action:
        return jsonify({'message': "Missing 'action' parameter."}), 400

    # Find the VM in the vm_cache
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

@app.route('/validate_password', methods=['GET'])
def validate_password():
    user_password = request.args.get('password')
    correct_password = '<your_password_here>'  # Replace with the actual correct password

    if user_password == correct_password:
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False})

if __name__ == "__main__":
    vcenter_instances = list(vm_cache.keys())
    if not vcenter_instances:
        print("No vCenter servers connected. Exiting.")
    else:
        print("Connected to vCenters:", ", ".join(vcenter_instances))

    app.run(host='0.0.0.0', port=80)
