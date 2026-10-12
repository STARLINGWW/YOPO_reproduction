"""Round-trip standard Image bytes over DDS/TCP to the Ubuntu22.04 container.

No host firewall/portproxy changes; Docker publishes a single loopback port.
Uses Isaac Sim's bundled Humble bridge. Does not claim closed-loop migration.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'artifacts/environment'
core=Path(sys.executable).parent/'Lib/site-packages/isaacsim/exts/isaacsim.ros2.core'
os.environ.update(ROS_DISTRO='humble',RMW_IMPLEMENTATION='rmw_fastrtps_cpp',ROS_DOMAIN_ID='42',
                  FASTRTPS_DEFAULT_PROFILES_FILE=str(ROOT/'configs/dds/tcp_client_windows.xml'),
                  ROS_LOG_DIR=str(ROOT/'artifacts/ros2_logs'))
os.environ['PATH']=str(core/'humble/lib')+os.pathsep+os.environ['PATH']
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'enable_cameras':False})
result={'status':'running','scope':'native Isaac to Linux ROS2 synthetic Image round trip over DDS/TCP'}
try:
    import omni.kit.app
    omni.kit.app.get_app().get_extension_manager().set_extension_enabled_immediate('isaacsim.ros2.bridge',True)
    for _ in range(20):app.update()
    import rclpy
    from sensor_msgs.msg import Image
    from std_msgs.msg import String
    rclpy.init(domain_id=42)
    node=rclpy.create_node('yopo_isaac_transport_probe')
    received={}
    sub=node.create_subscription(Image,'/yopo/transport_echo',lambda msg:received.__setitem__(msg.header.stamp.sec,msg),10)
    pub=node.create_publisher(Image,'/yopo/transport_input',10)
    stop_pub=node.create_publisher(String,'/yopo/transport_stop',10)
    result.update(domain_id=rclpy.get_default_context().get_domain_id(),
                  xml_profile=os.environ.get('FASTRTPS_DEFAULT_PROFILES_FILE'),pid=os.getpid())
    print('TRANSPORT_CONTEXT '+json.dumps(result),flush=True)
    samples=[]
    for i in range(10):
        raw=(np.arange(160*90,dtype=np.float32).reshape(90,160)/1000+i).tobytes()
        msg=Image();msg.header.frame_id='camera_optical';msg.header.stamp.sec=i+1
        msg.height=90;msg.width=160;msg.encoding='32FC1';msg.is_bigendian=0;msg.step=160*4;msg.data=raw
        started=time.perf_counter();deadline=time.monotonic()+30
        while i+1 not in received and time.monotonic()<deadline:
            pub.publish(msg)
            rclpy.spin_once(node,timeout_sec=.1)
            app.update()
        result.update(input_subscription_count=node.count_subscribers('/yopo/transport_input'),echo_publisher_count=node.count_publishers('/yopo/transport_echo'))
        assert i+1 in received,f'No echo for frame {i+1}; DDS discovery/data channel not established'
        echo=received[i+1]
        assert bytes(echo.data)==raw and echo.width==160 and echo.height==90 and echo.encoding=='32FC1'
        samples.append({'id':i+1,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'wall_roundtrip_ms':(time.perf_counter()-started)*1000})
    for _ in range(5):
        stop_pub.publish(String(data='probe_complete'))
        rclpy.spin_once(node,timeout_sec=.1)
    result.update(status='passed',frames=samples,byte_exact=True,port=50142)
    node.destroy_node();rclpy.shutdown()
except Exception:
    result.update(status='failed',traceback=traceback.format_exc())
finally:
    (OUTPUT/'isaac_docker_transport.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('TRANSPORT_RESULT '+json.dumps(result),flush=True)
    app.close()
