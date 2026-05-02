"""
Module sharepoint_writer
Cree des dossiers d'adherents, upload des photos, ecrit dans la liste.
"""

import json
import re
import logging
from datetime import datetime, timezone
from app.config import settings, SHAREPOINT_COLUMNS
from app.graph_client import get_graph_client

logger = logging.getLogger(__name__)

_cache = {"site_id": None, "drive_id": None, "list_id": None}


def get_site_id():
    if _cache["site_id"] is None:
        client = get_graph_client()
        path = f"/sites/{settings.SHAREPOINT_TENANT}.sharepoint.com:/sites/{settings.SHAREPOINT_SITE_NAME}"
        _cache["site_id"] = client.get(path)["id"]
    return _cache["site_id"]


def get_drive_id():
    if _cache["drive_id"] is None:
        client = get_graph_client()
        drives = client.get(f"/sites/{get_site_id()}/drives").get("value", [])
        target = next((d for d in drives if d.get("name") == settings.SHAREPOINT_LIBRARY), None)
        if not target:
            raise RuntimeError(f"Bibliotheque '{settings.SHAREPOINT_LIBRARY}' introuvable")
        _cache["drive_id"] = target["id"]
    return _cache["drive_id"]


def get_list_id():
    if _cache["list_id"] is None:
        client = get_graph_client()
        lists = client.get(f"/sites/{get_site_id()}/lists").get("value", [])
        target = next((l for l in lists if l.get("displayName") == settings.SHAREPOINT_LIST), None)
        if not target:
            raise RuntimeError(f"Liste '{settings.SHAREPOINT_LIST}' introuvable")
        _cache["list_id"] = target["id"]
    return _cache["list_id"]


def _slugify(texte):
    texte = texte.strip()
    texte = re.sub(r"\s+", "_", texte)
    texte = re.sub(r"[^A-Za-z0-9\u00C0-\u00FF_\-]", "", texte)
    return texte


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def creer_dossier_adherent(nom, num_adherent=""):
    client = get_graph_client()
    drive_id = get_drive_id()
    safe_nom = _slugify(nom)
    folder_name = f"{safe_nom}_{num_adherent}" if num_adherent else safe_nom

    body = {
        "name": folder_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "rename",
    }
    logger.info(f"Creation dossier : {folder_name}")
    folder = client.post(f"/drives/{drive_id}/root/children", json=body)

    return {
        "id": folder["id"],
        "name": folder["name"],
        "webUrl": folder["webUrl"],
    }


def uploader_photo(folder_id, nom_fichier, contenu, content_type="image/jpeg"):
    client = get_graph_client()
    drive_id = get_drive_id()
    path = f"/drives/{drive_id}/items/{folder_id}:/{nom_fichier}:/content"
    logger.info(f"Upload photo : {nom_fichier} ({len(contenu)} octets)")
    file_data = client.put_binary(path, data=contenu, content_type=content_type)

    return {
        "id": file_data["id"],
        "name": file_data["name"],
        "webUrl": file_data["webUrl"],
        "size": file_data.get("size", 0),
    }


def _convertir_valeur(cle_metier, valeur):
    # Listes/dicts : serialisation JSON pour la colonne donnees_enfants
    if isinstance(valeur, (list, dict)):
        return json.dumps(valeur, ensure_ascii=False)
    return valeur


def creer_ligne_dossier(donnees):
    client = get_graph_client()
    site_id = get_site_id()
    list_id = get_list_id()

    fields = {}
    for cle_metier, valeur in donnees.items():
        if cle_metier not in SHAREPOINT_COLUMNS:
            logger.warning(f"Cle '{cle_metier}' inconnue, ignoree")
            continue
        nom_interne = SHAREPOINT_COLUMNS[cle_metier]
        fields[nom_interne] = _convertir_valeur(cle_metier, valeur)

    if SHAREPOINT_COLUMNS["statut"] not in fields:
        fields[SHAREPOINT_COLUMNS["statut"]] = "En attente"
    if SHAREPOINT_COLUMNS["date_soumission"] not in fields:
        fields[SHAREPOINT_COLUMNS["date_soumission"]] = _now_iso()

    body = {"fields": fields}
    logger.info(f"Creation ligne pour '{donnees.get('nom_adherent', '?')}'")
    item = client.post(f"/sites/{site_id}/lists/{list_id}/items", json=body)

    return {"id": item["id"], "webUrl": item.get("webUrl", "")}


def soumettre_dossier_complet(donnees, photos):
    nom = donnees.get("nom_adherent")
    if not nom:
        raise ValueError("Le champ 'nom_adherent' est obligatoire")

    num = donnees.get("numero_adherent", "")

    dossier = creer_dossier_adherent(nom=nom, num_adherent=num)

    photos_uploadees = []
    for nom_fichier, content_type, contenu in photos:
        photo_info = uploader_photo(
            folder_id=dossier["id"],
            nom_fichier=nom_fichier,
            contenu=contenu,
            content_type=content_type,
        )
        photos_uploadees.append(photo_info)

    donnees_avec_lien = donnees.copy()
    donnees_avec_lien["lien_dossier"] = dossier["webUrl"]
    ligne = creer_ligne_dossier(donnees_avec_lien)

    return {
        "dossier": dossier,
        "photos": photos_uploadees,
        "ligne_liste_id": ligne["id"],
        "ligne_liste_url": ligne["webUrl"],
    }


if __name__ == "__main__":
    import io
    from PIL import Image

    print("Test du module sharepoint_writer\n")

    print("1) Recuperation des IDs SharePoint...")
    print(f"   Site ID  : {get_site_id()[:50]}...")
    print(f"   Drive ID : {get_drive_id()[:30]}...")
    print(f"   List ID  : {get_list_id()[:30]}...\n")

    print("2) Soumission d'un dossier de test complet...")

    img = Image.new("RGB", (200, 200), color=(15, 110, 86))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    fake_photo = buf.getvalue()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    donnees_test = {
        "nom_adherent":    f"TEST_INTEGRATION_{timestamp}",
        "numero_adherent": "9999",
        "telephone":       "+225 07 00 00 00 00",
        "type_adherent":   "Renouvellement",
        "cmu_adherent":    "CMU-TEST-12345",
        "a_un_conjoint":   False,
        "nb_enfants":      0,
        "notes":           "Ligne creee par le test d'integration.",
    }

    photos_test = [
        ("recu_BOA_test.jpg",        "image/jpeg", fake_photo),
        ("certificat_CNPS_test.jpg", "image/jpeg", fake_photo),
        ("justif_CMU_test.jpg",      "image/jpeg", fake_photo),
    ]

    result = soumettre_dossier_complet(donnees=donnees_test, photos=photos_test)

    print(f"   OK Dossier cree : {result['dossier']['name']}")
    print(f"      URL : {result['dossier']['webUrl']}")
    print(f"   OK {len(result['photos'])} photo(s) uploadee(s)")
    for p in result["photos"]:
        print(f"      - {p['name']}  ({p['size']} octets)")
    print(f"   OK Ligne liste creee (ID {result['ligne_liste_id']})")
    print(f"      URL : {result['ligne_liste_url']}")

    print("\nIntegration complete fonctionnelle !")