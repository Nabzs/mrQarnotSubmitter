import os
import logging
import meshroom.ui
from meshroom.ui.palette import PaletteManager

from ..utils.tokenUtils import isTokenValid, save_token

# Compatibilité Qt
try:
    from PySide2.QtCore import QEventLoop, Qt, QUrl
    from PySide2.QtQml import QQmlComponent
    from PySide2.QtGui import QGuiApplication
except ImportError:
    try:
        from PySide6.QtCore import QEventLoop, Qt, QUrl
        from PySide6.QtQml import QQmlComponent
        from PySide6.QtGui import QGuiApplication
    except ImportError:
        logging.error("Impossible de charger PySide.")

class QarnotDialog:

    def __init__(self):
        self.palette_wrapper = None
        self.engine = None

    def showDialog(self):
        self.engine = meshroom.ui.uiInstance.engine

        # Chargement du composant QML
        currentDir = os.path.dirname(os.path.realpath(__file__))
        qml_file = os.path.join(currentDir, 'qml/QarnotTokenDialog.qml')
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(qml_file))

        if component.status() == QQmlComponent.Error:
            logging.error(f"Erreur QML : {component.errorString()}")
            return False

        # Création du composant
        self.dialog = component.create()
        
        self.dialog.setModality(Qt.ApplicationModal)

        # On rend la fonction bloquante (comme ça on attend d'avoir le token pour exécuter la suite)
        self.loop = QEventLoop()

        self.dialog.submitSignal.connect(self.on_submit)
        self.dialog.cancelSignal.connect(self.on_cancel)

        self.dialog.setVisible(True)
        self.loop.exec_()

        # Quand c'est fini on return rien

        return
    
    def on_cancel(self, dialog):
        reconstruction = self.engine.rootContext().contextProperty("_reconstruction")
        reconstruction.graph.clearSubmittedNodes()
        print("Closing token dialog")
        dialog.close()

    def on_submit(self, token, dialog):
        dialog.setProperty("errorMessage", "")

        if isTokenValid(token):
            logging.info("Succès connexion Qarnot.")
            save_token(token)
            dialog.close()
            self.loop.quit() 
        else:
            dialog.setProperty("errorMessage", f"Erreur : le token n'a pas pu être validé. Vérifiez votre connection ou changez de token.")