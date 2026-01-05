import os
import logging
from PySide6.QtCore import Qt, QUrl
from PySide6.QtQml import QQmlComponent
import meshroom.ui


class BaseDialog:
    qmlPath = 'qml/BaseDialog.qml'
    message = ""
    buttonMessage = "Ok"
    dialog = None

    def show(self):
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
        self.dialog.setProperty("buttonText", self.buttonMessage)

        return