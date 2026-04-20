# Générateur de jeu de test statistiquement conforme (Streamlit + Docker)

Application conteneurisée permettant de :
- Charger un fichier tabulaire en entrée (xlsx, csv, parquet)
- Calculer des statistiques par colonne
- Générer un jeu de test synthétique qui préserve :
  - Noms et ordre des colonnes
  - Un nombre de lignes significatif (paramétrable)
  - Des statistiques par colonne proches de celles du jeu d'origine (tolérance ±5 % par défaut, configurable)
  - Des corrélations inter-colonnes sensibles validées par l'utilisateur (seuil |r| > 0,7)
  - Des contraintes de format texte via regex (conformité ≥ 95 % par défaut)
- Produire un rapport de conformité et exporter le jeu généré

---

## 1. Fonctionnalités

- Lecture de fichiers : CSV, XLSX, Parquet
- Inférence automatique du type de colonne
- Génération synthétique :
  - Numérique / date : distributions empiriques + bornes, tolérance ±5 %
  - Catégoriel / booléen : distributions observées, divergence Jensen-Shannon ≤ 0,05
  - Texte : génération conforme aux regex ou rééchantillonnage (conformité ≥ 95 %)
- Détection des corrélations inter-colonnes sensibles (Pearson / Spearman, |r| > 0,7)
- Validation utilisateur des paires à contraindre
- Rapport de conformité détaillé (global, par colonne, par paire)
- Export multi-formats (CSV, XLSX, Parquet) + rapport PDF/HTML

---

## 2. Stack technique

| Composant | Choix |
|---|---|
| Langage | Python ≥ 3.14 |
| Gestion des dépendances | Poetry |
| Interface utilisateur | Streamlit + Bootstrap 5 |
| Conteneurisation | Docker + docker-compose |

---

## 3. Démarrage rapide

```bash
docker compose up --build
```

Accès via http://localhost:8501

---

## 4. Paramètres de conformité par défaut

| Paramètre | Valeur par défaut | Configurable |
|---|---|---|
| Tolérance statistiques numériques | ±5 % | Oui |
| Seuil divergence JS (catégoriel) | ≤ 0,05 | Oui |
| Taux conformité regex (texte) | ≥ 95 % | Oui |
| Seuil corrélation sensible | \|r\| > 0,7 | Non |

---

## 5. Reproductibilité

À paramètres et seed identiques, les sorties sont considérées conformes lorsque les métriques de validation sont dans les tolérances configurées.

---

## 6. Limites

- Les corrélations sont préservées uniquement pour les paires validées par l'utilisateur
- Les regex trop restrictives peuvent réduire la diversité des données générées
- La divergence Jensen-Shannon est calculée sur les distributions discrétisées ; les colonnes à très haute cardinalité peuvent nécessiter un ajustement manuel

---

## 7. Licence

Apache-2.0
