import os
import logging
import threading 
from PySide6.QtCore import QEventLoop, Qt, QUrl, QTimer, QByteArray, QMetaObject, Q_ARG, QObject, Signal
from PySide6.QtQml import QQmlComponent
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
import meshroom.ui
from meshroom.ui.palette import PaletteManager

from .dialog import QarnotDialog
from ..utils.tokenUtils import get_token, isTokenValid, delete_token, get_user_info

def formatBytes(bytesValue):
    """Convertit un nombre d'octets en une chaîne lisible (B, KB, MB, GB, TB)."""
    if bytesValue is None:
        return "N/A"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    i = 0
    size = bytesValue
    
    while size >= 1024 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.2f} {units[i]}"

class Menu(QObject):
    data_ready = Signal(object, bool, object)
    dialog = None

    def __init__(self):
        super().__init__()
        self.injected_menu_ref = None 
        self.retry_count = 0
        self.dialog = QarnotDialog()
        
        self.data_ready.connect(self.update_ui)

        # --- PHASE 1 : ATTENTE DE L'API MESHROOM ---
        self.api_wait_timer = QTimer()
        self.api_wait_timer.timeout.connect(self.on_ui_ready)
        self.api_wait_timer.start(500)

    def on_ui_ready(self):
        self.api_wait_timer.stop()
        
        app = QApplication.instance()
            
        root_objects = app.engine.rootObjects()
        main_window = root_objects[0]

        stack_view = self.get_main_stack_view(main_window)

        stack_view.currentItemChanged.connect(self.on_page_changed)

    def on_page_changed(self):
        print("Changement de page")
        self.retry_count = 0
        self.attempt_injection()

    def onConnect(self, menu):
        self.dialog.show()
        menu.setProperty("isConnected", True)

    def onDisconnect(self, menu):
        delete_token()
        menu.setProperty("isConnected", False)

    def attempt_injection(self):
        app = QApplication.instance()
        root_objects = app.engine.rootObjects()
            
        main_window = root_objects[0]
        engine = app.engine

        print(f"Fenêtre principale trouvée : {main_window}")

        existing_menu_bar = self.find_menubar_recursive(main_window)

        print(f"✅ Barre de menu trouvée : {existing_menu_bar} (Classe: {existing_menu_bar.metaObject().className()})")

        currentDir = os.path.dirname(os.path.realpath(__file__))
        qml_file = os.path.join(currentDir, 'qml/QarnotMenu.qml')
        component = QQmlComponent(engine, QUrl.fromLocalFile(qml_file))

        if component.status() != QQmlComponent.Ready:
            print("Erreur QML :", component.errorString())
            return

        menu = component.create()
        menu.disconnectSignal.connect(self.onDisconnect)
        menu.connectSignal.connect(self.onConnect)
        menu.openSignal.connect(self.onOpen)

        if get_token():
            menu.setProperty("isConnected", True)

        QMetaObject.invokeMethod(
            menu, 
            "magicAttach", 
            Q_ARG("QVariant", existing_menu_bar)
        )
        
        print("✅ Menu injecté avec succès (méthode JS Proxy) !")

    # Utilitaires

    def onOpen(self, menu):
        menu.setProperty("email", "Chargement ...")
        menu.setProperty("runningTaskCount", "Chargement ...")
        menu.setProperty("storageInfo", "Chargement ...")
        print("DDDD")
        threading.Thread(target=self.fetch_data, args=(menu,), daemon=True).start()

    def fetch_data(self, menu):
            """Cette fonction tourne en arrière-plan"""
            print("AAAAA")
            token = get_token()
            connected = False
            user_info = None
            print("BBBBB")
            if token and isTokenValid(token):
                connected = True
                user_info = get_user_info(token)
            
            # Une fois fini, on envoie le signal au Thread Principal
            self.data_ready.emit(user_info, connected, menu)
            
    def update_ui(self, user_info, connected, menu):
        """Cette fonction est appelée par le signal sur le Thread Principal"""
        print("WWWWW")
        if connected and user_info:
            menu.setProperty("email", f"Compte : {user_info.email}")
            menu.setProperty("runningTaskCount", f"Tâches en cours : {user_info.running_task_count}")
            menu.setProperty("storageInfo", f"{formatBytes(user_info.used_quota_bytes_bucket)} libres / {formatBytes(user_info.quota_bytes_bucket)}")
        print("XXXXX")
        menu.setProperty("isConnected", connected)
    
    def get_main_stack_view(self, main_window):
        """
        Parcourt les enfants de la fenêtre pour trouver le StackView principal.
        """
        children = main_window.findChildren(QObject)
        
        for child in children:
            class_name = child.metaObject().className()

            if "StackView" in class_name:
                print(f"StackView trouvé : {child}")
                return child
                
        print("StackView introuvable.")
        return None

    def find_menubar_recursive(self, item):
        """ Cherche un objet dont le nom de classe contient 'MenuBar' """
        if "MenuBar" in item.metaObject().className():
            return item
        
        for child in item.children():
            res = self.find_menubar_recursive(child)
            if res: return res
        return None

    # def debug_hierarchy(self, item, indent=0):
    #     """ Affiche tout l'arbre pour que tu trouves le nom de classe """
    #     class_name = item.metaObject().className()
    #     print(" " * indent + f"> {item} | Class: {class_name}")
        
    #     for child in item.children():
    #         self.debug_hierarchy(child, indent + 2)

