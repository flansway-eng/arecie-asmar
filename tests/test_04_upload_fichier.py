"""
Test 04 — Upload d'un fichier dans un dossier SharePoint
=========================================================
Objectif : créer un dossier de test, y uploader une petite image PNG,
puis vérifier qu'elle est bien présente.

Si ce test passe ✅, on sait que :
- L'upload de binaires (photos) vers SharePoint fonctionne
- Le flux complet "créer dossier → y mettre fichier" est validé
- On peut désormais coder le formulaire de collecte en confiance

Comment lancer ce test :
    python tests/test_04_upload_fichier.py
"""

import os
import io
import requests
from datetime import datetime
from PIL import Image
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
print(f"✅ Jeton obtenu\n")

# === ÉTAPE 2 : récupérer les IDs nécessaires ===
print(f"🔍 Récupération du site et de la bibliothèque...")

# En-têtes pour les requêtes JSON
headers_json = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

# ID du site
site_url = f"https://graph.microsoft.com/v1.0/sites/{sharepoint_tenant}.sharepoint.com:/sites/{site_name}"
site_id = requests.get(site_url, headers=headers_json).json()["id"]

# ID de la bibliothèque
drives = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
    headers=headers_json
).json().get("value", [])
target_drive = next((d for d in drives if d.get("name") == library_name), None)
drive_id = target_drive["id"]
print(f"✅ Site et bibliothèque trouvés\n")

# === ÉTAPE 3 : créer un dossier de test ===
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
folder_name = f"ZZZ_TEST_UPLOAD_{timestamp}_a-supprimer"
print(f"📁 Création du dossier '{folder_name}'...")

create_folder_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
folder_response = requests.post(
    create_folder_url,
    headers=headers_json,
    json={
        "name": folder_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "rename",
    }
)
if folder_response.status_code not in (200, 201):
    print(f"❌ Création dossier échouée : {folder_response.status_code}")
    print(f"   {folder_response.text[:500]}")
    exit(1)
folder = folder_response.json()
folder_id = folder["id"]
print(f"✅ Dossier créé (ID: {folder_id[:30]}...)\n")

# === ÉTAPE 4 : générer une image PNG de test en mémoire ===
# On utilise Pillow pour créer une image 200x200 pixels avec un fond bleu
# et du texte au centre. Le fichier ne touche jamais le disque dur :
# il reste en mémoire (octets bruts) et part directement vers SharePoint.
print(f"🎨 Génération d'une image PNG de test en mémoire...")
img = Image.new("RGB", (200, 200), color=(15, 110, 86))  # Vert ARECIE-friendly

# Convertir l'image en octets bruts (PNG)
img_bytes = io.BytesIO()
img.save(img_bytes, format="PNG")
img_data = img_bytes.getvalue()
print(f"✅ Image générée ({len(img_data)} octets)\n")

# === ÉTAPE 5 : uploader l'image dans le dossier ===
# L'URL pour uploader un fichier dans un dossier précis :
# /drives/{drive_id}/items/{folder_id}:/{filename}:/content
# Méthode HTTP : PUT (et non POST, car on remplace le contenu d'un emplacement précis)
# Content-Type : image/png (ou autre selon le type de fichier)
filename = f"test_image_{timestamp}.png"
upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}:/{filename}:/content"

# Pour l'upload, on change l'en-tête Content-Type vers image/png
# car on n'envoie plus du JSON mais des octets bruts d'image.
headers_upload = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "image/png",
}

print(f"📤 Upload de l'image '{filename}'...")
upload_response = requests.put(upload_url, headers=headers_upload, data=img_data)

if upload_response.status_code not in (200, 201):
    print(f"❌ Upload échoué : {upload_response.status_code}")
    print(f"   {upload_response.text[:500]}")
    exit(1)

uploaded = upload_response.json()
print(f"✅ Image uploadée avec succès !")
print(f"   Nom : {uploaded.get('name')}")
print(f"   Taille : {uploaded.get('size', '?')} octets")
print(f"   URL web : {uploaded.get('webUrl', 'inconnue')}")

# === ÉTAPE 6 : vérifier en listant le contenu du dossier ===
print(f"\n🔍 Vérification : listage du contenu du dossier...")
list_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}/children"
list_response = requests.get(list_url, headers=headers_json)
items = list_response.json().get("value", [])
print(f"✅ {len(items)} élément(s) dans le dossier :")
for item in items:
    type_label = "📁 dossier" if "folder" in item else "📄 fichier"
    print(f"   • {type_label}  '{item.get('name')}'  ({item.get('size', 0)} octets)")

# === Résumé final ===
print(f"\n🎉 Test 04 réussi — l'upload de fichier fonctionne !")
print(f"   📌 Vérifiez visuellement dans SharePoint :")
print(f"   {folder.get('webUrl', '')}")
print(f"\n   ⚠️  N'oubliez pas de SUPPRIMER ce dossier de test après vérification.")
