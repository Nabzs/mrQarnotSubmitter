#!/usr/bin/env python
import os
import logging

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
    
    def __init__(self, parent=None):
        super(QarnotSubmitter, self).__init__(name='QarnotRender', parent=parent)
        self.reqPackages = []
        self.dialog = None 
        # On stocke le manager pour qu'il reste en vie
        self.palette_wrapper = None 

    def submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
        logging.info("Préparation Qarnot...")

        # 1. Récupération du moteur
        try:
            engine = meshroom.ui.uiInstance.engine
        except AttributeError:
            logging.error("Pas de moteur UI trouvé.")
            return False

        # 2. Création du composant
        qml_file = os.path.join(currentDir, 'QarnotTokenDialog.qml')
        component = QQmlComponent(engine, QUrl.fromLocalFile(qml_file))

        if component.status() == QQmlComponent.Error:
            logging.error(f"Erreur QML : {component.errorString()}")
            return False

        # 3. Création de la fenêtre
        self.dialog = component.create()
        if not self.dialog:
            return False

        # --- CORRECTION COULEUR ---
        # On crée une instance locale du PaletteManager liée au moteur
        # Comme elle lit QApplication.palette(), elle sera syncro avec le thème sombre
        self.palette_wrapper = PaletteManager(engine)
        
        # On injecte cet objet directement dans une propriété "palette" de la fenêtre
        self.dialog.setProperty("palette", self.palette_wrapper)
        # --------------------------

        # 4. Logique de validation
        def on_token_received(token):
            self.dialog.setProperty("errorMessage", "")
            
            if qarnot is None:
                self.dialog.setProperty("errorMessage", "Module 'qarnot' manquant.")
                return

            try:
                conn = qarnot.connection.Connection(client_token=token)
                # Test léger pour vérifier l'auth
                # conn.user_info() 
                
                logging.info("Succès connexion Qarnot.")
                self.dialog.close()
                
            except Exception as e:
                self.dialog.setProperty("errorMessage", f"Erreur : {str(e)}")

        self.dialog.acceptToken.connect(on_token_received)

        return True