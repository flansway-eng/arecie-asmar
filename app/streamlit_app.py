"""
App Streamlit ARECIE - Collecte des dossiers ASMAR 2026
"""

import sys
from pathlib import Path

# Ajouter la racine du projet au path pour permettre les imports app.xxx
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st


# === Configuration ===
st.set_page_config(
    page_title="ARECIE - Renouvellement ASMAR 2026",
    page_icon="📋",
    layout="centered",
)

NB_ETAPES = 9
NOMS_ETAPES = [
    "Accueil",
    "Identite",
    "Recu BOA",
    "Certificat CNPS",
    "CMU adherent",
    "Conjoint",
    "Enfants",
    "Recapitulatif",
    "Confirmation",
]


# === Etat de session ===
def init_state():
    if "etape" not in st.session_state:
        st.session_state.etape = 0
    if "donnees" not in st.session_state:
        st.session_state.donnees = {}
    if "photos" not in st.session_state:
        st.session_state.photos = {}
    if "submission_result" not in st.session_state:
        st.session_state.submission_result = None


def aller_etape(numero):
    st.session_state.etape = numero


def reinitialiser():
    st.session_state.etape = 0
    st.session_state.donnees = {}
    st.session_state.photos = {}
    st.session_state.submission_result = None


# === UI Helpers ===
def afficher_progression():
    etape = st.session_state.etape
    if etape == 0:
        return
    progression = etape / (NB_ETAPES - 1)
    st.progress(progression, text=f"Etape {etape} sur {NB_ETAPES - 1} - {NOMS_ETAPES[etape]}")


def boutons_nav(etape_precedente, etape_suivante, label_suivant="Suivant", suivant_actif=True):
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Precedent", use_container_width=True, key=f"prev_{st.session_state.etape}"):
            aller_etape(etape_precedente)
            st.rerun()
    with col2:
        if st.button(
            label_suivant,
            type="primary",
            use_container_width=True,
            disabled=not suivant_actif,
            key=f"next_{st.session_state.etape}",
        ):
            aller_etape(etape_suivante)
            st.rerun()


def widget_photo(cle_photo, titre, aide=""):
    photo = st.session_state.photos.get(cle_photo)

    if photo:
        st.success(f"OK - {photo['nom']} ({photo['taille_mo']} Mo)")
        if photo["type_mime"].startswith("image/"):
            st.image(photo["contenu"], caption="Apercu", use_container_width=True)
        else:
            st.info("PDF transmis")
        if st.button("Remplacer", key=f"remplacer_{cle_photo}"):
            del st.session_state.photos[cle_photo]
            st.rerun()
        return True

    fichier = st.file_uploader(
        titre,
        type=["jpg", "jpeg", "png", "pdf"],
        help=aide or "Formats : JPG, PNG, PDF (max 10 Mo)",
        key=f"upload_{cle_photo}",
    )

    if fichier is not None:
        taille_mo = len(fichier.getvalue()) / (1024 * 1024)
        if taille_mo > 10:
            st.error(f"Trop volumineux ({taille_mo:.1f} Mo). Max : 10 Mo.")
            return False

        st.session_state.photos[cle_photo] = {
            "nom": fichier.name,
            "type_mime": fichier.type,
            "contenu": fichier.getvalue(),
            "taille_mo": round(taille_mo, 2),
        }
        st.rerun()

    return False


# === Ecran 0 : Accueil ===
def ecran_accueil():
    st.title("ARECIE")
    st.subheader("Renouvellement couverture sante ASMAR 2026")
    st.markdown(
        "Bonjour !\n\n"
        "Cette application va vous guider pour transmettre les documents "
        "necessaires au renouvellement de votre couverture sante ASMAR 2026.\n\n"
        "Cela prend environ **5 minutes**. Vous aurez besoin :\n"
        "- de votre **recu de versement BOA**\n"
        "- de votre **certificat de vie CNPS** (ou son recu de depot)\n"
        "- de votre **numero CMU** et son justificatif\n"
        "- des informations sur votre **conjoint et enfants** s'il y a lieu"
    )
    st.info("Vous pourrez prendre les photos avec votre telephone ou choisir des photos deja prises.")

    if st.button("Commencer", type="primary", use_container_width=True):
        aller_etape(1)
        st.rerun()


# === Ecran 1 : Identite ===
def ecran_identite():
    st.header("Vos informations")
    st.markdown("Commencons par quelques informations sur vous.")

    d = st.session_state.donnees

    nom = st.text_input(
        "Votre nom et prenom complet *",
        value=d.get("nom_adherent", ""),
        placeholder="Ex: Roger Flan",
    )
    num = st.text_input(
        "Votre numero d'adherent ARECIE",
        value=d.get("numero_adherent", ""),
        placeholder="Ex: N° ASMAR : G1532-00XXX(laissez vide si inconnu)",
    )
    tel = st.text_input(
        "Votre numero WhatsApp *",
        value=d.get("telephone", ""),
        placeholder="Ex: +225 07 00 00 00 00",
        help="Pour vous contacter en cas de document manquant",
    )

    types_options = ["Renouvellement", "Nouvel adherent"]
    type_actuel = d.get("type_adherent", "Renouvellement")
    idx = types_options.index(type_actuel) if type_actuel in types_options else 0
    type_adh = st.radio("Vous etes : *", options=types_options, index=idx)

    d["nom_adherent"] = nom
    d["numero_adherent"] = num
    d["telephone"] = tel
    d["type_adherent"] = type_adh

    erreurs = []
    if not nom.strip():
        erreurs.append("Le nom est obligatoire")
    if not tel.strip():
        erreurs.append("Le numero WhatsApp est obligatoire")
    for e in erreurs:
        st.warning(e)

    st.caption("* champs obligatoires")
    boutons_nav(0, 2, suivant_actif=not erreurs)


# === Ecran 2 : Recu BOA ===
def ecran_recu_boa():
    st.header("Recu de versement BOA")
    st.markdown("Photographiez votre **recu de versement BOA** pour la cotisation ASMAR.")
    st.warning("Le **montant** et la **date** doivent etre bien lisibles.")

    photo_ok = widget_photo("recu_BOA", "Photo du recu BOA")

    if not photo_ok:
        st.info("Veuillez transmettre la photo pour continuer.")

    boutons_nav(1, 3, suivant_actif=photo_ok)


# === Ecran 3 : Certificat CNPS ===
def ecran_certificat_cnps():
    st.header("Certificat de vie CNPS")
    st.markdown(
        "Photographiez votre **certificat de vie CNPS** "
        "ou son **recu de depot** si le certificat n'est pas encore disponible."
    )

    photo_ok = widget_photo("certificat_CNPS", "Photo du certificat CNPS ou recu de depot")

    if not photo_ok:
        st.info("Veuillez transmettre la photo pour continuer.")

    boutons_nav(2, 4, suivant_actif=photo_ok)


# === Ecran 4 : CMU adherent ===
def ecran_cmu_adherent():
    st.header("Carte CMU - Adherent")
    st.markdown("Saisissez votre **numero CMU** et joignez le justificatif (carte CMU).")

    d = st.session_state.donnees

    num_cmu = st.text_input(
        "Votre numero de carte CMU *",
        value=d.get("cmu_adherent", ""),
        placeholder="Ex: CI-CMU-XXXXXXXX",
    )
    d["cmu_adherent"] = num_cmu

    photo_ok = widget_photo("cmu_adherent", "Photo de la carte CMU")

    erreurs = []
    if not num_cmu.strip():
        erreurs.append("Le numero CMU est obligatoire")
    if not photo_ok:
        erreurs.append("La photo de la carte CMU est obligatoire")
    for e in erreurs:
        st.warning(e)

    boutons_nav(3, 5, suivant_actif=not erreurs)


# === Ecran 5 : Conjoint ===
def ecran_conjoint():
    st.header("Conjoint beneficiaire")

    d = st.session_state.donnees

    a_conjoint = st.radio(
        "Avez-vous un conjoint beneficiaire ?",
        options=["Non", "Oui"],
        index=1 if d.get("a_un_conjoint", False) else 0,
        horizontal=True,
    )
    d["a_un_conjoint"] = (a_conjoint == "Oui")

    erreurs = []

    if d["a_un_conjoint"]:
        st.markdown("---")
        nom_c = st.text_input(
            "Nom et prenom du conjoint *",
            value=d.get("nom_conjoint", ""),
            placeholder="Ex: KOUASSI Marie",
        )
        cmu_c = st.text_input(
            "Numero CMU du conjoint *",
            value=d.get("cmu_conjoint", ""),
            placeholder="Ex: CI-CMU-XXXXXXXX",
        )
        d["nom_conjoint"] = nom_c
        d["cmu_conjoint"] = cmu_c

        photo_ok = widget_photo("cmu_conjoint", "Photo de la carte CMU du conjoint")

        if not nom_c.strip():
            erreurs.append("Le nom du conjoint est obligatoire")
        if not cmu_c.strip():
            erreurs.append("Le numero CMU du conjoint est obligatoire")
        if not photo_ok:
            erreurs.append("La photo de la carte CMU du conjoint est obligatoire")
        for e in erreurs:
            st.warning(e)
    else:
        d.pop("nom_conjoint", None)
        d.pop("cmu_conjoint", None)
        st.session_state.photos.pop("cmu_conjoint", None)
        st.info("Pas de conjoint beneficiaire declare.")

    boutons_nav(4, 6, suivant_actif=not erreurs)


# === Ecran 6 : Enfants ===
def ecran_enfants():
    st.header("Enfants beneficiaires")
    st.markdown("Combien d'enfants souhaitez-vous declarer comme beneficiaires (max 2) ?")

    d = st.session_state.donnees

    nb_actuel = d.get("nb_enfants", 0)
    nb = st.radio(
        "Nombre d'enfants beneficiaires :",
        options=[0, 1, 2],
        index=nb_actuel,
        horizontal=True,
    )
    d["nb_enfants"] = nb

    erreurs = []
    enfants_data = []

    if nb >= 1:
        st.markdown("---")
        st.subheader("Enfant 1")
        nom_e1 = st.text_input("Nom et prenom *", value=d.get("nom_enfant_1", ""), key="nom_e1")
        cmu_e1 = st.text_input("Numero CMU *", value=d.get("cmu_enfant_1", ""), key="cmu_e1")
        d["nom_enfant_1"] = nom_e1
        d["cmu_enfant_1"] = cmu_e1
        photo1 = widget_photo("cmu_enfant_1", "Photo carte CMU - Enfant 1")
        if not nom_e1.strip():
            erreurs.append("Nom de l'enfant 1 obligatoire")
        if not cmu_e1.strip():
            erreurs.append("Numero CMU de l'enfant 1 obligatoire")
        if not photo1:
            erreurs.append("Photo CMU enfant 1 obligatoire")
        enfants_data.append({"nom": nom_e1, "cmu": cmu_e1})

    if nb >= 2:
        st.markdown("---")
        st.subheader("Enfant 2")
        nom_e2 = st.text_input("Nom et prenom *", value=d.get("nom_enfant_2", ""), key="nom_e2")
        cmu_e2 = st.text_input("Numero CMU *", value=d.get("cmu_enfant_2", ""), key="cmu_e2")
        d["nom_enfant_2"] = nom_e2
        d["cmu_enfant_2"] = cmu_e2
        photo2 = widget_photo("cmu_enfant_2", "Photo carte CMU - Enfant 2")
        if not nom_e2.strip():
            erreurs.append("Nom de l'enfant 2 obligatoire")
        if not cmu_e2.strip():
            erreurs.append("Numero CMU de l'enfant 2 obligatoire")
        if not photo2:
            erreurs.append("Photo CMU enfant 2 obligatoire")
        enfants_data.append({"nom": nom_e2, "cmu": cmu_e2})

    if nb < 2:
        d.pop("nom_enfant_2", None)
        d.pop("cmu_enfant_2", None)
        st.session_state.photos.pop("cmu_enfant_2", None)
    if nb < 1:
        d.pop("nom_enfant_1", None)
        d.pop("cmu_enfant_1", None)
        st.session_state.photos.pop("cmu_enfant_1", None)

    d["donnees_enfants"] = enfants_data

    if nb == 0:
        st.info("Aucun enfant beneficiaire declare.")

    for e in erreurs:
        st.warning(e)

    boutons_nav(5, 7, suivant_actif=not erreurs)


# === Ecran 7 : Recapitulatif ===
def ecran_recapitulatif():
    st.header("Recapitulatif de votre dossier")
    st.markdown("Verifiez toutes les informations avant l'envoi.")

    d = st.session_state.donnees
    photos = st.session_state.photos

    st.subheader("Vos informations")
    st.write(f"**Nom :** {d.get('nom_adherent', '')}")
    st.write(f"**N. adherent :** {d.get('numero_adherent', '(non renseigne)')}")
    st.write(f"**Telephone WhatsApp :** {d.get('telephone', '')}")
    st.write(f"**Type :** {d.get('type_adherent', '')}")
    st.write(f"**N. CMU :** {d.get('cmu_adherent', '')}")

    st.subheader("Documents transmis")
    docs_attendus = [
        ("recu_BOA", "Recu BOA"),
        ("certificat_CNPS", "Certificat CNPS"),
        ("cmu_adherent", "Carte CMU adherent"),
    ]
    for cle, nom in docs_attendus:
        if cle in photos:
            st.write(f"OK - {nom}")
        else:
            st.write(f"MANQUANT - {nom}")

    if d.get("a_un_conjoint"):
        st.subheader("Conjoint")
        st.write(f"**Nom :** {d.get('nom_conjoint', '')}")
        st.write(f"**N. CMU :** {d.get('cmu_conjoint', '')}")
        if "cmu_conjoint" in photos:
            st.write("OK - Carte CMU conjoint")

    nb_enfants = d.get("nb_enfants", 0)
    if nb_enfants > 0:
        st.subheader(f"Enfants ({nb_enfants})")
        for i in range(1, nb_enfants + 1):
            st.write(f"**Enfant {i} :** {d.get(f'nom_enfant_{i}', '')} - CMU {d.get(f'cmu_enfant_{i}', '')}")
            if f"cmu_enfant_{i}" in photos:
                st.write(f"  OK - Photo CMU enfant {i}")

    st.markdown("---")
    st.warning(
        "Une fois envoye, vous ne pourrez plus modifier ce dossier. "
        "Si une information est incorrecte, retournez en arriere."
    )

    boutons_nav(6, 8, label_suivant="Envoyer mon dossier")


# === Ecran 8 : Confirmation (avec envoi reel) ===
def ecran_confirmation():
    if st.session_state.submission_result is None:
        with st.spinner("Transmission de votre dossier en cours..."):
            try:
                from app.sharepoint_writer import soumettre_dossier_complet

                d = st.session_state.donnees
                photos_a_envoyer = []
                mapping = {
                    "recu_BOA":         "recu_BOA",
                    "certificat_CNPS":  "certificat_CNPS",
                    "cmu_adherent":     "justificatif_CMU_adherent",
                    "cmu_conjoint":     "justificatif_CMU_conjoint",
                    "cmu_enfant_1":     "justificatif_CMU_enfant_1",
                    "cmu_enfant_2":     "justificatif_CMU_enfant_2",
                }

                for cle, suffixe in mapping.items():
                    photo = st.session_state.photos.get(cle)
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
                st.session_state.submission_result = {"success": True, "data": result}
            except Exception as e:
                st.session_state.submission_result = {"success": False, "error": str(e)}

    result = st.session_state.submission_result

    if result["success"]:
        st.balloons()
        st.success("Votre dossier a ete transmis avec succes !")
        st.markdown(
            f"**Reference :** Dossier #{result['data']['ligne_liste_id']}\n\n"
            f"Le secretariat de l'ARECIE va verifier vos documents.\n"
            f"En cas de document manquant ou illisible, vous serez recontacte sur votre numero WhatsApp.\n\n"
            f"**Merci de votre confiance !**"
        )
    else:
        st.error("Une erreur s'est produite lors de l'envoi.")
        st.code(result["error"])
        st.markdown(
            "Veuillez reessayer dans quelques minutes ou contacter le secretariat."
        )
        if st.button("Reessayer l'envoi"):
            st.session_state.submission_result = None
            st.rerun()

    if st.button("Nouveau dossier", use_container_width=True):
        reinitialiser()
        st.rerun()


# === Routeur ===
ECRANS = {
    0: ecran_accueil,
    1: ecran_identite,
    2: ecran_recu_boa,
    3: ecran_certificat_cnps,
    4: ecran_cmu_adherent,
    5: ecran_conjoint,
    6: ecran_enfants,
    7: ecran_recapitulatif,
    8: ecran_confirmation,
}


def main():
    init_state()
    afficher_progression()

    etape_actuelle = st.session_state.etape
    fonction_ecran = ECRANS.get(etape_actuelle, ecran_accueil)
    fonction_ecran()

    with st.expander("Etat interne (debug)"):
        st.json({
            "etape": st.session_state.etape,
            "donnees": st.session_state.donnees,
            "photos": list(st.session_state.photos.keys()),
        })


if __name__ == "__main__":
    main()