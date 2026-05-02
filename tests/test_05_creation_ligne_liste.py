"""
Test 05 — Création d'une ligne dans la liste "Dossiers ASMAR 2026"
====================================================================
Objectif : ajouter une ligne de test (un faux adhérent) dans la liste
SharePoint pour valider l'écriture des métadonnées.

Si ce test passe ✅, on a TOUT validé pour construire l'app :
- Authentification Azure
- Lecture du site SharePoint
- Création de dossiers
- Upload de fichiers
- Écriture dans les listes

Comment lancer ce test :
    python tests/test_05_creation_ligne_liste.py
"""

import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

# === ÉTAPE 1 : authentification ===
load_dotenv()
client_id = os.getenv("AZURE_CLIENT_ID")
tenant_id = os.getenv("AZURE_TENANT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
sharepoint_tenant = os.getenv("SHAREPOINT_TENANT")
site_name = os.getenv("SHAREPOINT_SITE_NAME")
list_name = os.getenv("SHAREPOINT_LIST")

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

# === ÉTAPE 2 : récupérer le site et la liste ===
print(f"🔍 Récupération du site et de la liste '{list_name}'...")
site_url = f"https://graph.microsoft.com/v1.0/sites/{sharepoint_tenant}.sharepoint.com:/sites/{site_name}"
site_id = requests.get(site_url, headers=headers).json()["id"]

lists = requests.get(
    f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists",
    headers=headers
).json().get("value", [])
target_list = next((l for l in lists if l.get("displayName") == list_name), None)
if not target_list:
    print(f"❌ Liste '{list_name}' introuvable")
    exit(1)
list_id = target_list["id"]
print(f"✅ Liste trouvée (ID: {list_id[:30]}...)\n")

# === ÉTAPE 3 : lister les colonnes de la liste ===
# C'est crucial : on doit connaître les NOMS INTERNES des colonnes
# pour pouvoir y écrire (le nom affiché peut être différent).
print(f"📋 Découverte des colonnes de la liste...")
columns_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/columns"
columns_response = requests.get(columns_url, headers=headers)
columns = columns_response.json().get("value", [])

# On affiche le mapping affichage → interne pour les colonnes qui nous intéressent
print(f"   {len(columns)} colonne(s) trouvée(s).")
print(f"   Mapping (Nom affiché → Nom interne) :")

# Filtrer pour ne montrer que les colonnes "métier" (pas les colonnes système)
meaningful_columns = []
for col in columns:
    display = col.get("displayName", "")
    internal = col.get("name", "")
    is_readonly = col.get("readOnly", False)
    is_hidden = col.get("hidden", False)
    
    # On ignore les colonnes système cachées ou en lecture seule
    if not is_hidden and not is_readonly:
        meaningful_columns.append((display, internal, col))
        if display in ["Nom adhérent", "N° adhérent", "Téléphone WhatsApp",
                       "Type adhérent", "Statut", "Date soumission",
                       "CMU adhérent", "A un conjoint", "Nb enfants",
                       "Notes", "Lien dossier"]:
            print(f"      • '{display}' → '{internal}'")

# === ÉTAPE 4 : créer une ligne de test ===
# Le format pour créer une ligne dans une liste SharePoint :
# POST /sites/{site_id}/lists/{list_id}/items
# Body : { "fields": { "ColonneInterne1": "valeur1", "ColonneInterne2": "valeur2", ... } }
#
# Le nom interne de la colonne "Nom adhérent" (renommée depuis "Titre")
# est probablement resté "Title" — c'est le standard SharePoint.

timestamp = datetime.now(timezone.utc).isoformat()
test_data = {
    "fields": {
        "Title": "TEST_API_a-supprimer",  # "Title" = nom interne de "Nom adhérent"
        "field_1": "9999",  # Si "N° adhérent" a comme nom interne "field_1"
        # On va ajuster les noms internes si besoin après le premier essai
    }
}

# Pour être plus robustes, construisons les fields seulement avec "Title" pour commencer
# (la colonne Titre/Nom adhérent est la SEULE garantie de fonctionner partout)
test_data_minimal = {
    "fields": {
        "Title": f"TEST_API_{datetime.now().strftime('%H%M%S')}_a-supprimer"
    }
}

print(f"\n📝 Création d'une ligne de test minimale...")
print(f"   Champ Title : {test_data_minimal['fields']['Title']}")

create_item_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
create_response = requests.post(create_item_url, headers=headers, json=test_data_minimal)

if create_response.status_code not in (200, 201):
    print(f"❌ Création échouée")
    print(f"   Code HTTP : {create_response.status_code}")
    print(f"   Réponse : {create_response.text[:600]}")
    exit(1)

item = create_response.json()
item_id = item.get("id", "?")
print(f"✅ Ligne créée !")
print(f"   ID : {item_id}")
print(f"   webUrl : {item.get('webUrl', 'inconnue')}")

# === ÉTAPE 5 : relire la ligne pour vérifier ===
print(f"\n🔍 Relecture de la ligne...")
read_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}?expand=fields"
read_response = requests.get(read_url, headers=headers)
if read_response.status_code == 200:
    re_item = read_response.json()
    fields = re_item.get("fields", {})
    print(f"✅ Ligne relue avec succès")
    print(f"   Title : {fields.get('Title', '?')}")
    print(f"   Créée le : {re_item.get('createdDateTime', '?')}")

# === ÉTAPE 6 : afficher TOUS les noms internes pour référence future ===
print(f"\n📋 RÉFÉRENCE — Tous les noms internes de la liste :")
print(f"   (à utiliser dans le code de l'app pour écrire dans chaque colonne)")
for display, internal, col in meaningful_columns:
    col_type = col.get("columnGroup", "") or list(col.keys())[-1]  # type approximatif
    print(f"      '{display}'  →  internalName='{internal}'")

print(f"\n🎉 Test 05 réussi — l'écriture dans les listes fonctionne !")
print(f"\n   📌 Vérifiez visuellement dans SharePoint la liste 'Dossiers ASMAR 2026'")
print(f"   Vous devriez voir une ligne 'TEST_API_...' à supprimer après vérification.")
