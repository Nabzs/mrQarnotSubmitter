#!/usr/bin/env python
try:
    import os
    import logging
    import qarnot

    from meshroom.core.submitter import BaseSubmitter

    from .utils.tokenUtils import get_token, isTokenValid, delete_token
    from .utils.qarnotUtils import async_watch_task, get_running_task_for_project, start_task
    from .ui.tokenDialog import TokenDialog
    from .ui.menu import Menu

    class QarnotSubmitter(BaseSubmitter):
        tokenDialog = None 
        infoDialog = None
        engine = None
        menu = None

        def __init__(self, parent=None):
            super(QarnotSubmitter, self).__init__(name='QarnotSubmitter', parent=parent)
            self.reqPackages = []
            self.tokenDialog = TokenDialog()

            print("Init submitter")

            self.menu = Menu()
        
        def submit(self, nodes, edges, filepath, submitLabel="{projectName}"):
            # Contrairement aux submitters classique, cette fonction submit ne démarre pas nécéssairement la tâche (elle ouvre une popup qui peut échouer)
            logging.info("Préparation Qarnot...")

            token = get_token()

            if not token or not isTokenValid(token):
                self.tokenDialog.show()

            token = get_token()

            if token and isTokenValid(token):
                # Si la tâche existe, on la récupère plutôt que d'en relancer une nouvelle
                job = get_running_task_for_project(nodes)

                if not job:
                    # Sinon on créé une nouvelle tâche
                    job = start_task(nodes, edges, filepath, submitLabel)
                    print("Creating new task")
                else:
                    print("Resuming old task")

                # Pour finir, on démarre un thread qui observe la tâche et télécharge le résultat
                async_watch_task(job, nodes)
                return True
            else:
                delete_token()
                return False
            
            return True

except Exception as e:
    print(e)