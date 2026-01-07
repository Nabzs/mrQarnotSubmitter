import os
import sys
import qarnot
import json
import tempfile
from datetime import datetime
import logging
import uuid
#import threading
from concurrent.futures import ThreadPoolExecutor

from meshroom.core import graph as pg
from meshroom.core.desc.computation import Level


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


def download_cache_from_bucket(output_bucket, uid_map, is_snapshot=True):
    for local_node_dir, remote_node_dir in uid_map.items():        
        output_bucket.sync_remote_to_local(local_node_dir, remote_node_dir)
        
        if not is_snapshot:
            print(f"{remote_node_dir} downloaded from bucket")


def uid_mapping(local_nodes, local_file_path, tmp_file_path):
    uid_map = {}

    remote_nodes = pg.loadGraph(tmp_file_path).nodes
    
    local_dir = os.path.join(os.path.dirname(local_file_path), "MeshroomCache")
    remote_dir = "MeshroomCache"
    
    for local_node in local_nodes:
        for remote_node in remote_nodes:
            if local_node.name == remote_node.name:
                # Crée le répertoire du node s'il n'existe pas
                local_node_dir = os.path.join(os.path.join(local_dir, local_node.nodeType), local_node._uid)
                os.makedirs(local_node_dir, exist_ok=True)
                remote_node_dir = "/".join([remote_dir, remote_node.nodeType, remote_node._uid])

                uid_map[local_node_dir] = remote_node_dir

    print("uid fully mapped")
    
    return uid_map


def get_running_task_for_project(nodes):
    """
    Returns a running qarnot task for the corresponding nodes if it exists, or None otherwise
    
    :param nodes: List of nodes computed by the remote qarnot task
    """
    token = get_token()
    conn = qarnot.connection.Connection(client_token=token)

    for remote_task in conn.all_tasks():
        if remote_task.state in ['Submitted', 'FullyExecuting', 'FullyDispatched']:
            missingNodes = False
            
            for node in nodes:
                if node._uid not in remote_task.tags:
                    missingNodes = True

            if not missingNodes:
                return remote_task


def start_task(nodes, edges, filepath, submitLabel):
    print(submitLabel)
    nodesToTask = mapEdgesFromOrigin(edges, findOriginNodes(edges))

    # Get the data of the mg project file
    mg_data = load_mg_file(filepath)
    
    tmp_data, uploads_paths = update_mg_file(mg_data)

    tmp_filepath = save_tmp_mg_file(tmp_data, os.path.abspath("C:/tmp"))
    
    uploads_paths[os.path.basename(tmp_filepath)] = tmp_filepath

    # Normaliser le chemin fourni
    abs_path = os.path.abspath(filepath)

    # dossier du projet : ex. C:\Users\Nabil\Desktop\MeshroomTest
    project_dir = os.path.dirname(abs_path)
    # nom du fichier dans le conteneur : a.mg
    container_input_rel = os.path.basename(tmp_filepath)
    print(f"Detected file input. Project dir: '{project_dir}', file: '{container_input_rel}'")

    # TASK SETUP
    token = get_token()
    conn = qarnot.connection.Connection(client_token=token)

    task = conn.create_task(
        f"meshroom-task ({os.path.basename(abs_path)})",    # Nom de la tâche
        "docker-nvidia-batch",                              # Profil de la tâche
    )


    # Type de pricing (on-demand évite que la tâche soit coupée en plein milieu)
    task.scheduling_type = qarnot.scheduling_type.OnDemandScheduling
    task.constants["DOCKER_REPO"] = "alicevision/meshroom"
    task.constants["DOCKER_TAG"] = "2025.1.0-av3.3.0-ubuntu22.04-cuda12.1.1"

    # Commande Meshroom dans le conteneur
    docker_graph = f"/job/{container_input_rel}"
    task.constants["DOCKER_CMD"] = (f"/opt/Meshroom_bundle/meshroom_compute {docker_graph} --toNode {nodes[-1].name}")

    # On enregistre les UIDs des nodes sur la tâche (permet de retrouver la tâche en cas de crash)
    task.tags = [node._uid for node in nodes]
    task.labels = {
        'tmp_filepath': tmp_filepath,
        'filepath': filepath
    }

    # BUCKETS
    input_bucket = setup_bucket(conn, "meshroomIn")
    output_bucket = setup_bucket(conn, "meshroomOut")

    # Sync files to input bucket: expects a mapping {local_path: remote_name}
    print("Uploading input data to bucket 'meshroomIn'...")
    input_bucket.sync_files(uploads_paths)
    print("Upload complete.")
    
    # Attacher les buckets
    task.resources.append(input_bucket)
    task.results = output_bucket
        
    # TASK START
    task._snapshot_whitelist = "^(.*status.*|.*\.mg)"
    task.submit()
    
    return task


def watch_task(task, nodes):

    raise qarnot.exceptions.NotEnoughCreditsException

    # BUCKETS
    token = get_token()
    conn = qarnot.connection.Connection(client_token=token)
    input_bucket = setup_bucket(conn, "meshroomIn")
    output_bucket = setup_bucket(conn, "meshroomOut")

    # MONITORING LOOP
    last_state = ""
    done = False
    uid_map = {}

    tmp_file_path = task.labels["tmp_filepath"]
    filepath = task.labels["filepath"]

    while not done:
        try:
            task.instant()
        except Exception as e:
            print(f"Error retrieving task status: {e}", file=sys.stderr)
        
        # OUTPUT HANDLING
        _latest_out = task.fresh_stdout()
        if _latest_out:
            for line in _latest_out.replace("\\n", "\n").splitlines():
                print(line)

        _latest_err = task.fresh_stderr()
        if _latest_err:
            for line in _latest_err.replace("\\n", "\n").splitlines():
                print(line, file=sys.stderr)

        if task.state == "FullyExecuting":

            instance_info = task.status.running_instances_info.per_running_instance_info[0]
            cpu = instance_info.cpu_usage
            memory = instance_info.current_memory_mb
            print("-- ", datetime.now(), "| {:.2f} % CPU | {:.2f} MB MEMORY".format(cpu, memory))
            download_cache_from_bucket(output_bucket, uid_map)

        elif task.state == "Failure":
            print("-- Errors: %s" % task.errors[0])

            done = True
        
        elif task.state == "Success":
    
            # Récupère le fichier mg de meshroomOut 
            print("-- Task completed successfully.")
            done = True

        if task.state != last_state:
            last_state = task.state
            print("=" * 10)
            print("-- {}".format(last_state))

            if format(task.state) == "Submitted":
                print("Waiting for tasks to be dispached to the qarnot rendering farm (this may take a few minutes)...")
            if format(task.state) == "FullyDispatched":
                print("Waiting for tasks to start rendering (this may take a few minutes)...")
            if format(task.state) == "FullyExecuting":
                task.instant()
                output_bucket.get_file(os.path.basename(tmp_file_path), local=tmp_file_path)
                uid_map = uid_mapping(nodes, filepath, tmp_file_path)
                print(uid_map)


        done = task.wait(5)
    
    # Récupérer les résultats en local
    print("Downloading results from bucket")
    output_bucket.get_file(os.path.basename(tmp_file_path), local=tmp_file_path)
    download_cache_from_bucket(output_bucket, uid_map, False)
    print("Results synchronized to local folder")
    
    delete_file(tmp_file_path)
    
    return done


def async_watch_task(task, nodes):
    with ThreadPoolExecutor() as executor:
        future = executor.submit(watch_task, task, nodes)
        future.result()
        
        print("La tâche a été lancée dans un thread en arrière-plan.")

        return future

def isGPU(node):
    desc = node.nodeDesc  # ← LA BONNE SOURCE

    return (desc.gpu != Level.NONE)

def findOriginNodes(edges):
    dst = {dst for _, dst in edges}
    src  = {src for src, _ in edges}

    return list(dst - src)

def isOriginNode(node, edges):
    dst = {dst for dst, src in edges}
    return not (node in dst)

def mapEdgesFromOrigin(edges, originNodes):
    treatedNodes = []
    nodesToTask = {}

    for originNode in originNodes:
        treatedNodes.append(originNode)
        nodesToTask[originNode.name] = [isGPU(originNode), 0]

        for e in [dst for dst, src in edges if src == originNode]:
            nodesToTask = mapEdges(edges, e, originNode, nodesToTask, 1, treatedNodes)
        
        
    return nodesToTask

def mapEdges(edges, currentNode, previousNode, nodesToTask, depth, treatedNodes):

    treatedNodes.append(currentNode)
    if isGPU(currentNode) == isGPU(previousNode):
        nodesToTask[currentNode.name] = nodesToTask.pop(previousNode.name)
    else:
        nodesToTask[currentNode.name] = [isGPU(currentNode), depth]

    for nextNode in [dst for dst, src in edges if src == currentNode]:
        if not nextNode in treatedNodes:
            nodesToTask = mapEdges(edges, nextNode, currentNode, nodesToTask, depth+1, treatedNodes)
        elif isGPU(nextNode) == isGPU(currentNode):
            nodesToTask.pop(currentNode.name)
        
    return nodesToTask