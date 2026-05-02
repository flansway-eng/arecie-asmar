"""
Test 06 — Diagnostic des colonnes de la liste.
Cree une ligne en ajoutant les champs un par un pour identifier
celui qui pose probleme.
"""

from datetime import datetime, timezone
from app.config import SHAREPOINT_COLUMNS
from app.graph_client import get_graph_client
from app.sharepoint_writer import get_site_id, get_list_id

client = get_graph_client()
site_id = get_site_id()
list_id = get_list_id()

base_url = f"/sites/{site_id}/lists/{list_id}/items"


def essayer(label: str, fields: dict) -> bool:
    """Essaye de creer une ligne avec les champs donnes."""
    timestamp = datetime.now().strftime("%H%M%S")
    fields_with_title = dict(fields)
    fields_with_title["Title"] = f"DIAG_{label}_{timestamp}"

    try:
        item = client.post(base_url, json={"fields": fields_with_title})
        print(f"  OK  - '{label}' : ligne creee (ID {item['id']})")
        return True
    except RuntimeError as e:
        msg = str(e).split("Detail : ")[-1] if "Detail" in str(e) else str(e)[:200]
        print(f"  ECHEC - '{label}' : {msg[:200]}")
        return False


print("Diagnostic des colonnes - une par une\n")

# Test 1 : juste le titre (ca on sait que ca marche)
print("Test 1 : Title seul")
essayer("title_seul", {})

# Test 2 : ajouter le numero adherent
print("\nTest 2 : Title + N_adherent (texte)")
essayer("num_adherent", {
    SHAREPOINT_COLUMNS["numero_adherent"]: "9999",
})

# Test 3 : ajouter le telephone
print("\nTest 3 : + telephone (texte)")
essayer("telephone", {
    SHAREPOINT_COLUMNS["numero_adherent"]: "9999",
    SHAREPOINT_COLUMNS["telephone"]: "+225 07 00 00 00 00",
})

# Test 4 : ajouter type_adherent (Choix)
print("\nTest 4 : + type_adherent (Choix)")
essayer("type_adherent", {
    SHAREPOINT_COLUMNS["type_adherent"]: "Renouvellement",
})

# Test 5 : ajouter cmu_adherent (texte)
print("\nTest 5 : + cmu_adherent (texte)")
essayer("cmu_adherent", {
    SHAREPOINT_COLUMNS["cmu_adherent"]: "CMU-TEST-12345",
})

# Test 6 : ajouter a_un_conjoint avec False (Oui/Non)
print("\nTest 6 : + a_un_conjoint = False (Oui/Non)")
essayer("conjoint_false", {
    SHAREPOINT_COLUMNS["a_un_conjoint"]: False,
})

# Test 7 : ajouter a_un_conjoint avec 0 (alternative pour Oui/Non)
print("\nTest 7 : + a_un_conjoint = 0 (alternative)")
essayer("conjoint_zero", {
    SHAREPOINT_COLUMNS["a_un_conjoint"]: 0,
})

# Test 8 : ajouter nb_enfants
print("\nTest 8 : + nb_enfants = 0 (Nombre)")
essayer("nb_enfants", {
    SHAREPOINT_COLUMNS["nb_enfants"]: 0,
})

# Test 9 : ajouter date_soumission
print("\nTest 9 : + date_soumission (DateTime ISO)")
essayer("date_soumission", {
    SHAREPOINT_COLUMNS["date_soumission"]: datetime.now(timezone.utc).isoformat(),
})

# Test 10 : ajouter notes
print("\nTest 10 : + notes (Texte plusieurs lignes)")
essayer("notes", {
    SHAREPOINT_COLUMNS["notes"]: "Ceci est une note de test.",
})

# Test 11 : ajouter le statut explicitement
print("\nTest 11 : + statut explicite (Choix)")
essayer("statut", {
    SHAREPOINT_COLUMNS["statut"]: "En attente",
})

# Test 12 : ajouter un lien hypertexte (Lien dossier)
print("\nTest 12 : + lien_dossier (Lien)")
essayer("lien_dossier", {
    SHAREPOINT_COLUMNS["lien_dossier"]: "https://example.com",
})

print("\nDiagnostic termine.")
print("Verifiez dans SharePoint quelles lignes 'DIAG_*' ont ete creees.")
print("Celles qui MANQUENT correspondent aux colonnes problematiques.")
