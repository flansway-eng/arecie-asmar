"""
Module client Microsoft Graph
==============================
Encapsule l'authentification Azure et les requêtes HTTP vers Microsoft Graph.

Utilisation :
    from app.graph_client import get_graph_client
    
    client = get_graph_client()
    response = client.get("/sites/...")
    response = client.post("/sites/.../items", json=data)
    response = client.put("/drives/.../content", data=binary_data, content_type="image/png")
"""

import logging
import requests
from msal import ConfidentialClientApplication
from app.config import settings

logger = logging.getLogger(__name__)


class GraphClient:
    """
    Client réutilisable pour appeler l'API Microsoft Graph.
    
    Gère l'authentification, le cache du jeton, et les requêtes HTTP
    avec gestion d'erreurs.
    """

    def __init__(self):
        # On crée l'app MSAL UNE SEULE FOIS pour toute la durée du programme.
        # MSAL gère son propre cache de jetons en interne.
        self._msal_app = ConfidentialClientApplication(
            client_id=settings.AZURE_CLIENT_ID,
            authority=settings.authority_url,
            client_credential=settings.AZURE_CLIENT_SECRET,
        )
        # On va retenir le jeton pour ne pas le redemander inutilement.
        self._cached_token: str | None = None

    def _get_token(self) -> str:
        """
        Récupère un jeton d'accès valide.
        Si le cache MSAL contient encore un jeton non expiré, il est réutilisé.
        Sinon, MSAL en obtient un nouveau automatiquement.
        """
        result = self._msal_app.acquire_token_for_client(
            scopes=[settings.GRAPH_SCOPE]
        )
        if "access_token" not in result:
            error = result.get("error_description", "Erreur inconnue")
            raise RuntimeError(f"Échec d'authentification Azure : {error}")
        return result["access_token"]

    def _build_url(self, path: str) -> str:
        """
        Construit une URL complète à partir d'un chemin relatif.
        Accepte aussi bien '/sites/...' que 'https://graph.microsoft.com/v1.0/sites/...'.
        """
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{settings.GRAPH_BASE_URL}{path}"

    def _build_headers(self, content_type: str = "application/json") -> dict:
        """
        Construit les en-têtes HTTP avec le jeton Bearer.
        """
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": content_type,
        }

    def get(self, path: str, params: dict | None = None) -> dict:
        """
        Effectue une requête GET vers Microsoft Graph.
        Renvoie le JSON décodé en dictionnaire Python.
        """
        url = self._build_url(path)
        response = requests.get(url, headers=self._build_headers(), params=params)
        return self._handle_response(response, "GET", url)

    def post(self, path: str, json: dict | None = None) -> dict:
        """
        Effectue une requête POST avec un body JSON.
        Utilisé pour créer des éléments (dossiers, lignes de liste...).
        """
        url = self._build_url(path)
        response = requests.post(url, headers=self._build_headers(), json=json)
        return self._handle_response(response, "POST", url)

    def put_binary(self, path: str, data: bytes, content_type: str) -> dict:
        """
        Effectue une requête PUT avec des données binaires (upload de fichier).
        Le content_type doit refléter le type du fichier ('image/png', 'application/pdf', etc.).
        """
        url = self._build_url(path)
        headers = self._build_headers(content_type=content_type)
        response = requests.put(url, headers=headers, data=data)
        return self._handle_response(response, "PUT", url)

    def patch(self, path: str, json: dict) -> dict:
        """
        Effectue une requête PATCH pour mettre à jour partiellement un élément.
        Utilisé pour modifier le statut d'un dossier, par exemple.
        """
        url = self._build_url(path)
        response = requests.patch(url, headers=self._build_headers(), json=json)
        return self._handle_response(response, "PATCH", url)

    def _handle_response(self, response: requests.Response, method: str, url: str) -> dict:
        """
        Vérifie le code HTTP et renvoie le JSON.
        En cas d'erreur, lève une exception avec le détail pour debug.
        """
        if response.status_code in (200, 201, 204):
            # 204 = succès sans contenu (PATCH/DELETE) → on renvoie un dict vide
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()

        # Erreur — on construit un message clair pour faciliter le debug
        try:
            error_body = response.json()
            error_msg = error_body.get("error", {}).get("message", response.text[:300])
        except Exception:
            error_msg = response.text[:300]

        raise RuntimeError(
            f"Microsoft Graph a répondu HTTP {response.status_code} sur {method} {url}\n"
            f"Détail : {error_msg}"
        )


# === Singleton : une seule instance pour toute l'app ===
_client_instance: GraphClient | None = None


def get_graph_client() -> GraphClient:
    """
    Renvoie l'instance unique de GraphClient (créée à la demande).
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = GraphClient()
    return _client_instance


# === Test rapide en lançant le module directement ===
if __name__ == "__main__":
    print("🔧 Test du GraphClient...\n")
    client = get_graph_client()
    
    # Test 1 — Récupérer le site SharePoint
    print(f"1️⃣  Recherche du site '{settings.SHAREPOINT_SITE_NAME}'...")
    site = client.get(
        f"/sites/{settings.SHAREPOINT_TENANT}.sharepoint.com:"
        f"/sites/{settings.SHAREPOINT_SITE_NAME}"
    )
    print(f"   ✅ Site trouvé : {site.get('displayName')}")
    print(f"   ID : {site.get('id', '')[:50]}...\n")

    # Test 2 — Lister les bibliothèques
    print(f"2️⃣  Lecture des bibliothèques du site...")
    drives = client.get(f"/sites/{site['id']}/drives")
    print(f"   ✅ {len(drives.get('value', []))} bibliothèque(s) trouvée(s)")
    for drive in drives.get("value", []):
        print(f"      • {drive.get('name')}")

    print(f"\n🎉 GraphClient opérationnel !")
