"""
App Flask ARECIE - Collecte des dossiers ASMAR 2026
Flux 1 : verification carte bloquee -> soumission justificatifs renouvellement
Flux 2 : depot dossier de remboursement avec scan factures -> envoi DPS
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import base64
import os
import secrets
import json as _json
from pathlib import Path as _Path
from io import BytesIO
import requests as _requests
from dotenv import load_dotenv

load_dotenv()

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, Response, abort,
)
from PIL import Image
from app.sharepoint_writer import soumettre_dossier_complet

# === Chargement des cartes bloquees ===
_CARTES_FILE = _Path(__file__).parent / "data" / "cartes_bloquees.json"
try:
    with open(_CARTES_FILE, encoding="utf-8") as _f:
        CARTES_BLOQUEES = _json.load(_f)
    print(f"[OK] {len(CARTES_BLOQUEES)} cartes bloquees chargees")
except FileNotFoundError:
    CARTES_BLOQUEES = []
    print("[WARN] cartes_bloquees.json introuvable")

# === Cle API Anthropic ===
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if ANTHROPIC_API_KEY:
    print("[OK] Cle API Anthropic chargee")
else:
    print("[WARN] ANTHROPIC_API_KEY manquante — validation IA desactivee")

# === Configuration Flask ===
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="../static",
    static_url_path="/static",
)

app.secret_key = secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

# Cache photos en memoire (1 worker obligatoire)
PHOTOS_CACHE: dict = {}

# === Prompts de validation IA ===
PROMPTS_VALIDATION = {
    "recu_BOA": (
        "Tu es un assistant de validation documentaire pour l'ARECIE, association de retraites ivoiriens. "
        "Analyse cette image et reponds UNIQUEMENT en JSON valide, sans markdown ni backticks. "
        "Verifie : "
        "1) Est-ce bien un recu de versement de la BOA (Bank of Africa) ou un document bancaire BOA ? "
        "2) Y a-t-il une date de l'annee 2025 visible sur le document ? "
        "3) Le document est-il suffisamment lisible (texte net, non flou, non tronque, montant visible) ? "
        "Reponds avec ce format JSON exact : "
        "{\"nature_ok\": true, \"nature_msg\": \"...\", "
        "\"date_ok\": true, \"date_msg\": \"...\", "
        "\"lisibilite_ok\": true, \"lisibilite_msg\": \"...\", "
        "\"resume\": \"...\"}"
    ),
    "certificat_CNPS": (
        "Tu es un assistant de validation documentaire pour l'ARECIE, association de retraites ivoiriens. "
        "Analyse cette image et reponds UNIQUEMENT en JSON valide, sans markdown ni backticks. "
        "Verifie : "
        "1) Est-ce bien un certificat de vie CNPS (Caisse Nationale de Prevoyance Sociale) "
        "ou un recu de depot de certificat de vie CNPS ? "
        "2) Y a-t-il une date de l'annee 2025 visible sur le document ? "
        "3) Le document est-il suffisamment lisible (texte net, non flou, non tronque) ? "
        "Reponds avec ce format JSON exact : "
        "{\"nature_ok\": true, \"nature_msg\": \"...\", "
        "\"date_ok\": true, \"date_msg\": \"...\", "
        "\"lisibilite_ok\": true, \"lisibilite_msg\": \"...\", "
        "\"resume\": \"...\"}"
    ),
    "cmu_adherent": (
        "Tu es un assistant de validation documentaire pour l'ARECIE, association de retraites ivoiriens. "
        "Analyse cette image et reponds UNIQUEMENT en JSON valide, sans markdown ni backticks. "
        "Verifie : "
        "1) Est-ce bien une carte CMU (Couverture Maladie Universelle) ivoirienne "
        "ou un justificatif CMU (attestation, recepisse) ? "
        "2) Y a-t-il une date ou une annee 2025 visible sur le document ? "
        "3) Le document est-il suffisamment lisible (numero CMU visible, texte net, non flou) ? "
        "Reponds avec ce format JSON exact : "
        "{\"nature_ok\": true, \"nature_msg\": \"...\", "
        "\"date_ok\": true, \"date_msg\": \"...\", "
        "\"lisibilite_ok\": true, \"lisibilite_msg\": \"...\", "
        "\"resume\": \"...\"}"
    ),
}


# ── Validation IA (flux renouvellement) ──────────────────────────────────────

def valider_document_ia(image_bytes, type_doc, mime_type):
    if not ANTHROPIC_API_KEY:
        return {"disponible": False}
    prompt = PROMPTS_VALIDATION.get(type_doc)
    if not prompt:
        return {"disponible": False}
    if mime_type.startswith("image/") and len(image_bytes) > 3 * 1024 * 1024:
        img = Image.open(BytesIO(image_bytes))
        img.thumbnail((1200, 1200))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        image_bytes = buf.getvalue()
        mime_type = "image/jpeg"
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    try:
        resp = _requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":          ANTHROPIC_API_KEY,
                "anthropic-version":  "2023-06-01",
                "content-type":       "application/json",
            },
            json={
                "model":      "claude-sonnet-4-6",
                "max_tokens": 1024,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type":       "base64",
                            "media_type": mime_type,
                            "data":       b64,
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            },
            timeout=30,
        )
        resp.raise_for_status()
        texte = resp.json()["content"][0]["text"].strip()
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        resultat = _json.loads(texte)
        resultat["disponible"] = True
        return resultat
    except Exception as e:
        print(f"[WARN] Validation IA echouee pour {type_doc}: {e}")
        return {"disponible": False}


# ── Helpers communs ───────────────────────────────────────────────────────────

def chercher_carte(query):
    q = query.strip().upper()
    if not q or len(q) < 3:
        return "erreur", []
    resultats = []
    for carte in CARTES_BLOQUEES:
        if (
            q in carte["username"].upper()
            or q in carte["matricule_willis"].upper()
            or q in carte["nom"].upper()
            or q in carte["prenom"].upper()
        ):
            resultats.append(carte)
    if not resultats:
        return "non_bloquee", []
    if len(resultats) > 3:
        return "ambigu", resultats
    return "bloquee", resultats


def get_donnees():
    if "donnees" not in session:
        session["donnees"] = {}
    return session["donnees"]


def get_session_id():
    if "sid" not in session:
        session["sid"] = secrets.token_hex(16)
    return session["sid"]


def _stocker_fichier(cache_key: str, meta_key: str, cle: str, fichier_storage):
    """
    Stocke un fichier (photo ou document) dans PHOTOS_CACHE.
    Detecte les images via PIL independamment du content_type declare
    (correction bug extensions numeriques sur Android).
    """
    contenu_brut = fichier_storage.read()
    nom_original = fichier_storage.filename or "fichier.jpg"
    type_mime    = fichier_storage.content_type or ""

    try:
        with Image.open(BytesIO(contenu_brut)) as probe:
            probe.verify()
        img = Image.open(BytesIO(contenu_brut))
        max_dim = 1600
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        contenu_final = buf.getvalue()
        type_mime = "image/jpeg"
        ext = "jpg"
    except Exception:
        contenu_final = contenu_brut
        parts = nom_original.rsplit(".", 1)
        if len(parts) == 2 and parts[1].isalpha() and 1 <= len(parts[1]) <= 5:
            ext = parts[1].lower()
        elif type_mime and "/" in type_mime:
            ext = type_mime.split("/")[-1].split(";")[0].strip().lower()
        else:
            ext = "bin"
        if not type_mime:
            type_mime = "application/octet-stream"

    PHOTOS_CACHE.setdefault(cache_key, {})[cle] = {
        "nom":      f"{cle}.{ext}",
        "type_mime": type_mime,
        "contenu":  contenu_final,
        "taille_mo": round(len(contenu_final) / (1024 * 1024), 2),
    }
    session[meta_key] = session.get(meta_key, {})
    session[meta_key][cle] = {
        "nom":      f"{cle}.{ext}",
        "taille_mo": PHOTOS_CACHE[cache_key][cle]["taille_mo"],
    }
    session.modified = True
    return contenu_final, type_mime


def stocker_photo(session_id, cle, fichier_storage):
    """Flux renouvellement ASMAR."""
    return _stocker_fichier(session_id, "photos_meta", cle, fichier_storage)


def stocker_doc_remb(session_id, cle, fichier_storage):
    """Flux remboursement."""
    return _stocker_fichier(f"remb_{session_id}", "remb_photos_meta", cle, fichier_storage)


def supprimer_photo(session_id, cle):
    if session_id in PHOTOS_CACHE and cle in PHOTOS_CACHE[session_id]:
        del PHOTOS_CACHE[session_id][cle]
    for meta_key in ("photos_meta", "validations"):
        if meta_key in session and cle in session[meta_key]:
            del session[meta_key][cle]
            session.modified = True


def supprimer_doc_remb(session_id, cle):
    remb_key = f"remb_{session_id}"
    if remb_key in PHOTOS_CACHE and cle in PHOTOS_CACHE[remb_key]:
        del PHOTOS_CACHE[remb_key][cle]
    if "remb_photos_meta" in session and cle in session["remb_photos_meta"]:
        del session["remb_photos_meta"][cle]
        session.modified = True


def get_remb_donnees():
    if "remb_donnees" not in session:
        session["remb_donnees"] = {}
    return session["remb_donnees"]


# ═══════════════════════════════════════════════════════════════════════════════
# FLUX 1 — Renouvellement ASMAR (routes existantes)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET", "POST"])
def accueil():
    resultat = None
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if len(query) < 3:
            resultat = {"status": "erreur", "message": "Saisissez au moins 3 caracteres."}
        else:
            status, cartes = chercher_carte(query)
            if status == "bloquee":
                session["carte_verifiee"] = cartes[0]
                session.modified = True
            resultat = {"status": status, "cartes": cartes, "count": len(cartes)}
    return render_template("etape_0_accueil.html", resultat=resultat, query=query)


@app.route("/identite", methods=["GET", "POST"])
def identite():
    d = get_donnees()
    erreurs = []
    carte = session.get("carte_verifiee", {})
    if carte and not d.get("nom_adherent"):
        d["nom_adherent"]   = f"{carte.get('prenom', '')} {carte.get('nom', '')}".strip().title()
        d["numero_adherent"] = carte.get("matricule_willis", "")
        session.modified = True
    if request.method == "POST":
        d["nom_adherent"]   = request.form.get("nom_adherent", "").strip()
        d["numero_adherent"] = request.form.get("numero_adherent", "").strip()
        d["telephone"]      = request.form.get("telephone", "").strip()
        d["type_adherent"]  = request.form.get("type_adherent", "Renouvellement")
        session.modified = True
        if not d["nom_adherent"]:
            erreurs.append("Le nom est obligatoire")
        if not d["telephone"]:
            erreurs.append("Le numero WhatsApp est obligatoire")
        if not erreurs:
            return redirect(url_for("recu_boa"))
    return render_template("etape_1_identite.html", d=d, erreurs=erreurs)


@app.route("/recu-boa", methods=["GET", "POST"])
def recu_boa():
    sid = get_session_id()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action")
        if action == "remplacer":
            supprimer_photo(sid, "recu_BOA")
            return redirect(url_for("recu_boa"))
        if action == "suivant":
            if "recu_BOA" in session.get("photos_meta", {}):
                return redirect(url_for("certificat_cnps"))
            else:
                erreurs.append("Veuillez transmettre la photo du recu BOA")
        fichier = request.files.get("photo")
        if fichier and fichier.filename:
            contenu, mime = stocker_photo(sid, "recu_BOA", fichier)
            validation = valider_document_ia(contenu, "recu_BOA", mime)
            session.setdefault("validations", {})["recu_BOA"] = validation
            session.modified = True
            return redirect(url_for("recu_boa"))
    photo_meta = session.get("photos_meta", {}).get("recu_BOA")
    validation  = session.get("validations", {}).get("recu_BOA")
    return render_template("etape_2_recu_boa.html",
                           photo=photo_meta, erreurs=erreurs, validation=validation)


@app.route("/certificat-cnps", methods=["GET", "POST"])
def certificat_cnps():
    sid = get_session_id()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action")
        if action == "remplacer":
            supprimer_photo(sid, "certificat_CNPS")
            return redirect(url_for("certificat_cnps"))
        if action == "suivant":
            if "certificat_CNPS" in session.get("photos_meta", {}):
                return redirect(url_for("cmu_adherent"))
            else:
                erreurs.append("Veuillez transmettre la photo du certificat CNPS")
        fichier = request.files.get("photo")
        if fichier and fichier.filename:
            contenu, mime = stocker_photo(sid, "certificat_CNPS", fichier)
            validation = valider_document_ia(contenu, "certificat_CNPS", mime)
            session.setdefault("validations", {})["certificat_CNPS"] = validation
            session.modified = True
            return redirect(url_for("certificat_cnps"))
    photo_meta = session.get("photos_meta", {}).get("certificat_CNPS")
    validation  = session.get("validations", {}).get("certificat_CNPS")
    return render_template("etape_3_certificat_cnps.html",
                           photo=photo_meta, erreurs=erreurs, validation=validation)


@app.route("/cmu-adherent", methods=["GET", "POST"])
def cmu_adherent():
    sid = get_session_id()
    d = get_donnees()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action")
        if action == "remplacer":
            supprimer_photo(sid, "cmu_adherent")
            d["cmu_adherent"] = request.form.get("cmu_adherent", "").strip()
            session.modified = True
            return redirect(url_for("cmu_adherent"))
        d["cmu_adherent"] = request.form.get("cmu_adherent", "").strip()
        session.modified = True
        fichier = request.files.get("photo")
        if fichier and fichier.filename:
            contenu, mime = stocker_photo(sid, "cmu_adherent", fichier)
            validation = valider_document_ia(contenu, "cmu_adherent", mime)
            session.setdefault("validations", {})["cmu_adherent"] = validation
            session.modified = True
            return redirect(url_for("cmu_adherent"))
        if action == "suivant":
            if not d["cmu_adherent"]:
                erreurs.append("Le numero CMU est obligatoire")
            if "cmu_adherent" not in session.get("photos_meta", {}):
                erreurs.append("La photo de la carte CMU est obligatoire")
            if not erreurs:
                return redirect(url_for("conjoint"))
    photo_meta = session.get("photos_meta", {}).get("cmu_adherent")
    validation  = session.get("validations", {}).get("cmu_adherent")
    return render_template("etape_4_cmu_adherent.html",
                           d=d, photo=photo_meta, erreurs=erreurs, validation=validation)


@app.route("/conjoint", methods=["GET", "POST"])
def conjoint():
    sid = get_session_id()
    d = get_donnees()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action")
        if action == "remplacer":
            supprimer_photo(sid, "cmu_conjoint")
            return redirect(url_for("conjoint"))
        a_un_conjoint = request.form.get("a_un_conjoint") == "Oui"
        d["a_un_conjoint"] = a_un_conjoint
        if a_un_conjoint:
            d["nom_conjoint"] = request.form.get("nom_conjoint", "").strip()
            d["cmu_conjoint"] = request.form.get("cmu_conjoint", "").strip()
        else:
            d.pop("nom_conjoint", None)
            d.pop("cmu_conjoint", None)
            supprimer_photo(sid, "cmu_conjoint")
        session.modified = True
        fichier = request.files.get("photo")
        if fichier and fichier.filename:
            stocker_photo(sid, "cmu_conjoint", fichier)
            return redirect(url_for("conjoint"))
        if action == "suivant":
            if a_un_conjoint:
                if not d.get("nom_conjoint"):
                    erreurs.append("Le nom du conjoint est obligatoire")
                if not d.get("cmu_conjoint"):
                    erreurs.append("Le numero CMU du conjoint est obligatoire")
                if "cmu_conjoint" not in session.get("photos_meta", {}):
                    erreurs.append("La photo de la carte CMU du conjoint est obligatoire")
            if not erreurs:
                return redirect(url_for("enfants"))
    photo_meta = session.get("photos_meta", {}).get("cmu_conjoint")
    return render_template("etape_5_conjoint.html", d=d, photo=photo_meta, erreurs=erreurs)


@app.route("/enfants", methods=["GET", "POST"])
def enfants():
    sid = get_session_id()
    d = get_donnees()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action")
        if action and action.startswith("remplacer_"):
            cle = action.replace("remplacer_", "")
            supprimer_photo(sid, cle)
            return redirect(url_for("enfants"))
        nb = int(request.form.get("nb_enfants", 0))
        d["nb_enfants"] = nb
        for i in range(1, 3):
            cle_photo = f"cmu_enfant_{i}"
            if i <= nb:
                d[f"nom_enfant_{i}"] = request.form.get(f"nom_enfant_{i}", "").strip()
                d[f"cmu_enfant_{i}"] = request.form.get(f"cmu_enfant_{i}", "").strip()
                fichier = request.files.get(f"photo_{i}")
                if fichier and fichier.filename:
                    stocker_photo(sid, cle_photo, fichier)
            else:
                d.pop(f"nom_enfant_{i}", None)
                d.pop(f"cmu_enfant_{i}", None)
                supprimer_photo(sid, cle_photo)
        d["donnees_enfants"] = [
            {"nom": d.get(f"nom_enfant_{i}", ""), "cmu": d.get(f"cmu_enfant_{i}", "")}
            for i in range(1, nb + 1)
        ]
        session.modified = True
        if action == "suivant":
            for i in range(1, nb + 1):
                if not d.get(f"nom_enfant_{i}"):
                    erreurs.append(f"Nom de l'enfant {i} obligatoire")
                if not d.get(f"cmu_enfant_{i}"):
                    erreurs.append(f"Numero CMU de l'enfant {i} obligatoire")
                if f"cmu_enfant_{i}" not in session.get("photos_meta", {}):
                    erreurs.append(f"Photo CMU enfant {i} obligatoire")
            if not erreurs:
                return redirect(url_for("recapitulatif"))
        else:
            return redirect(url_for("enfants"))
    return render_template(
        "etape_6_enfants.html",
        d=d,
        photos_meta=session.get("photos_meta", {}),
        erreurs=erreurs,
    )


@app.route("/recapitulatif", methods=["GET", "POST"])
def recapitulatif():
    if request.method == "POST":
        return redirect(url_for("envoyer"))
    return render_template(
        "etape_7_recapitulatif.html",
        d=get_donnees(),
        photos_meta=session.get("photos_meta", {}),
    )


@app.route("/envoyer")
def envoyer():
    sid = get_session_id()
    d = get_donnees()
    try:
        photos_a_envoyer = []
        mapping = {
            "recu_BOA":        "recu_BOA",
            "certificat_CNPS": "certificat_CNPS",
            "cmu_adherent":    "justificatif_CMU_adherent",
            "cmu_conjoint":    "justificatif_CMU_conjoint",
            "cmu_enfant_1":    "justificatif_CMU_enfant_1",
            "cmu_enfant_2":    "justificatif_CMU_enfant_2",
        }
        cache_session = PHOTOS_CACHE.get(sid, {})
        for cle, suffixe in mapping.items():
            photo = cache_session.get(cle)
            if photo:
                ext = photo["nom"].split(".")[-1].lower()
                photos_a_envoyer.append(
                    (f"{suffixe}.{ext}", photo["type_mime"], photo["contenu"])
                )
        donnees_propres = {
            k: v for k, v in d.items()
            if not k.startswith("nom_enfant_") and not k.startswith("cmu_enfant_")
        }
        result = soumettre_dossier_complet(donnees=donnees_propres, photos=photos_a_envoyer)
        if sid in PHOTOS_CACHE:
            del PHOTOS_CACHE[sid]
        return render_template(
            "etape_8_confirmation.html",
            success=True,
            ref_id=result["ligne_liste_id"],
        )
    except Exception as e:
        return render_template(
            "etape_8_confirmation.html",
            success=False,
            error=str(e),
        )


@app.route("/photo-preview/<cle>")
def photo_preview(cle):
    sid = get_session_id()
    photo = PHOTOS_CACHE.get(sid, {}).get(cle)
    if not photo:
        abort(404)
    return Response(photo["contenu"], mimetype=photo["type_mime"])


@app.route("/nouveau-dossier")
def nouveau_dossier():
    sid = get_session_id()
    if sid in PHOTOS_CACHE:
        del PHOTOS_CACHE[sid]
    session.clear()
    return redirect(url_for("accueil"))


# ═══════════════════════════════════════════════════════════════════════════════
# FLUX 2 — Remboursement ASMAR (nouvelles routes)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/remboursement")
def remboursement_accueil():
    return render_template("remb_0_accueil.html")


@app.route("/remboursement/identite", methods=["GET", "POST"])
def remboursement_identite():
    d = get_remb_donnees()
    erreurs = []
    if request.method == "POST":
        d["nom_adherent"]    = request.form.get("nom_adherent", "").strip()
        d["numero_adherent"] = request.form.get("numero_adherent", "").strip()
        d["telephone"]       = request.form.get("telephone", "").strip()
        session.modified = True
        if not d["nom_adherent"]:
            erreurs.append("Le nom est obligatoire")
        if not d["telephone"]:
            erreurs.append("Le numero WhatsApp est obligatoire")
        if not erreurs:
            return redirect(url_for("remboursement_documents"))
    return render_template("remb_1_identite.html", d=d, erreurs=erreurs)


@app.route("/remboursement/documents", methods=["GET", "POST"])
def remboursement_documents():
    sid = get_session_id()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action", "")
        if action.startswith("remplacer_"):
            supprimer_doc_remb(sid, action.replace("remplacer_", ""))
            return redirect(url_for("remboursement_documents"))
        for cle, champ in [("ordonnance", "ordonnance"), ("bulletin_examen", "bulletin_examen")]:
            fichier = request.files.get(champ)
            if fichier and fichier.filename:
                stocker_doc_remb(sid, cle, fichier)
                return redirect(url_for("remboursement_documents"))
        if action == "suivant":
            if "ordonnance" not in session.get("remb_photos_meta", {}):
                erreurs.append("L'ordonnance medicale est obligatoire")
            if not erreurs:
                return redirect(url_for("remboursement_factures"))
    photos_meta = session.get("remb_photos_meta", {})
    return render_template("remb_2_documents.html", photos_meta=photos_meta, erreurs=erreurs)


@app.route("/remboursement/factures", methods=["GET", "POST"])
def remboursement_factures():
    sid = get_session_id()
    erreurs = []
    if request.method == "POST":
        action = request.form.get("action", "")
        if action.startswith("remplacer_"):
            supprimer_doc_remb(sid, action.replace("remplacer_", ""))
            return redirect(url_for("remboursement_factures"))
        for i in range(1, 4):
            fichier = request.files.get(f"facture_{i}")
            if fichier and fichier.filename:
                stocker_doc_remb(sid, f"facture_{i}", fichier)
                return redirect(url_for("remboursement_factures"))
        if action == "suivant":
            if "facture_1" not in session.get("remb_photos_meta", {}):
                erreurs.append("Au moins une facture est obligatoire")
            if not erreurs:
                return redirect(url_for("remboursement_recapitulatif"))
    photos_meta = session.get("remb_photos_meta", {})
    return render_template("remb_3_factures.html", photos_meta=photos_meta, erreurs=erreurs)


@app.route("/remboursement/recapitulatif", methods=["GET", "POST"])
def remboursement_recapitulatif():
    if request.method == "POST":
        return redirect(url_for("remboursement_envoyer"))
    return render_template(
        "remb_4_recapitulatif.html",
        d=get_remb_donnees(),
        photos_meta=session.get("remb_photos_meta", {}),
    )


@app.route("/remboursement/envoyer")
def remboursement_envoyer():
    from app.remb_writer import soumettre_remboursement
    sid = get_session_id()
    d = get_remb_donnees()
    try:
        remb_key = f"remb_{sid}"
        cache_remb = PHOTOS_CACHE.get(remb_key, {})
        documents = []
        for cle in ["ordonnance", "bulletin_examen", "facture_1", "facture_2", "facture_3"]:
            doc = cache_remb.get(cle)
            if doc:
                documents.append((doc["nom"], doc["type_mime"], doc["contenu"]))

        result = soumettre_remboursement(donnees=d, documents=documents)

        if remb_key in PHOTOS_CACHE:
            del PHOTOS_CACHE[remb_key]
        session.pop("remb_donnees",     None)
        session.pop("remb_photos_meta", None)
        session.modified = True

        return render_template(
            "remb_5_confirmation.html",
            success=True,
            dossier_name=result["dossier"]["name"],
            dossier_url=result["dossier"]["webUrl"],
            email_sent=result["email"].get("sent", False),
            nb_docs=len(result["documents"]),
        )
    except Exception as e:
        return render_template(
            "remb_5_confirmation.html",
            success=False,
            error=str(e),
        )


@app.route("/remboursement/photo-preview/<cle>")
def remb_photo_preview(cle):
    sid = get_session_id()
    doc = PHOTOS_CACHE.get(f"remb_{sid}", {}).get(cle)
    if not doc:
        abort(404)
    return Response(doc["contenu"], mimetype=doc["type_mime"])


@app.route("/remboursement/nouveau")
def remboursement_nouveau():
    sid = get_session_id()
    remb_key = f"remb_{sid}"
    if remb_key in PHOTOS_CACHE:
        del PHOTOS_CACHE[remb_key]
    session.pop("remb_donnees",     None)
    session.pop("remb_photos_meta", None)
    session.modified = True
    return redirect(url_for("remboursement_accueil"))


# ── Lancement local ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)