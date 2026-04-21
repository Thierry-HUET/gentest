# anonyx_Gen
### v1.0.1 - (c) Thierry HUET / APERTO-NOTA - 04/2026
### Générateur de jeu de test statistiquement conforme

anonyx_Gen fait partie de la suite **Anonyx**, dédiée à la protection et à la maîtrise des données.

| Produit | Rôle |
|---|---|
| **anonyx_Gen** | Génération de jeux de test synthétiques (ce module) |
| **anonyx_Mask** | Pseudonymisation de données _(à venir)_ |

---

## 1. Fonctionnalités

- Chargement de fichiers : CSV (détection automatique du séparateur), XLSX, Parquet
- Inférence automatique du type de colonne avec heuristiques :
  - **Identifiants** (MMSI, codes, index…) → traitement texte, rééchantillonnage propre sans `.0`
  - **Années** (construction, fabrication…) → traitement catégoriel, valeurs entières restituées
- Génération synthétique :
  - Numérique : KDE + clip sur [min, max], tolérance ±5 % (configurable)
  - Catégoriel / booléen : distribution observée, divergence Jensen-Shannon ≤ 0,05
  - Texte : rééchantillonnage ou pattern regex (conformité ≥ 95 %)
  - Datetime : interpolation uniforme sur [min, max]
- Contraintes de corrélation inter-colonnes (Pearson / Spearman, |r| > 0,7), copule gaussienne
- Vue par colonne : profil original + résultat synthétique + regex dans un seul expander
- Rapport de conformité détaillé avec motif KO concis par colonne
- Export multi-formats (CSV, XLSX, Parquet) + rapport HTML

---

## 2. Stack technique

| Composant | Choix |
|---|---|
| Langage | Python ≥ 3.14 |
| Gestion des dépendances | Poetry |
| Interface utilisateur | Streamlit (CSS personnalisé, sans dépendance externe) |
| Conteneurisation | Docker + docker-compose |

---

## 3. Démarrage rapide

**En local :**
```bash
cd gentest
poetry install
streamlit run src/anonyx/app.py
```

**Via Docker :**
```bash
docker compose up --build
```

Accès : http://localhost:8501

---

## 4. Paramètres de conformité par défaut

| Paramètre | Valeur par défaut | Configurable |
|---|---|---|
| Tolérance statistiques numériques | ±5 % | Oui |
| Seuil divergence JS (catégoriel) | ≤ 0,05 | Oui |
| Taux conformité regex (texte) | ≥ 95 % | Oui |
| Seuil corrélation sensible | \|r\| > 0,7 | Non |

---

## 5. Arborescence

```
gentest/
├── src/
│   ├── anonyx/
│   │   ├── app.py              # Point d'entrée Streamlit
│   │   ├── core/
│   │   │   ├── loader.py       # Chargement CSV/XLSX/Parquet
│   │   │   ├── profiler.py     # Inférence types + statistiques
│   │   │   ├── correlations.py # Détection corrélations sensibles
│   │   │   ├── generator.py    # Génération synthétique
│   │   │   └── validator.py    # Rapport de conformité
│   │   └── ui/
│   │       ├── components.py   # CSS + composants réutilisables
│   │       └── layout.py       # Mise en page Streamlit
│   └── static/
│       └── Logo_complet.png
├── .streamlit/
│   └── config.toml
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── VERSION
```

---

## 6. Limites

- Les corrélations sont préservées uniquement pour les paires validées par l'utilisateur
- Les regex trop restrictives peuvent réduire la diversité des données générées
- La divergence Jensen-Shannon est calculée sur les distributions discrétisées ; les colonnes à très haute cardinalité peuvent nécessiter un ajustement manuel
- Python 3.14 est en version RC — si l'image `python:3.14-slim` n'est pas disponible sur Docker Hub, utiliser temporairement `3.13-slim`

---

## 7. Licence

Apache-2.0 — © Aperto Nota · https://aperto-nota.fr
