"""
Test 02 — Exploration du site SharePoint
=========================================
Objectif : trouver le site ARECIE-Suivi-ASMAR2026 sur SharePoint
et lister ses bibliothèques + listes pour confirmer que tout est
bien configuré et accessible.

Si ce test passe ✅, on sait que :
- Les permissions Sites.ReadWrite.All fonctionnent
- Le site SharePoint est bien identifiable
- La bibliothèque "Documents Adhérents" et la liste "Dossiers ASMAR 2026" sont visibles

Comment lancer ce test :
    python tests/test_02_sharepoint.py
"""

import os
import requests
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

# === ÉTAPE 1 : récupérer un jeton d'accès (comme dans test_01) ===
load_dotenv()
client_id = os.getenv("AZURE_CLIENT_ID")
tenant_id = os.getenv("AZURE_TENANT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
sharepoint_tenant = os.getenv("SHAREPOINT_TENANT")
site_name = os.getenv("SHAREPOINT_SITE_NAME")

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
    print(f"❌ Authentification échouée : {result.get('error_description')}")
    exit(1)

token = result["access_token"]
print(f"✅ Jeton obtenu\n")

# === ÉTAPE 2 : préparer les en-têtes HTTP ===
# Toutes nos requêtes vers Microsoft Graph auront le jeton dans l'en-tête.
# C'est le standard "Bearer" pour OAuth 2.0.
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

# === ÉTAPE 3 : trouver l'ID du site SharePoint ===
# L'URL de Microsoft Graph pour interroger un site par son nom est :
# https://graph.microsoft.com/v1.0/sites/{tenant}.sharepoint.com:/sites/{site_name}
site_url = f"https://graph.microsoft.com/v1.0/sites/{sharepoint_tenant}.sharepoint.com:/sites/{site_name}"
print(f"🔍 Recherche du site : {site_name}")
print(f"   URL appelée : {site_url}")

response = requests.get(site_url, headers=headers)

if response.status_code != 200:
    print(f"\n❌ Erreur lors de la recherche du site")
    print(f"   Code HTTP : {response.status_code}")
    print(f"   Réponse : {response.text[:500]}")
    exit(1)

site_data = response.json()
site_id = site_data["id"]
print(f"\n✅ Site trouvé !")
print(f"   Nom complet : {site_data.get('displayName', 'inconnu')}")
print(f"   Description : {site_data.get('description', '(vide)')}")
print(f"   URL web : {site_data.get('webUrl', 'inconnue')}")
print(f"   ID interne : {site_id[:50]}...")

# === ÉTAPE 4 : lister les bibliothèques de documents (drives) ===
# Dans la terminologie Microsoft Graph, une "bibliothèque" s'appelle un "drive".
print(f"\n📚 Recherche des bibliothèques de documents...")
drives_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
response = requests.get(drives_url, headers=headers)

if response.status_code != 200:
    print(f"❌ Erreur : {response.status_code} — {response.text[:300]}")
    exit(1)

drives = response.json().get("value", [])
print(f"   {len(drives)} bibliothèque(s) trouvée(s) :")
for drive in drives:
    name = drive.get("name", "?")
    drive_id = drive.get("id", "?")
    print(f"   • '{name}'  (ID: {drive_id[:30]}...)")

# === ÉTAPE 5 : lister les listes SharePoint ===
print(f"\n📋 Recherche des listes SharePoint...")
lists_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
response = requests.get(lists_url, headers=headers)

if response.status_code != 200:
    print(f"❌ Erreur : {response.status_code} — {response.text[:300]}")
    exit(1)

lists = response.json().get("value", [])
print(f"   {len(lists)} liste(s) trouvée(s) :")
for lst in lists:
    name = lst.get("displayName", "?")
    list_id = lst.get("id", "?")
    template = lst.get("list", {}).get("template", "?")
    print(f"   • '{name}'  (template: {template}, ID: {list_id[:20]}...)")

# === ÉTAPE 6 : vérifications spécifiques ===
print(f"\n🔎 Vérifications spécifiques pour notre projet :")

# Bibliothèque "Documents Adhérents"
target_library = os.getenv("SHAREPOINT_LIBRARY")
found_library = next((d for d in drives if d.get("name") == target_library), None)
if found_library:
    print(f"   ✅ Bibliothèque '{target_library}' trouvée")
else:
    print(f"   ⚠️  Bibliothèque '{target_library}' INTROUVABLE")
    print(f"      Vérifiez le nom exact dans .env (SHAREPOINT_LIBRARY)")

# Liste "Dossiers ASMAR 2026"
target_list = os.getenv("SHAREPOINT_LIST")
found_list = next((l for l in lists if l.get("displayName") == target_list), None)
if found_list:
    print(f"   ✅ Liste '{target_list}' trouvée")
else:
    print(f"   ⚠️  Liste '{target_list}' INTROUVABLE")
    print(f"      Vérifiez le nom exact dans .env (SHAREPOINT_LIST)")

print(f"\n🎉 Test 02 terminé — exploration du site réussie !")
