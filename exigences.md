# Spécification – Exigences formelles
## Application de génération de jeu de test statistiquement conforme

---

## 1. Exigences générales

### REQ-GEN-01 – Nature du composant

Le système SHALL être implémenté sous la forme d'une application conteneurisée, déployable via Docker, exposant une interface utilisateur web.

### REQ-GEN-02 – Objectif

Le système SHALL permettre la génération de jeux de données synthétiques respectant les statistiques et dépendances observées dans un jeu de données d’entrée.

---

## 2. Exigences d’entrées/sorties

### REQ-IO-01 – Formats supportés

Le système SHALL supporter en entrée et en sortie les formats CSV, XLSX et Parquet.

### REQ-IO-02 – Préservation du schéma

Le système SHALL préserver les noms et l’ordre des colonnes.

---

## 3. Exigences statistiques

### REQ-STA-01 – Colonnes numériques

Le système SHALL respecter min, max, moyenne, écart-type, quantiles et taux de nulls selon des tolérances configurables.

### REQ-STA-02 – Colonnes catégorielles

Le système SHALL respecter les distributions de modalités selon une métrique de divergence configurable.

### REQ-STA-03 – Colonnes texte

Le système SHALL générer des valeurs conformes aux regex définies par colonne, avec un taux minimal de conformité configurable.

---

## 4. Corrélations inter-colonnes

### REQ-COR-01 – Détection de sensibilité

Le système SHALL calculer un score de sensibilité pour les paires de colonnes basé sur la force de dépendance et des critères de risque.

### REQ-COR-02 – Validation utilisateur

Le système SHALL permettre à l’utilisateur de valider les paires à contraindre parmi celles proposées.

### REQ-COR-03 – Périmètre effectif

Le système SHALL appliquer les contraintes uniquement aux paires validées par l’utilisateur.

---

## 5. Validation

### REQ-VAL-01 – Rapport

Le système SHALL produire un rapport indiquant la conformité globale, par colonne et par paire de colonnes validée.
