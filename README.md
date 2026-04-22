# Midara v1.2.1
### Générateur de jeu de test statistiquement conforme

Midara fait partie du **Projet Anonyx**, dédié à la protection et à la maîtrise des données.

| Module | Rôle |
|---|---|
| **Midara** | Génération de jeux de test synthétiques (ce module) |
| **anonyx_Mask** | Pseudonymisation de données _(à venir)_ |

---

## 1. Fonctionnalités

- Chargement de fichiers : CSV (détection automatique du séparateur), XLSX, Parquet
- Inférence automatique du type de colonne avec heuristiques :
  - **Identifiants** → traitement texte, rééchantillonnage propre sans `.0`
  - **Années**  → traitement catégoriel, valeurs entières restituées
  - **Dates catégorielles** → normalisation des clés `value_counts` via `str(k.date())`
- Génération synthétique :
  - Numérique : KDE + clip sur [min, max], tolérance ±5 % (configurable)
  - Catégoriel / booléen : distribution observée, divergence Jensen-Shannon ≤ 0,05
  - Texte : rééchantillonnage ou pattern regex (conformité ≥ 95 %)
  - Datetime : interpolation uniforme sur [min, max]
- Contraintes de corrélation inter-colonnes (Pearson / Spearman, |r| > 0,7), copule gaussienne
- **Statistiques bivariées toutes paires** avec filtrage spectral (Kaiser λ > 1) :
  - r² de Pearson (num × num), V de Cramér (cat × cat), η² (num × cat)
  - Heatmap triangulaire original (bleu) / synthétique (orange)
- Interface en 6 blocs séquentiels :
  - ① Vue par colonne : accordéon titre fixe + détail colonne par colonne
  - ② Corrélations sensibles
  - ③ Génération
  - ④ Qualité du jeu de test : score, 4 métriques, colonnes KO, heatmap corrélations, heatmap bivariée
  - ⑤ Rapport détaillé : conformité colonne par colonne (expander)
  - ⑥ Export
- Export multi-formats (CSV, XLSX, Parquet) + rapport HTML téléchargeable

---

## 2. Stack technique

| Composant | Choix |
|---|---|
| Langage | Python ≥ 3.14 |
| Gestion des dépendances | Poetry |
| Interface utilisateur | Streamlit (CSS personnalisé, palette `#006699`) |
| Conteneurisation | Docker + docker-compose |

---

## 3. Démarrage rapide

**En local :**
```bash
cd gentest
poetry install
make run
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
| Tolérance statistiques numériques | ±5 % | Oui (1 %–20 %) |
| Seuil divergence JS (catégoriel) | ≤ 0,05 | Oui (0,01–0,20) |
| Taux conformité regex (texte) | ≥ 95 % | Oui (50 %–100 %) |
| Seuil corrélation sensible | \|r\| > 0,7 | Non |
| Seuil Kaiser (filtrage spectral bivarié) | λ > 1 | Non |

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
│   │   │   ├── bivariate.py    # Statistiques bivariées + filtrage spectral
│   │   │   ├── generator.py    # Génération synthétique
│   │   │   └── validator.py    # Rapport de conformité
│   │   └── ui/
│   │       ├── components.py   # CSS + composants réutilisables
│   │       └── layout.py       # Mise en page Streamlit
│   └── static/
│       ├── logo_anonyx_gen.png
│       └── Logo_complet.png
├── .streamlit/
│   └── config.toml
├── pyproject.toml
├── Makefile
├── Dockerfile
├── docker-compose.yml
├── exigences.md
└── VERSION
```

---

## 6. Changelog

### v1.2.0
- Nouveau module `bivariate.py` : statistiques d'association toutes paires (r², V de Cramér, η²)
- Filtrage spectral des colonnes peu informatives (décomposition propre, critère Kaiser λ > 1)
- Heatmap triangulaire original/synthétique dans le bloc ④
- Cache de la matrice bivariée originale en session (recalcul uniquement si changement de fichier)

### v1.1.0
- Nouveau bloc **④ Qualité du jeu de test** : 4 métriques, tableau KO, heatmap corrélations
- Bloc ① restructuré : titre `section_header` hors accordéon, expander `Détail des colonnes`
- Bloc ⑤ Rapport détaillé et ⑥ Export (renumérotation)
- Logo sidebar supprimé, logo page principale via `st.image` (pas de rognage)
- Correction normalisation clés `value_counts` pour colonnes catégorielles contenant des `Timestamp`
- Nettoyage : suppression du code mort (`COLOR_ACCENT`, `card()`, `Optional`, `_warnings.py`)
- Optimisation : heuristiques de typage calculées une seule fois par colonne

### v1.0.1
- Version initiale publique

---

## 7. Limites

- Les corrélations bivariées contraintes restent limitées aux paires numériques validées par l'utilisateur
- Les regex trop restrictives peuvent réduire la diversité des valeurs générées
- La divergence Jensen-Shannon est calculée sur des distributions discrétisées ; les colonnes à très haute cardinalité peuvent nécessiter un ajustement manuel du seuil
- Python 3.14 est en version RC — si l'image `python:3.14-slim` n'est pas disponible sur Docker Hub, utiliser temporairement `3.13-slim`

---

## 8. Licence

Apache-2.0 — © Aperto Nota · https://aperto-nota.fr
