# ARECIE - Renouvellement ASMAR 2026

Application de collecte des dossiers de renouvellement de la couverture santé ASMAR 2026 pour les retraités EECI et CIE membres de l'ARECIE.

## Description

Cette application Streamlit guide les adhérents à travers un formulaire conversationnel pour transmettre les documents requis :
- Reçu de versement BOA
- Certificat de vie CNPS (ou reçu de dépôt)
- Numéro CMU et justificatif (adhérent + ayants droits)

Les documents sont automatiquement déposés sur SharePoint dans le site `ARECIE-Suivi-ASMAR2026`.

## Architecture

- `app/config.py` — Configuration et chargement des secrets
- `app/graph_client.py` — Client Microsoft Graph (authentification + API)
- `app/sharepoint_writer.py` — Opérations SharePoint (créer dossier, upload, écrire liste)
- `app/streamlit_app.py` — Interface utilisateur conversationnelle
- `tests/` — Scripts de test des intégrations

## Installation locale

```bash
git clone https://github.com/flansway-eng/arecie-asmar.git
cd arecie-asmar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Créer un fichier `.env` à la racine avec les secrets Azure (voir `.env.example`).

## Lancer l'application

```bash
streamlit run app/streamlit_app.py
```

## Déploiement

L'application est déployée sur Streamlit Cloud. Les secrets Azure sont configurés dans les paramètres du déploiement.

## Auteur

ARECIE - Association des Retraités EECI/CIE