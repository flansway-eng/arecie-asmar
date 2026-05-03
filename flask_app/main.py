"""
App Flask ARECIE - Collecte des dossiers ASMAR 2026
Version finale
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, redirect, url_for, session, Response, abort
from io import BytesIO
from PIL import Image
import secrets

from app.sharepoint_writer import soumettre_dossier_complet


app = Flask(
    __name__,
    template_folder="templates",
    static_folder="../static",
    static_url_path="/static",
)

app.secret_key = secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

PHOTOS_CACHE = {}


def get_donnees():
    if "donnees" not in session:
        session["donnees"] = {}
    return session["donnees"]


def get_session_id():
    if "sid" not in session:
        session["sid"] = secrets.token_hex(16)
    return session["sid"]


def stocker_photo(session_id, cle, fichier_storage):
    contenu_brut = fichier_storage.read()
    nom_original = fichier_storage.filename or "photo.jpg"
    type_mime = fichier_storage.content_type or "image/jpeg"

    if type_mime.startswith("image/"):
        img = Image.open(BytesIO(contenu_brut))
        max_dim = 1600
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        contenu_compresse = buf.getvalue()
        type_mime = "image/jpeg"
        ext = "jpg"
    else:
        contenu_compresse = contenu_brut
        ext = nom_original.split(".")[-1].lower()

    PHOTOS_CACHE.setdefault(session_id, {})[cle] = {
        "nom": f"{cle}.{ext}",
        "type_mime": type_mime,
        "contenu": contenu_compresse,
        "taille_mo": round(len(contenu_compresse) / (1024 * 1024), 2),
    }

    session["photos_meta"] = session.get("photos_meta", {})
    session["photos_meta"][cle] = {
        "nom": f"{cle}.{ext}",
        "taille_mo": PHOTOS_CACHE[session_id][cle]["taille_mo"],
    }
    session.modified = True


def supprimer_photo(session_id, cle):
    if session_id in PHOTOS_CACHE and cle in PHOTOS_CACHE[session_id]:
        del PHOTOS_CACHE[session_id][cle]
    if "photos_meta" in session and cle in session["photos_meta"]:
        del session["photos_meta"][cle]
        session.modified = True


@app.route("/")
def accueil():
    return render_template("etape_0_accueil.html")


@app.route("/identite", methods=["GET", "POST"])
def identite():
    d = get_donnees()
    erreurs = []

    if request.method == "POST":
        d["nom_adherent"] = request.form.get("nom_adherent", "").strip()
        d["numero_adherent"] = request.form.get("numero_adherent", "").strip()
        d["telephone"] = request.form.get("telephone", "").strip()
        d["type_adherent"] = request.form.get("type_adherent", "Renouvellement")
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
            stocker_photo(sid, "recu_BOA", fichier)
            return redirect(url_for("recu_boa"))

    photo_meta = session.get("photos_meta", {}).get("recu_BOA")
    return render_template("etape_2_recu_boa.html", photo=photo_meta, erreurs=erreurs)


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
            stocker_photo(sid, "certificat_CNPS", fichier)
            return redirect(url_for("certificat_cnps"))

    photo_meta = session.get("photos_meta", {}).get("certificat_CNPS")
    return render_template("etape_3_certificat_cnps.html", photo=photo_meta, erreurs=erreurs)


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
            stocker_photo(sid, "cmu_adherent", fichier)
            return redirect(url_for("cmu_adherent"))

        if action == "suivant":
            if not d["cmu_adherent"]:
                erreurs.append("Le numero CMU est obligatoire")
            if "cmu_adherent" not in session.get("photos_meta", {}):
                erreurs.append("La photo de la carte CMU est obligatoire")

            if not erreurs:
                return redirect(url_for("conjoint"))

    photo_meta = session.get("photos_meta", {}).get("cmu_adherent")
    return render_template("etape_4_cmu_adherent.html", d=d, photo=photo_meta, erreurs=erreurs)


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
            "recu_BOA":         "recu_BOA",
            "certificat_CNPS":  "certificat_CNPS",
            "cmu_adherent":     "justificatif_CMU_adherent",
            "cmu_conjoint":     "justificatif_CMU_conjoint",
            "cmu_enfant_1":     "justificatif_CMU_enfant_1",
            "cmu_enfant_2":     "justificatif_CMU_enfant_2",
        }

        cache_session = PHOTOS_CACHE.get(sid, {})
        for cle, suffixe in mapping.items():
            photo = cache_session.get(cle)
            if photo:
                ext = photo["nom"].split(".")[-1].lower()
                nom_final = f"{suffixe}.{ext}"
                photos_a_envoyer.append(
                    (nom_final, photo["type_mime"], photo["contenu"])
                )

        donnees_propres = {
            k: v for k, v in d.items()
            if not k.startswith("nom_enfant_") and not k.startswith("cmu_enfant_")
        }

        result = soumettre_dossier_complet(
            donnees=donnees_propres,
            photos=photos_a_envoyer,
        )

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)