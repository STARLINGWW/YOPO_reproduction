"""Container-side ROS2 image echo for a bounded native Isaac transport check."""
from pathlib import Path
import json
import time
import os
import rclpy
from sensor_msgs.msg import Image
from std_msgs.msg import String

output=Path('/workspace/artifacts/environment')
rclpy.init(domain_id=42)
node=rclpy.create_node('yopo_transport_echo')
publisher=node.create_publisher(Image,'/yopo/transport_echo',10)
received=[]
stop=[]
def callback(message):
    received.append({'sec':message.header.stamp.sec,'nanosec':message.header.stamp.nanosec,'bytes':len(message.data)})
    publisher.publish(message)
subscription=node.create_subscription(Image,'/yopo/transport_input',callback,10)
stop_sub=node.create_subscription(String,'/yopo/transport_stop',lambda msg:stop.append(msg.data),10)
(output/'transport_server_ready.json').write_text(json.dumps({'status':'ready','scope':'ready is not communication proof'}))
deadline=time.monotonic()+180
last_heartbeat=0.
while time.monotonic()<deadline and not stop:
    rclpy.spin_once(node,timeout_sec=.1)
    if time.monotonic()-last_heartbeat>2:
        last_heartbeat=time.monotonic()
        (output/'transport_server_live.json').write_text(json.dumps({'pid':os.getpid(),'domain':node.context.get_domain_id(),
            'input_publishers':node.count_publishers('/yopo/transport_input'),'echo_subscribers':node.count_subscribers('/yopo/transport_echo'),
            'images_received':len(received),'monotonic':time.monotonic()}))
report={'status':'passed' if received and stop else 'timeout','images':received,'stop_received':bool(stop),'scope':'synthetic image echo only'}
(output/'transport_server_result.json').write_text(json.dumps(report,indent=2))
node.destroy_node();rclpy.shutdown()
print(json.dumps(report),flush=True)
