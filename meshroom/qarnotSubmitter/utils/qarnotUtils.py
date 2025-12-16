import os
import sys
import qarnot
import json
import tempfile
from datetime import datetime
import logging
import uuid
import threading

from meshroom.core import graph as pg

currentDir = os.path.dirname(os.path.realpath(__file__))
from .tokenUtils import get_token

def setup_bucket(conn, bucket_name, is_output=False):
    # Récupère ou crée le bucket
    if(is_output):
        try:
            bucket = conn.retrieve_bucket(bucket_name)
            bucket.delete()
        except:
            pass
            
    bucket = conn.retrieve_or_create_bucket(bucket_name)
    print(f"Bucket ready: {bucket_name}")
    return bucket
 
def load_mg_file(filepath):
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
        
    print(f"mg file {os.path.basename(filepath)} loaded")

    return data

def update_mg_file(mg_data):
    updated_data = mg_data
    images_paths = {}
    
    for viewpoint in updated_data["graph"]["CameraInit_1"]["inputs"]["viewpoints"]:
        images_paths[os.path.basename(viewpoint["path"])] = os.path.abspath(viewpoint["path"])
        viewpoint["path"] = os.path.join("/job/", os.path.basename(viewpoint["path"]))
    
    return updated_data, images_paths


def save_tmp_mg_file(data, temp_path, filename=None):
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

def delete_file(path):
    """
    Supprime un fichier si il existe.
    """
    path = os.path.abspath(path)
    if os.path.isfile(path):
        os.remove(path)
        return True
    
    print("mg temp file deleted")
    return False


def download_cache_from_bucket(output_bucket, local_file_path, tmp_file_path):
    
    remote_graph = pg.loadGraph(tmp_file_path)
    local_graph = pg.loadGraph(local_file_path)
    
    local_dir = os.path.join(os.path.dirname(local_file_path), "MeshroomCache")
    remote_dir = "MeshroomCache"
    
    for i in range(len(remote_graph.nodes)):
        local_node = local_graph.nodes[i]
        remote_node = remote_graph.nodes[i]
        
        # Crée le répertoire du node s'il n'existe pas
        local_node_dir = os.path.join(os.path.join(local_dir, local_node.nodeType), local_node._uid)
        os.makedirs(local_node_dir, exist_ok=True)
        remote_node_dir = "/".join([remote_dir, remote_node.nodeType, remote_node._uid])
        
        output_bucket.sync_remote_to_local(local_node_dir, remote_node_dir)
        
        # print(f"Cache {local_node.nodeName} downloaded from bucket")
        
        
    

def launch_task(nodes, edges, filepath, submitLabel="{projectName}"):
            
    mg_data = load_mg_file(filepath)
    
    tmp_data, uploads_paths = update_mg_file(mg_data)

    tmp_file_path = save_tmp_mg_file(tmp_data, os.path.abspath("C:/tmp"))
    
    uploads_paths[os.path.basename(tmp_file_path)] = tmp_file_path

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
    token = get_token()
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
    input_bucket = setup_bucket(conn, "meshroomIn")
    output_bucket = setup_bucket(conn, "meshroomOut")

    
    # Sync files to input bucket: expects a mapping {local_path: remote_name}
    print("Uploading input data to bucket 'meshroomIn'...")
    input_bucket.sync_files(uploads_paths)
    print("Upload complete.")
    
    # Attacher les buckets
    task.resources.append(input_bucket)   # OK, c'est une liste
    task.results = output_bucket
        
    # TASK START
    task._snapshot_whitelist = "^(.*status.*|.*\.mg)"
    task.submit()
    
    # StatusData.initExternSubmit()

    # MONITORING LOOP
    last_state = ""
    done = False

    while not done:
        try:
            task.instant()
        except Exception as e:
            print(f"Error retrieving task status: {e}", file=sys.stderr)

        try:
            output_bucket.get_file(os.path.basename(tmp_file_path), local=tmp_file_path)
            download_cache_from_bucket(output_bucket, filepath, tmp_file_path)
        except:
            pass
        
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
        
        if task.state == "Success":
    
            # Récupère le fichier mg de meshroomOut 
            print("-- Task completed successfully.")
            done = True

        done = task.wait(10)
    
    
    # Récupérer les résultats en local
    print("Downloading results from bucket")
    output_bucket.get_file(os.path.basename(tmp_file_path), local=tmp_file_path)
    download_cache_from_bucket(output_bucket, filepath, tmp_file_path)
    print("Resluts synchronized to local folder")
    
    delete_file(tmp_file_path)
    
    return done

def async_launch_task(nodes, edges, filepath, submitLabel="{projectName}"):
    task_thread = threading.Thread(
        target=launch_task,
        args=(nodes, edges, filepath, submitLabel),
        daemon=True
    )
    
    task_thread.start()
    
    print("La tâche a été lancée dans un thread en arrière-plan.")

    return task_thread