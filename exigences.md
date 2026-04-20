# Spécification – Exigences formelles
## Application de génération de jeu de test statistiquement conforme

---

## 1. Exigences générales

### REQ-GEN-01 – Nature du composant

Le système SHALL être implémenté sous la forme d'une application conteneurisée, déployable via Docker, exposant une interface utilisateur web (Streamlit, design Bootstrap 5).

### REQ-GEN-02 – Objectif

Le système SHALL permettre la génération de jeux de données synthétiques respectant les statistiques et dépendances observées dans un jeu de données d'entrée.

### REQ-GEN-03 – Environnement d'exécution

Le système SHALL être développé en Python ≥ 3.14, géré via Poetry, et packagé dans une image Docker. L'interface utilisateur SHALL être réalisée avec Streamlit.

---

## 2. Exigences d'entrées/sorties

### REQ-IO-01 – Formats supportés

Le système SHALL supporter en entrée et en sortie les formats CSV, XLSX et Parquet.

### REQ-IO-02 – Préservation du schéma

Le système SHALL préserver les noms et l'ordre des colonnes.

---

## 3. Exigences statistiques

### REQ-STA-01 – Colonnes numériques

Le système SHALL respecter min, max, moyenne, écart-type, quantiles et taux de nulls avec une tolérance par défaut de ±5 % par rapport aux valeurs observées sur le jeu d'origine. Cette tolérance SHALL être configurable par l'utilisateur via l'interface.

### REQ-STA-02 – Colonnes catégorielles

Le système SHALL respecter les distributions de modalités en utilisant la divergence de Jensen-Shannon (JS) comme métrique de référence. La valeur seuil par défaut SHALL être JS ≤ 0,05, configurable par l'utilisateur.

### REQ-STA-03 – Colonnes texte

Le système SHALL générer des valeurs conformes aux regex définies par colonne. Le taux minimal de conformité par défaut SHALL être de 95 %, configurable par l'utilisateur.

---

## 4. Corrélations inter-colonnes

### REQ-COR-01 – Détection de sensibilité

Le système SHALL calculer un score de sensibilité pour chaque paire de colonnes selon les règles suivantes :
- Colonnes numériques/numériques : coefficient de Pearson
- Colonnes ordinales ou mixtes : coefficient de Spearman
- Une paire est signalée comme sensible si |r| > 0,7

### REQ-COR-02 – Validation utilisateur

Le système SHALL présenter à l'utilisateur les paires détectées comme sensibles et lui permettre de sélectionner celles à contraindre lors de la génération.

### REQ-COR-03 – Périmètre effectif

Le système SHALL appliquer les contraintes de corrélation uniquement aux paires validées par l'utilisateur.

---

## 5. Validation

### REQ-VAL-01 – Rapport

Le système SHALL produire un rapport de conformité indiquant :
- La conformité globale (score synthétique)
- La conformité par colonne (métriques vs tolérances)
- La conformité par paire de colonnes validée (score de corrélation observé vs attendu)

Le rapport SHALL être exportable au format PDF et/ou HTML.
