"""Refresh project-local DDS NAT addresses; never changes host network settings."""
from pathlib import Path
from datetime import datetime
import ipaddress
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
output=subprocess.check_output(['docker','compose','run','--rm','-T','ros','getent','ahostsv4','host.docker.internal'],cwd=ROOT,text=True)
address=str(ipaddress.IPv4Address(output.split()[0]))
namespace='http://www.eprosima.com/XMLSchemas/fastRTPS_Profiles'
ET.register_namespace('',namespace)
ns={'d':namespace}
client=ROOT/'configs/dds/tcp_client_windows.xml'
tree=ET.parse(client)
tree.find('.//d:wan_addr',ns).text=address
tree.write(client,encoding='utf-8',xml_declaration=True)
server=ROOT/'configs/dds/tcp_server.xml'
tree=ET.parse(server)
tree.find('.//d:initialPeersList/d:locator/d:tcpv4/d:address',ns).text=address
tree.write(server,encoding='utf-8',xml_declaration=True)
report={'configured_at':datetime.now().astimezone().isoformat(),'docker_host_ipv4':address,
        'docker_published_address':'127.0.0.1','docker_port':50142,'native_loopback_port':50143,
        'domain_id':42,'host_firewall_modified':False,'host_portproxy_modified':False,
        'transport':'ROS2 Fast DDS TCPv4, fixed bidirectional locators',
        'reference':'https://fast-dds.docs.eprosima.com/en/2.6.x/fastdds/transport/tcp/tcp.html'}
(ROOT/'artifacts/environment/dds_configuration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
