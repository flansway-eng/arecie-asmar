"""
Test 01 — Connexion Azure
==========================
Objectif : vérifier que les 3 codes secrets Azure permettent bien
d'obtenir un jeton d'accès auprès de Microsoft.

Si ce test passe ✅, on sait que :
- Les 3 secrets dans .env sont corrects
- L'application Azure est correctement configurée
- Notre Python peut parler à Microsoft

Comment lancer ce test :
    python tests/test_01_connexion.py
"""

import os
from dotenv import load_dotenv
from msal import ConfidentialClientApplication

# === ÉTAPE 1 : charger les secrets depuis .env ===
# load_dotenv() lit le fichier .env et place chaque variable
# dans os.environ pour qu'on puisse les récupérer.
print("📂 Chargement du fichier .env...")
load_dotenv()

client_id = os.getenv("AZURE_CLIENT_ID")
tenant_id = os.getenv("AZURE_TENANT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")

# === ÉTAPE 2 : vérifier que les variables sont bien lues ===
# Si une variable manque, on arrête tout de suite avec un message clair.
if not client_id:
    print("❌ AZURE_CLIENT_ID est manquant dans .env")
    exit(1)
if not tenant_id:
    print("❌ AZURE_TENANT_ID est manquant dans .env")
    exit(1)
if not client_secret:
    print("❌ AZURE_CLIENT_SECRET est manquant dans .env")
    exit(1)

print(f"✅ Client ID lu : {client_id[:8]}...")
print(f"✅ Tenant ID lu : {tenant_id[:8]}...")
print(f"✅ Client Secret lu : {client_secret[:4]}... ({len(client_secret)} caractères)")

# === ÉTAPE 3 : préparer la requête d'authentification auprès d'Azure ===
# L'URL d'autorité est composée du Tenant ID — c'est l'adresse
# du "guichet d'authentification" de notre organisation flansway.
authority_url = f"https://login.microsoftonline.com/{tenant_id}"
print(f"\n🔐 Connexion à : {authority_url}")

# On crée un objet MSAL "ConfidentialClientApplication" — c'est
# l'objet qui va gérer l'authentification pour nous.
# "Confidential" parce qu'on a un secret (l'app n'est pas publique).
app = ConfidentialClientApplication(
    client_id=client_id,
    authority=authority_url,
    client_credential=client_secret,
)

# === ÉTAPE 4 : demander le jeton d'accès ===
# "Scopes" = la liste des permissions qu'on demande.
# Pour Microsoft Graph, on utilise toujours ".default" qui veut dire
# "donne-moi tous les droits que cette app a déjà obtenus en Azure".
print("🎫 Demande de jeton d'accès à Microsoft Graph...")
result = app.acquire_token_for_client(
    scopes=["https://graph.microsoft.com/.default"]
)

# === ÉTAPE 5 : vérifier la réponse ===
# La réponse est un dictionnaire Python.
# Si "access_token" est dedans, c'est gagné.
# Si "error" est dedans, on a un problème — on l'affiche pour debug.
if "access_token" in result:
    token = result["access_token"]
    print(f"\n✅ SUCCÈS ! Jeton d'accès obtenu.")
    print(f"   Type : {result.get('token_type', 'inconnu')}")
    print(f"   Expire dans : {result.get('expires_in', 'inconnu')} secondes")
    print(f"   Début du jeton : {token[:30]}...")
    print(f"   Longueur totale : {len(token)} caractères")
    print("\n🎉 La connexion Azure fonctionne parfaitement !")
    print("   Vous pouvez passer à l'étape suivante (test SharePoint).")
else:
    print(f"\n❌ ÉCHEC de l'authentification")
    print(f"   Erreur : {result.get('error', 'inconnu')}")
    print(f"   Description : {result.get('error_description', 'aucune')}")
    print(f"   Code de corrélation : {result.get('correlation_id', 'aucun')}")
    exit(1)
