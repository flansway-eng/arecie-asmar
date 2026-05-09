import pandas as pd
import json
from pathlib import Path

EXCEL_PATH = Path("/mnt/c/Users/DELL USER/OneDrive - Flan'S WaY LLC/Bureau/AGC/Carte BDD/Assistant ASMAR/liste des cartes bloquées pour défaut de paiement.xlsx")

OUT_PATH = Path("flask_app/data/cartes_bloquees.json")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

print(f"Lecture de : {EXCEL_PATH}")
df = pd.read_excel(EXCEL_PATH, header=3)
df.columns = [
    '_', 'USERNAME', 'MATRICULE_WILLIS', 'FIRST_NAME', 'LAST_NAME',
    'MATRICULE_ENTREPRISE', 'SOCIETE', 'COLLEGE', 'DATE_RETRAITE', 'MOTIF', 'AGE'
]
df = df[df['USERNAME'].notna() & (df['USERNAME'] != 'USERNAME')].copy()
df['AGE'] = pd.to_numeric(df['AGE'], errors='coerce')

records = []
for _, r in df.iterrows():
    def val(col):
        v = r[col]
        return str(v).strip() if pd.notna(v) else ""
    records.append({
        "username":         val('USERNAME'),
        "matricule_willis": val('MATRICULE_WILLIS'),
        "prenom":           val('FIRST_NAME'),
        "nom":              val('LAST_NAME'),
        "societe":          val('SOCIETE'),
        "college":          val('COLLEGE'),
        "motif":            val('MOTIF'),
        "age":              int(r['AGE']) if pd.notna(r['AGE']) else None,
    })

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"JSON genere : {len(records)} cartes")
print(f"Fichier     : {OUT_PATH}")
print(f"Taille      : {OUT_PATH.stat().st_size // 1024} Ko")
print(f"Apercu      : {json.dumps(records[0], ensure_ascii=False)}")