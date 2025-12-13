import os
import sys
import qarnot
import json
import tempfile
from datetime import datetime
import logging
import uuid


from meshroom.core import graph as pg
from meshroom.core.submitter import BaseSubmitter

currentDir = os.path.dirname(os.path.realpath(__file__))

# ⚠️ évite de committer ce token dans un repo public
token = "881daefdc9d361680f814a2e62811ee325d6b10761e757d10c6d4e2b755b26d58266a1e2d6096fff8a75cd14ea36d01dec1c12dbf4f21ac2deda33e9340229f4"


class QarnotSubmitter(BaseSubmitter):

    def __init__(self, parent=None):
        super(QarnotSubmitter, self).__init__(name="QarnotRender", parent=parent)
        self.reqPackages = []

    def setup_bucket(self, conn, bucket_name):
        # Récupère ou crée le bucket
        bucket = conn.retrieve_or_create_bucket(bucket_name)
        print(f"Bucket ready: {bucket_name}")
        return bucket

    def upload_path_to_bucket(self, bucket_name, folder_path):
        conn = qarnot.connection.Connection(client_token=token)
        destination_bucket = self.setup_bucket(conn, bucket_name)

        print(f"Syncing local folder '{folder_path}' to bucket '{bucket_name}'...")
        destination_bucket.sync_directory(folder_path)
        print("Sync complete.")

    def download_path_from_bucket(self, bucket_name, folder_path):
        conn = qarnot.connection.Connection(client_token=token)
        source_bucket = self.setup_bucket(conn, bucket_name)

        print(f"Syncing bucket '{bucket_name}' to local folder '{folder_path}'...")
        source_bucket.sync_remote_to_local(folder_path)
        print("Sync complete.")        
        

    def load_mg_file(self, filepath):
        """
        Charge un fichier .mg (JSON Meshroom) et renvoie le dictionnaire Python.
        
        Args:
            filepath (str): Chemin vers le fichier .mg
            
        Returns:
            dict: Contenu JSON chargé
        Raises:
            FileNotFoundError: si le fichier n'existe pas
            json.JSONDecodeError: si le .mg n'est pas un JSON valide
        """
        filepath = os.path.abspath(filepath)

        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"MG file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def update_mg_file(self, mg_data):
        updated_data = mg_data
        folder_path = os.path.dirname(mg_data["graph"]["CameraInit_1"]["inputs"]["viewpoints"][0]["path"])
        
        for viewpoint in updated_data["graph"]["CameraInit_1"]["inputs"]["viewpoints"]:
            viewpoint["path"] = os.path.join("/job/", os.path.basename(viewpoint["path"]))
        
        return updated_data, folder_path
    
    # def get_mg_file(self, output_bucket, tmp_file_path):
    #     output_bucket.get_file(os.path.basename(tmp_file_path) ,os.path.abspath(tmp_file_path))

            
    
    def save_tmp_mg_file(self, data, temp_path, filename=None):
        """
        Sauvegarde un fichier .mg temporaire.
        
        - temp_path peut être :
            ✔ un dossier (ex: "C:/tmp")
            ✔ un chemin complet de fichier (ex: "C:/tmp/myfile.mg")
        
        - filename : nom du fichier si temp_path est un dossier
        """

        temp_path = os.path.abspath(temp_path)

        # Si temp_path est un dossier → générer un fichier
        if os.path.isdir(temp_path) or temp_path.endswith(("/", "\\")):
            os.makedirs(temp_path, exist_ok=True)

            # si pas de nom fourni → nom unique
            if filename is None:
                filename = f"meshroom_{uuid.uuid4().hex}.mg"

            temp_path = os.path.join(temp_path, filename)

        else:
            # temp_path est un fichier → créer le dossier parent
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

        # Écrire les données JSON
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return temp_path

    def delete_tmp_mg_file(self, path):
        """
        Supprime un fichier si il existe.
        """
        path = os.path.abspath(path)
        if os.path.isfile(path):
            os.remove(path)
            return True
        return False
    
    
    def download_cache_from_bucket(self, output_bucket, local_file_path, tmp_file_path):
        
        remote_graph = pg.loadGraph(tmp_file_path)
        local_graph = pg.loadGraph(local_file_path)
        
        local_dir = os.path.join(os.path.dirname(local_file_path), "MeshroomCache")
        remote_dir = "MeshroomCache"
        
        for i in range(len(local_graph.nodes)):
            local_node = local_graph.nodes[i]
            remote_node = remote_graph.nodes[i]
            
            # Crée le répertoire du node s'il n'existe pas
            local_node_dir = os.path.join(os.path.join(local_dir, local_node.nodeType), local_node._uid)
            os.makedirs(local_node_dir, exist_ok=True)
            
            remote_node_dir = "/".join([remote_dir, remote_node.nodeType, remote_node._uid])

            print(local_node_dir, remote_node_dir)
            
            output_bucket.sync_remote_to_local(local_node_dir, remote_node_dir)


    def submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
        
        # graph = pg.loadGraph(filepath)
        
        # startNodes=None
        # nodes, edges = graph.dfsOnFinish(startNodes=startNodes)
        
        # print(nodes[0].att)
                
        mg_data = self.load_mg_file(filepath)
        
        tmp_data, image_path = self.update_mg_file(mg_data)

        tmp_file_path = self.save_tmp_mg_file(tmp_data, image_path, "meshroom_423f3335b845457499b7588d76dd386a.mg")

        if not filepath:
            print("Please provide a path to the Meshroom project or input folder.", file=sys.stderr)
            return

        print(f"Starting photogrammetry task for subfolder: {filepath}")

        # Normaliser le chemin fourni par
        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            print(f"Error: path '{abs_path}' does not exist!", file=sys.stderr)
            return

        # Si filepath est un fichier (ex: a.mg)
        if os.path.isfile(abs_path):
            # dossier du projet : ex. C:\Users\Nabil\Desktop\MeshroomTest
            project_dir = os.path.dirname(abs_path)
            # nom du fichier dans le conteneur : a.mg
            container_input_rel = os.path.basename(tmp_file_path)
            print(f"Detected file input. Project dir: '{project_dir}', file: '{container_input_rel}'")
        else:
            # Si c'est un dossier, on considère que c'est directement le dossier de projet
            project_dir = abs_path
            container_input_rel = ""  # on utilisera /job directement
            print(f"Detected directory input. Project dir: '{project_dir}'")

        # TASK SETUP
        conn = qarnot.connection.Connection(client_token=token)

        profile = "docker-nvidia-batch"
        task = conn.create_task("meshroom-test", profile, 1)

        task.constants["DOCKER_REPO"] = "alicevision/meshroom"
        task.constants["DOCKER_TAG"] = "2025.1.0-av3.3.0-ubuntu22.04-cuda12.1.1"

        # Chemin d'input dans le conteneur
        if container_input_rel:
            # ex: /job/a.mg
            docker_graph = f"/job/{container_input_rel}"
        else:
            # si on reçoit un dossier, il faudrait décider quel .mg lancer
            print("Error: a .mg file is required as input.", file=sys.stderr)
            return

        # Commande Meshroom dans le conteneur
        task.constants["DOCKER_CMD"] = (f"/opt/Meshroom_bundle/meshroom_compute {docker_graph}")

        # BUCKETS
        input_bucket = self.setup_bucket(conn, "meshroomIn")
        output_bucket = self.setup_bucket(conn, "meshroomOut")

        # Sync des données d'entrée : on envoie UNIQUEMENT le dossier du projet
        if not os.path.isdir(image_path):
            print(f"Error: project directory '{image_path}' does not exist or is not a directory!", file=sys.stderr)
            return

        print(f"Uploading input data from '{image_path}' to bucket 'meshroomIn'...")
        input_bucket.sync_directory(image_path)
        print("Upload complete.")
        
        # Attacher les buckets
        task.resources.append(input_bucket)   # OK, c'est une liste
        task.results = output_bucket

        # TASK START
        task.submit()

        # MONITORING LOOP
        last_state = ""
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

            if task.state == "FullyExecuting":
                instance_info = task.status.running_instances_info.per_running_instance_info[0]
                cpu = instance_info.cpu_usage
                memory = instance_info.current_memory_mb
                print("-- ", datetime.now(), "| {:.2f} % CPU | {:.2f} MB MEMORY".format(cpu, memory))

            if task.state == "Failure":
                print("-- Errors: %s" % task.errors[0])
                done = True

            done = task.wait(10)

            if task.state == "Success":
        
                # Récupère le fichier mg de meshroomOut 
                output_bucket.get_file(os.path.basename(tmp_file_path), local=tmp_file_path)
                self.download_cache_from_bucket(output_bucket, filepath, tmp_file_path)

                print("-- Task completed successfully.")
                # Récupérer les résultats dans ./out
                self.download_path_from_bucket("meshroomOut", "out")
                print("Output synchronized to local 'out' folder.")
                done = True
                
            
