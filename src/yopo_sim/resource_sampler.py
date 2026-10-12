"""Background host/process/GPU resource samples, independent of flight stepping."""
import csv,json,os,subprocess,threading,time


class ResourceSampler:
    def __init__(self,path,simulation_time,interval=1.,container_id=None):
        self.path=path;self.simulation_time=simulation_time;self.interval=interval
        self.stop_event=threading.Event();self.thread=threading.Thread(target=self._run,daemon=True)
        self.container_id=container_id

    def start(self):self.thread.start()
    def close(self):self.stop_event.set();self.thread.join(timeout=6.)

    def _run(self):
        try:
            import psutil
            process=psutil.Process();process.cpu_percent();psutil.cpu_percent()
        except ImportError:psutil=None;process=None
        with self.path.open('w',encoding='utf-8') as file:
            while not self.stop_event.is_set():
                row={'wall_unix_s':time.time(),'sim_time_s':self.simulation_time(),
                     'native_pid':os.getpid(),'scope':'native process + host totals; GPU totals include other processes'}
                if process is not None:
                    row.update(native_rss_bytes=process.memory_info().rss,native_cpu_percent=process.cpu_percent(),
                               host_cpu_percent=psutil.cpu_percent(),host_available_ram_bytes=psutil.virtual_memory().available)
                try:
                    result=subprocess.run(['nvidia-smi','--query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw',
                        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
                    if result.returncode:raise RuntimeError(result.stderr.strip())
                    rows=list(csv.reader(result.stdout.strip().splitlines()));devices=[]
                    for values in rows:
                        fields=['gpu_index','gpu_utilization_percent','gpu_used_memory_MiB','gpu_total_memory_MiB','gpu_power_W']
                        item={}
                        for name,value in zip(fields,values):
                            try:item[name]=float(value)
                            except ValueError:item[name]=None
                        devices.append(item)
                    row['gpus']=devices
                except Exception as exc:row['gpu_sample_error']=str(exc)
                file.write(json.dumps(row)+'\n');file.flush()
                if self.container_id:
                    sample={'wall_unix_s':time.time(),'sim_time_s':self.simulation_time(),'scope':'selected Docker container, including its launcher processes','container_id':self.container_id}
                    try:
                        command_started=time.perf_counter()
                        stats=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}',self.container_id],
                            capture_output=True,text=True,timeout=3,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
                        if stats.returncode:raise RuntimeError(stats.stderr.strip())
                        sample['docker_stats']=json.loads(stats.stdout.strip());sample['query_wall_ms']=(time.perf_counter()-command_started)*1000
                    except Exception as exc:sample['error']=str(exc)
                    with (self.path.parent/'container_resources.jsonl').open('a',encoding='utf-8') as target:target.write(json.dumps(sample)+'\n')
                self.stop_event.wait(self.interval)
