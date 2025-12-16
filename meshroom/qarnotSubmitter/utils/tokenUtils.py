import qarnot
import keyring
from keyring.backends import Windows
keyring.set_keyring(Windows.WinVaultKeyring())

# Identifiants pour le stockage
SERVICE_ID = "qarnot_submitter"
KEY_NAME = "qarnot_token"

def save_token(token):
    try:
        keyring.set_password(SERVICE_ID, KEY_NAME, token)
        print("Token sécurisé avec succès.")
    except Exception as e:
        print(f"Erreur lors du stockage : {e}")

def get_token():

    try:
        token = keyring.get_password(SERVICE_ID, KEY_NAME)
        if token:
            return token
        else:
            print("Aucun token trouvé.")
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération : {e} ({type(e)})")
        return None

def delete_token():
    try:
        keyring.delete_password(SERVICE_ID, KEY_NAME)
        print("Token supprimé.")
    except keyring.errors.PasswordDeleteError:
        print("Le token n'existait pas.")


def isTokenValid(token):
    try:
        conn = qarnot.connection.Connection(client_token=token)
        return True
    except Exception as e:
        print(e)
        return False
    
def get_user_info(token):
    try:
        conn = qarnot.connection.Connection(client_token=token)
        return conn.user_info
    except:
        return ""