#!/usr/bin/env python
import os
import logging
#from src.tokenUtils import save_token, get_token

import keyring
from keyring.backends import Windows
keyring.set_keyring(Windows.WinVaultKeyring())

# Identifiants pour le stockage
SERVICE_ID = "qarnot_submitter"
KEY_NAME = "qarnot_token"

def save_token(token):
    try:
        # Stocke le token de manière sécurisée
        keyring.set_password(SERVICE_ID, KEY_NAME, token)
        print("Token sécurisé avec succès.")
    except Exception as e:
        print(f"Erreur lors du stockage : {e}")

def get_token():
    try:
        # Récupère le token sans jamais l'écrire sur le disque
        token = keyring.get_password(SERVICE_ID, KEY_NAME)
        if token:
            return token
        else:
            print("Aucun token trouvé.")
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération : {e}")
        return None

def delete_token():
    try:
        keyring.delete_password(SERVICE_ID, KEY_NAME)
        print("Token supprimé.")
    except keyring.errors.PasswordDeleteError:
        print("Le token n'existait pas.")


# Import Qarnot
try:
    import qarnot
except ImportError:
    qarnot = None
    logging.warning("Module 'qarnot' manquant.")

# Compatibilité Qt
try:
    from PySide2.QtCore import QUrl
    from PySide2.QtQml import QQmlComponent
    from PySide2.QtGui import QGuiApplication
except ImportError:
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtGui import QGuiApplication
    except ImportError:
        logging.error("Impossible de charger PySide.")

from meshroom.core.submitter import BaseSubmitter
import meshroom.ui
# On importe la classe existante de Meshroom
from meshroom.ui.palette import PaletteManager

currentDir = os.path.dirname(os.path.realpath(__file__))

class QarnotSubmitter(BaseSubmitter):
    dialog = None 
    engine = None

    def __init__(self, parent=None):
        super(QarnotSubmitter, self).__init__(name='QarnotRender', parent=parent)
        self.reqPackages = []
        # On stocke le manager pour qu'il reste en vie
        self.palette_wrapper = None 

    def cancel_submit(self, rrrr):
        reconstruction = self.engine.rootContext().contextProperty("_reconstruction")
        reconstruction.graph.clearSubmittedNodes()
        print("Closing token dialog")
        # Pas top mais ça marche
        rrrr.close()

        # self.dialog.close()

    # 4. Logique de validation
    def on_token_received(self, token, rrrr):
        rrrr.setProperty("errorMessage", "")
        
        if qarnot is None:
            rrrr.setProperty("errorMessage", "Module 'qarnot' manquant.")
            return

        try:
            conn = qarnot.connection.Connection(client_token=token)
            # Test léger pour vérifier l'auth
            # conn.user_info() 

            logging.info("Succès connexion Qarnot.")
            save_token(token)
            # self.dialog.close()
        except Exception as e:
            rrrr.setProperty("errorMessage", f"Erreur : token pas valide.")

    def true_submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
        # On fait des vrais trucs
        pass

    def submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
        logging.info("Préparation Qarnot...")

        token = get_token()

        if token:
            self.true_submit(nodes, edges, filepath, submitLabel="{projectName}")
        else:
            # 1. Récupération du moteur
            try:
                self.engine = meshroom.ui.uiInstance.engine
            except AttributeError:
                logging.error("Pas de moteur UI trouvé.")

                return False
            # 2. Création du composant
            qml_file = os.path.join(currentDir, 'QarnotTokenDialog.qml')
            component = QQmlComponent(self.engine, QUrl.fromLocalFile(qml_file))

            if component.status() == QQmlComponent.Error:
                logging.error(f"Erreur QML : {component.errorString()}")
                return False

            # 3. Création de la fenêtre
            self.dialog = component.create()

            print(self.dialog)
            if not self.dialog:
                return False

            # --- CORRECTION COULEUR ---
            # On crée une instance locale du PaletteManager liée au moteur
            # Comme elle lit QApplication.palette(), elle sera syncro avec le thème sombre
            # self.palette_wrapper = PaletteManager(engine)
            
            # On injecte cet objet directement dans une propriété "palette" de la fenêtre
            self.dialog.setProperty("palette", self.palette_wrapper)
            # --------------------------

            self.dialog.acceptToken.connect(self.on_token_received)
            self.dialog.cancel.connect(self.cancel_submit)
