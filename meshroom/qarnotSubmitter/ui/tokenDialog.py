import logging
from PySide6.QtCore import QEventLoop
import os
import logging
from PySide6.QtCore import Qt, QUrl
from PySide6.QtQml import QQmlComponent
import meshroom.ui

from ..utils.tokenUtils import isTokenValid, save_token
from .baseDialog import BaseDialog

class TokenDialog(BaseDialog):
    qmlPath = 'qml/TokenDialog.qml'
    loop = None

    def __init__(self):
        super().__init__()

    def show(self):
        #super().show()
        self.engine = meshroom.ui.uiInstance.engine

        # Chargement du composant QML
        currentDir = os.path.dirname(os.path.realpath(__file__))
        print(self.qmlPath)
        qml_file = os.path.join(currentDir, self.qmlPath)
        component = QQmlComponent(self.engine, QUrl.fromLocalFile(qml_file))

        # Mise à jour des variables

        if component.status() == QQmlComponent.Error:
            logging.error(f"Erreur QML : {component.errorString()}")
            return False

        # Création du composant
        self.dialog = component.create()
        self.dialog.setModality(Qt.ApplicationModal)

        self.dialog.setProperty("message", self.message)
        self.dialog.setProperty("buttonText", self.buttonText)

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