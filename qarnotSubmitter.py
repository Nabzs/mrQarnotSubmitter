import os
import sys
import qarnot
from datetime import datetime
import logging


from meshroom.core.submitter import BaseSubmitter

currentDir = os.path.dirname(os.path.realpath(__file__))



token = "84fb43be76e78533713fbce9fc73d4e16a8ddbe6bb57256257c88c1f2ae2c31e99b98e342f0562398e13ea17734f02528dda78aae32f2529c2ec5d7338ff6c92"

class QarnotSubmitter(BaseSubmitter):

    def __init__(self, parent=None):
        super(QarnotSubmitter, self).__init__(name="QarnotRender", parent=parent)
        self.reqPackages = []
    
    def setup_bucket(self, conn, bucket_name):
        try:
            bucket = conn.retrieve_bucket(bucket_name)
            print("Found input bucket.")
        except qarnot.exceptions.BucketStorageUnavailableException as e:
            bucket = conn.create_bucket(bucket_name)
            print("Created input bucket.")
        
        return bucket
    
    def upload_path_to_bucket(self, bucket_name, folder_path):
        conn = qarnot.connection.Connection(client_token=token)
        destination_bucket = self.setup_buckets(conn, bucket_name)
        
        print(f"Syncing local {folder_path} folder to input bucket '{bucket_name}'...")
        destination_bucket.sync_directory(folder_path)
        print("Sync complete.")
            
        
    def download_path_from_bucket(self, bucket_name, folder_path):
        conn = qarnot.connection.Connection(client_token=token)
        source_bucket = self.setup_buckets(conn, bucket_name)
        
        print("Syncing output bucket 'meshroom-out' to local 'out' folder...")
        source_bucket.sync_remote_to_local(bucket_name)
        print("Sync complete.")

    def submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
        
        if not filepath:
            print("Please provide a subfolder name containing input data for the photogrammetry task. It should be located directly within the 'in' folder.", file=sys.stderr)
            return
        
        print(f"Starting photogrammetry task for subfolder: {filepath}")

        # TASK SETUP
        conn = qarnot.connection.Connection(client_token=token)

        profile = "docker-nvidia-batch"
        task = conn.create_task("meshroom-test", profile, 1)
        task.constants["DOCKER_REPO"] = "alicevision/meshroom" #os.environ.get("MESHROOM_DOCKER_REPO")
        task.constants["DOCKER_TAG"] = "2025.1.0-av3.3.0-ubuntu22.04-cuda12.1.1" #os.environ.get("MESHROOM_DOCKER_TAG")
        task.constants['DOCKER_CMD'] = f"/opt/Meshroom_bundle/meshroom_compute --input /job/{filepath} --output /job/output"

        # BUCKET CONNECTION

        input_bucket = self.setup_bucket(conn, "meshroomIn")
        output_bucket = self.setup_bucket(conn, "meshroomOut")
        task.resources.append(input_bucket)
        task.results = output_bucket

        # TASK START
        task.submit()

        # MONITORING LOOP
        last_state = ''
        done = False

        while not done:

            # OUTPUT HANDLING
            _latest_out = task.fresh_stdout()
            if _latest_out:
                for line in _latest_out.replace("\\n", "\n").splitlines():
                    print(line)

            _latest_err = task.fresh_stderr()
            if _latest_err:
                for line in _latest_err.replace("\\n", "\n").splitlines():
                    print(line, file=sys.stderr)

            if task.state != last_state:
                last_state = task.state
                print("=" * 10)
                print("-- {}".format(last_state))

            if task.state == 'FullyExecuting':
                instance_info = task.status.running_instances_info.per_running_instance_info[0]
                cpu = instance_info.cpu_usage
                memory = instance_info.current_memory_mb
                print("-- ", datetime.now(), "| {:.2f} % CPU | {:.2f} MB MEMORY".format(cpu, memory))

            # Display errors on failure
            if task.state == 'Failure':
                print("-- Errors: %s" % task.errors[0])
                done = True

            done = task.wait(10)

            if task.state == 'Success':
                print("-- Task completed successfully.")
                sync_folder("out")
                print("Output synchronized to local 'out' folder.")

        pass
