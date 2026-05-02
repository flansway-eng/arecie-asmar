"""Test 07 - Diagnostic format hyperlien SharePoint."""

from datetime import datetime
from app.config import SHAREPOINT_COLUMNS
from app.graph_client import get_graph_client
from app.sharepoint_writer import get_site_id, get_list_id

client = get_graph_client()
site_id = get_site_id()
list_id = get_list_id()

base_url = f"/sites/{site_id}/lists/{list_id}/items"
nom_interne = SHAREPOINT_COLUMNS["lien_dossier"]
print(f"Nom interne de 'lien_dossier' : {nom_interne}\n")


def essayer(label, valeur):
    timestamp = datetime.now().strftime("%H%M%S")
    body = {
        "fields": {
            "Title": f"DIAG_HYPER_{label}_{timestamp}",
            nom_interne: valeur,
        }
    }
    try:
        item = client.post(base_url, json=body)
        print(f"  OK     - format '{label}' : ligne {item['id']}")
        return True
    except RuntimeError as e:
        msg = str(e)
        # Extraire juste la fin du message
        if "Detail :" in msg:
            msg = msg.split("Detail :")[-1].strip()
        print(f"  ECHEC  - format '{label}' : {msg[:150]}")
        return False


# Format 1 : objet Url+Description (ce qu'on essaye actuellement)
print("Format 1 : objet {Url, Description}")
essayer("objet_url_desc", {
    "Url": "https://example.com",
    "Description": "Test",
})

# Format 2 : objet avec cles minuscules
print("\nFormat 2 : objet {url, description} minuscules")
essayer("objet_minuscules", {
    "url": "https://example.com",
    "description": "Test",
})

# Format 3 : string simple URL
print("\nFormat 3 : string simple")
essayer("string_simple", "https://example.com")

# Format 4 : suffixe de la colonne avec _Url
print(f"\nFormat 4 : 2 champs separes ({nom_interne}, {nom_interne}_Description)")
timestamp = datetime.now().strftime("%H%M%S")
body = {
    "fields": {
        "Title": f"DIAG_HYPER_deux_champs_{timestamp}",
        nom_interne: "https://example.com",
    }
}
try:
    item = client.post(base_url, json=body)
    print(f"  OK     - format 'deux_champs' : ligne {item['id']}")
except RuntimeError as e:
    print(f"  ECHEC  - format 'deux_champs' : {str(e)[-150:]}")

print("\nDiagnostic termine.")