"""
Module remb_writer
Gestion des dossiers de remboursement ASMAR 2026 :
  - Depot des scans dans la bibliotheque "Remboursements ASMAR"
  - Envoi email automatique a la DPS/WTW avec les pieces jointes
"""

import os
import re
import base64
import logging
import time
import requests as _requests
from datetime import datetime, timezone
from app.graph_client import get_graph_client

logger = logging.getLogger(__name__)

SHAREPOINT_TENANT       = os.environ.get("SHAREPOINT_TENANT", "")
SHAREPOINT_SITE_NAME    = os.environ.get("SHAREPOINT_SITE_NAME", "")
SHAREPOINT_LIBRARY_REMB = os.environ.get("SHAREPOINT_LIBRARY_REMB", "Remboursements ASMAR")
MAIL_DPS                = os.environ.get("MAIL_DPS", "")
MAIL_SENDER             = os.environ.get("MAIL_SENDER", "")
MAIL_CC                 = os.environ.get("MAIL_CC", "")
AZURE_TENANT_ID         = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID         = os.environ.get("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET     = os.environ.get("AZURE_CLIENT_SECRET", "")

_cache = {"site_id": None, "remb_drive_id": None}
_token_cache: dict = {"token": None, "expires_at": 0}


# ── Auth ──────────────────────────────────────────────────────────────────────

def _get_mail_token() -> str:
    """Obtient un access token Graph avec scope Mail.Send."""
    if _token_cache["token"] and _token_cache["expires_at"] > time.time() + 60:
        return _token_cache["token"]
    resp = _requests.post(
        f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type":    "client_credentials",
            "client_id":     AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "scope":         "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _token_cache["token"]


# ── SharePoint helpers ────────────────────────────────────────────────────────

def get_site_id() -> str:
    if _cache["site_id"] is None:
        client = get_graph_client()
        path = f"/sites/{SHAREPOINT_TENANT}.sharepoint.com:/sites/{SHAREPOINT_SITE_NAME}"
        _cache["site_id"] = client.get(path)["id"]
    return _cache["site_id"]


def get_remb_drive_id() -> str:
    if _cache["remb_drive_id"] is None:
        client = get_graph_client()
        drives = client.get(f"/sites/{get_site_id()}/drives").get("value", [])
        target = next((d for d in drives if d.get("name") == SHAREPOINT_LIBRARY_REMB), None)
        if not target:
            raise RuntimeError(
                f"Bibliotheque '{SHAREPOINT_LIBRARY_REMB}' introuvable — "
                "verifier la variable SHAREPOINT_LIBRARY_REMB"
            )
        _cache["remb_drive_id"] = target["id"]
    return _cache["remb_drive_id"]


def _slugify(texte: str) -> str:
    texte = texte.strip()
    texte = re.sub(r"\s+", "_", texte)
    texte = re.sub(r"[^A-Za-z0-9\u00C0-\u00FF_\-]", "", texte)
    return texte


# ── Dossier et upload ─────────────────────────────────────────────────────────

def creer_dossier_remb(nom: str, num_adherent: str = "") -> dict:
    """Cree un dossier date-stampe dans la bibliotheque Remboursements ASMAR."""
    client = get_graph_client()
    drive_id = get_remb_drive_id()
    safe_nom = _slugify(nom)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{safe_nom}_{num_adherent}_{ts}" if num_adherent else f"{safe_nom}_{ts}"

    body = {
        "name": folder_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": "rename",
    }
    logger.info(f"Creation dossier remboursement : {folder_name}")
    folder = client.post(f"/drives/{drive_id}/root/children", json=body)
    return {
        "id":     folder["id"],
        "name":   folder["name"],
        "webUrl": folder["webUrl"],
    }


def uploader_document_remb(
    folder_id: str, nom_fichier: str, contenu: bytes, content_type: str = "image/jpeg"
) -> dict:
    client = get_graph_client()
    drive_id = get_remb_drive_id()
    path = f"/drives/{drive_id}/items/{folder_id}:/{nom_fichier}:/content"
    logger.info(f"Upload remb : {nom_fichier} ({len(contenu)} octets)")
    file_data = client.put_binary(path, data=contenu, content_type=content_type)
    return {
        "id":     file_data["id"],
        "name":   file_data["name"],
        "webUrl": file_data["webUrl"],
        "size":   file_data.get("size", 0),
    }


# ── Email DPS ─────────────────────────────────────────────────────────────────

def envoyer_email_dps(donnees: dict, dossier_url: str, documents: list) -> dict:
    """
    Envoie un email a la DPS (WTW) avec les scans en pieces jointes.
    documents : list of (nom_fichier, content_type, contenu_bytes)
    """
    if not MAIL_DPS or not MAIL_SENDER:
        logger.warning("MAIL_DPS ou MAIL_SENDER non configure — email non envoye")
        return {"sent": False, "reason": "MAIL_DPS ou MAIL_SENDER manquant"}

    nom  = donnees.get("nom_adherent", "")
    num  = donnees.get("numero_adherent", "")
    tel  = donnees.get("telephone", "")
    date = datetime.now().strftime("%d/%m/%Y a %Hh%M")

    # Pieces jointes
    attachments = []
    for nom_fichier, content_type, contenu in documents:
        b64 = base64.standard_b64encode(contenu).decode("utf-8")
        attachments.append({
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name":         nom_fichier,
            "contentType":  content_type,
            "contentBytes": b64,
        })

    subject = f"Demande remboursement ASMAR 2026 — {nom} ({num})"

    body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto">
  <div style="background:#0F6E56;padding:20px;border-radius:8px 8px 0 0">
    <h2 style="color:white;margin:0">Demande de remboursement ASMAR 2026</h2>
    <p style="color:#c8e6c9;margin:4px 0 0">Secretariat General &mdash; ARECIE</p>
  </div>
  <div style="background:#f0faf5;padding:16px;border-left:4px solid #0F6E56">
    <p style="margin:0;font-weight:bold;color:#0F6E56">
      Nouvelle demande de remboursement deposee en ligne
    </p>
    <p style="margin:4px 0 0;font-size:13px;color:#166534">
      {len(attachments)} document(s) en piece(s) jointe(s)
    </p>
  </div>
  <div style="padding:24px;background:white;border:1px solid #e5e7eb;border-top:none">
    <h3 style="color:#0F6E56;margin-top:0">Informations adherent</h3>
    <table style="width:100%;border-collapse:collapse">
      <tr style="background:#f9fafb">
        <td style="padding:8px 12px;color:#6b7280;width:42%">Nom adherent</td>
        <td style="padding:8px 12px;font-weight:600">{nom}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6b7280">N&deg; adherent</td>
        <td style="padding:8px 12px;font-weight:600">{num}</td>
      </tr>
      <tr style="background:#f9fafb">
        <td style="padding:8px 12px;color:#6b7280">Telephone WhatsApp</td>
        <td style="padding:8px 12px">{tel}</td>
      </tr>
      <tr>
        <td style="padding:8px 12px;color:#6b7280">Date soumission</td>
        <td style="padding:8px 12px">{date}</td>
      </tr>
      <tr style="background:#f9fafb">
        <td style="padding:8px 12px;color:#6b7280">Dossier SharePoint</td>
        <td style="padding:8px 12px">
          <a href="{dossier_url}" style="color:#0F6E56">Voir les documents</a>
        </td>
      </tr>
    </table>
  </div>
  <div style="padding:16px;background:#f9fafb;border:1px solid #e5e7eb;
              border-top:none;border-radius:0 0 8px 8px;text-align:center">
    <p style="margin:0;font-size:12px;color:#9ca3af">
      Envoye automatiquement par le systeme ARECIE-ASMAR &bull; {date}
    </p>
  </div>
</body></html>"""

    token = _get_mail_token()
    payload: dict = {
        "message": {
            "subject":      subject,
            "body":         {"contentType": "HTML", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": MAIL_DPS}}],
            "ccRecipients": [{"emailAddress": {"address": MAIL_CC}}] if MAIL_CC else None,
            "attachments":  attachments if attachments else None,
        },
        "saveToSentItems": True,
    }

    resp = _requests.post(
        f"https://graph.microsoft.com/v1.0/users/{MAIL_SENDER}/sendMail",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=60,
    )

    if resp.status_code not in (200, 202):
        try:
            err = resp.json()
            msg = err.get("error", {}).get("message", f"HTTP {resp.status_code}")
        except Exception:
            msg = f"HTTP {resp.status_code}"
        logger.error(f"Erreur envoi email DPS : {msg}")
        raise RuntimeError(f"Erreur envoi email DPS : {msg}")

    logger.info(f"Email remboursement envoye a {MAIL_DPS}")
    return {"sent": True, "attachments": len(attachments)}


# ── Point d'entree principal ──────────────────────────────────────────────────

def soumettre_remboursement(donnees: dict, documents: list) -> dict:
    """
    Soumet un dossier de remboursement complet :
      1. Cree un dossier dans "Remboursements ASMAR"
      2. Uploade les documents
      3. Envoie l'email a la DPS (non bloquant si echec)

    donnees  : dict avec nom_adherent, numero_adherent, telephone
    documents: list of (nom_fichier, content_type, contenu_bytes)
    """
    nom = donnees.get("nom_adherent", "INCONNU")
    num = donnees.get("numero_adherent", "")

    # 1. Dossier SharePoint
    dossier = creer_dossier_remb(nom=nom, num_adherent=num)

    # 2. Upload documents
    docs_uploadees = []
    for nom_fichier, content_type, contenu in documents:
        info = uploader_document_remb(
            folder_id=dossier["id"],
            nom_fichier=nom_fichier,
            contenu=contenu,
            content_type=content_type,
        )
        docs_uploadees.append(info)

    # 3. Email DPS (non bloquant)
    try:
        email_result = envoyer_email_dps(donnees, dossier["webUrl"], documents)
    except Exception as e:
        logger.error(f"Email DPS non envoye (upload OK) : {e}")
        email_result = {"sent": False, "reason": str(e)}

    return {
        "dossier":   dossier,
        "documents": docs_uploadees,
        "email":     email_result,
    }