#!/usr/bin/env python
try:
    import os
    import logging
    import qarnot
    import keyring
    from keyring.backends import Windows
    keyring.set_keyring(Windows.WinVaultKeyring())

    from meshroom.core.submitter import BaseSubmitter

    from .utils.tokenUtils import get_token, isTokenValid, delete_token
    from .utils.qarnotUtils import async_launch_task
    from .ui.dialog import QarnotDialog

    class QarnotSubmitter(BaseSubmitter):
        dialog = None 
        engine = None

        def __init__(self, parent=None):
            super(QarnotSubmitter, self).__init__(name='QarnotRender', parent=parent)
            self.reqPackages = []
            self.dialog = QarnotDialog()
            delete_token()

        def submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
            # Contrairement aux submitters classique, cette fonction submit ne démarre pas nécéssairement la tâche (elle ouvre une popup qui peut échouer)
            logging.info("Préparation Qarnot...")

            token = get_token()

            if not token or not isTokenValid(token):
                self.dialog.showDialog()

            token = get_token()

            if token and isTokenValid(token):
                async_launch_task(nodes, edges, filepath, submitLabel="{projectName}")
            else:
                delete_token()

except Exception as e:
    print(e)