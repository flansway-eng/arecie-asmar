"""
Test 03 — Création d'un dossier dans SharePoint
================================================
Objectif : créer un dossier de test dans la bibliothèque
"Documents Adhérents" pour valider les permissions d'écriture.

Si ce test passe ✅, on sait que :
- Files.ReadWrite.All fonctionne bien
- L'app peut créer des dossiers SharePoint
- On est prêts pour la création automatique de dossiers d'adhérents

Comment lancer ce test :
    python tests/test_03_creation_dossier.py
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

# === ÉTAPE 1 : authentification ===
load_dotenv()
client_id = os.getenv("AZURE_CLIENT_ID")
tenant_id = os.getenv("AZURE_TENANT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
sharepoint_tenant = os.getenv("SHAREPOINT_TENANT")
site_name = os.getenv("SHAREPOINT_SITE_NAME")
library_name = os.getenv("SHAREPOINT_LIBRARY")

print(f"🔐 Authentification...")
app = ConfidentialClientApplication(
    client_id=client_id,
    authority=f"https://login.microsoftonline.com/{tenant_id}",
    client_credential=client_secret,
)
result = app.acquire_token_for_client(
    scopes=["https://graph.microsoft.com/.default"]
)
if "access_token" not in result:
    print(f"❌ {result.get('error_description')}")
    exit(1)
token = result["access_token"]
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
print(f"✅ Jeton obtenu\n")

# === ÉTAPE 2 : récupérer l'ID du site ===
print(f"🔍 Recherche du site...")
site_url = f"https://graph.microsoft.com/v1.0/sites/{sharepoint_tenant}.sharepoint.com:/sites/{site_name}"
response = requests.get(site_url, headers=headers)
if response.status_code != 200:
    print(f"❌ Site introuvable : {response.status_code}")
    exit(1)
site_id = response.json()["id"]
print(f"✅ Site trouvé\n")

# === ÉTAPE 3 : récupérer l'ID de la bibliothèque "Documents Adhérents" ===
print(f"📚 Recherche de la bibliothèque '{library_name}'...")
drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
response = requests.get(drives_url, headers=headers)
drives = response.json().get("value", [])
target_drive = next((d for d in drives if d.get("name") == library_name), None)

if not target_drive:
    print(f"❌ Bibliothèque '{library_name}' introuvable")
    exit(1)

drive_id = target_drive["id"]
print(f"✅ Bibliothèque trouvée (ID: {drive_id[:30]}...)\n")

# === ÉTAPE 4 : créer le dossier de test ===
# On génère un nom unique avec horodatage pour ne pas avoir de conflit
# si on relance le test plusieurs fois.
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
folder_name = f"ZZZ_TEST_CONNEXION_{timestamp}_a-supprimer"
print(f"📁 Création du dossier '{folder_name}'...")

# L'URL pour créer un élément à la racine de la bibliothèque :
# /drives/{drive_id}/root/children
# On envoie un POST avec un JSON décrivant le dossier.
create_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
folder_data = {
    "name": folder_name,
    "folder": {},  # ← dit à Graph que c'est un DOSSIER, pas un fichier
    "@microsoft.graph.conflictBehavior": "rename",  # si conflit, ajoute un suffixe
}

response = requests.post(create_url, headers=headers, json=folder_data)

if response.status_code not in (200, 201):
    print(f"❌ Échec de création")
    print(f"   Code HTTP : {response.status_code}")
    print(f"   Réponse : {response.text[:500]}")
    exit(1)

folder = response.json()
print(f"✅ Dossier créé !")
print(f"   Nom : {folder.get('name')}")
print(f"   ID : {folder.get('id', '?')[:40]}...")
print(f"   URL web : {folder.get('webUrl', 'inconnue')}")

# === ÉTAPE 5 : vérifier en relisant le dossier ===
print(f"\n🔍 Vérification : relecture du dossier...")
folder_id = folder["id"]
read_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}"
response = requests.get(read_url, headers=headers)

if response.status_code != 200:
    print(f"⚠️  Le dossier a été créé mais n'est pas relisible : {response.status_code}")
else:
    re_folder = response.json()
    print(f"✅ Dossier confirmé existant")
    print(f"   Date création : {re_folder.get('createdDateTime', '?')}")
    print(f"   Créé par : {re_folder.get('createdBy', {}).get('application', {}).get('displayName', '?')}")

# === Résumé final ===
print(f"\n🎉 Test 03 terminé avec succès !")
print(f"   📌 Allez vérifier dans SharePoint :")
print(f"   {folder.get('webUrl', '')}")
print(f"\n   ⚠️  N'oubliez pas de SUPPRIMER ce dossier de test après vérification.")
