"""
Module de configuration
========================
Centralise tous les paramètres du projet. Lu une seule fois au démarrage.

Utilisation depuis un autre module :
    from app.config import settings
    print(settings.SHAREPOINT_SITE_NAME)
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Charge automatiquement le .env au moment où ce module est importé.
load_dotenv()


def _require(var_name: str) -> str:
    """
    Récupère une variable d'environnement obligatoire.
    Lève une erreur claire si elle est absente.
    """
    value = os.getenv(var_name)
    if not value:
        raise RuntimeError(
            f"Variable d'environnement manquante : {var_name}\n"
            f"Vérifiez votre fichier .env"
        )
    return value


@dataclass(frozen=True)
class Settings:
    """
    Conteneur immuable de tous les paramètres de l'app.
    `frozen=True` empêche la modification après création — sécurité.
    """

    # === Secrets Azure ===
    AZURE_CLIENT_ID: str
    AZURE_TENANT_ID: str
    AZURE_CLIENT_SECRET: str

    # === Configuration SharePoint ===
    SHAREPOINT_TENANT: str
    SHAREPOINT_SITE_NAME: str
    SHAREPOINT_LIBRARY: str
    SHAREPOINT_LIST: str

    # === Constantes Microsoft Graph ===
    GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"
    GRAPH_SCOPE: str = "https://graph.microsoft.com/.default"

    @property
    def authority_url(self) -> str:
        """URL du serveur d'autorité Azure pour notre tenant."""
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}"

    @property
    def site_lookup_url(self) -> str:
        """URL pour rechercher le site SharePoint par son nom."""
        return (
            f"{self.GRAPH_BASE_URL}/sites/"
            f"{self.SHAREPOINT_TENANT}.sharepoint.com:"
            f"/sites/{self.SHAREPOINT_SITE_NAME}"
        )


# === Mapping des colonnes de la liste "Dossiers ASMAR 2026" ===
# Issu du Test 05 — ces noms internes sont définitifs.
# Si on renomme une colonne dans SharePoint, le nom interne ne change PAS.
SHAREPOINT_COLUMNS = {
    "nom_adherent":      "Title",
    "numero_adherent":   "N_x00b0_adh_x00e9_rent",
    "telephone":         "T_x00e9_l_x00e9_phoneWhatsApp",
    "type_adherent":     "Typeadh_x00e9_rent",
    "statut":            "Statutdudossier",
    "date_soumission":   "Datesoumission",
    "cmu_adherent":      "CMUadh_x00e9_rent",
    "a_un_conjoint":     "Aunconjoint",
    "nom_conjoint":      "Nomconjoint",
    "cmu_conjoint":      "CMUconjoint",  # à confirmer au premier test
    "nb_enfants":        "Nb_x0020_enfants",
    "donnees_enfants":   "Donn_x00e9_es_x0020_enfants",
    "lien_dossier":      "Lien_x0020_dossier",
    "notes":             "Notes",
    "validee_par":       "Valid_x00e9_e_x0020_par",
    "date_validation":   "Date_x0020_validation",
}

# === Valeurs autorisées pour les colonnes de type Choix ===
TYPES_ADHERENT = ["Renouvellement", "Nouvel adhérent"]
STATUTS = ["En attente", "Complet", "Incomplet", "Validé", "Rejeté"]


def load_settings() -> Settings:
    """
    Construit l'objet Settings en lisant les variables d'environnement.
    À appeler une seule fois au démarrage de l'app.
    """
    return Settings(
        AZURE_CLIENT_ID=_require("AZURE_CLIENT_ID"),
        AZURE_TENANT_ID=_require("AZURE_TENANT_ID"),
        AZURE_CLIENT_SECRET=_require("AZURE_CLIENT_SECRET"),
        SHAREPOINT_TENANT=_require("SHAREPOINT_TENANT"),
        SHAREPOINT_SITE_NAME=_require("SHAREPOINT_SITE_NAME"),
        SHAREPOINT_LIBRARY=_require("SHAREPOINT_LIBRARY"),
        SHAREPOINT_LIST=_require("SHAREPOINT_LIST"),
    )


# Singleton — la seule instance accessible depuis tout le code.
settings = load_settings()


# === Si on lance ce module directement, on affiche un résumé pour vérification ===
if __name__ == "__main__":
    print("✅ Configuration chargée avec succès\n")
    print(f"Site SharePoint : {settings.SHAREPOINT_SITE_NAME}")
    print(f"Bibliothèque    : {settings.SHAREPOINT_LIBRARY}")
    print(f"Liste           : {settings.SHAREPOINT_LIST}")
    print(f"Tenant Azure    : {settings.AZURE_TENANT_ID[:8]}...")
    print(f"Authority URL   : {settings.authority_url}")
    print(f"\n📋 {len(SHAREPOINT_COLUMNS)} colonnes mappées dans SHAREPOINT_COLUMNS")
