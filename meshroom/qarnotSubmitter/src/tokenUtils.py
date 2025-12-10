import keyring

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