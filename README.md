# Générateur de jeu de test statistiquement conforme (Streamlit + Docker)

Application conteneurisée permettant de
- Charger un fichier tabulaire en entrée (xlsx, csv, parquet)
- Calculer des statistiques par colonne
- Générer un jeu de test synthétique qui préserve
  - Noms et ordre des colonnes
  - Un nombre de lignes significatif (paramétrable)
  - Des statistiques par colonne proches de celles du jeu d’origine (avec tolérances)
  - Des corrélations inter-colonnes sensibles validées par l’utilisateur
  - Des contraintes de format texte via regex
- Produire un rapport de conformité et exporter le jeu généré

---

## 1. Fonctionnalités

- Lecture de fichiers : CSV, XLSX, Parquet
- Inférence automatique du type de colonne
- Génération synthétique
  - Numérique / date : distributions empiriques + bornes
  - Catégoriel / booléen : distributions observées
  - Texte : génération conforme aux regex ou rééchantillonnage
- Détection des corrélations inter-colonnes sensibles
- Validation utilisateur des paires à contraindre
- Rapport de conformité détaillé
- Export multi-formats

---

## 2. Démarrage rapide

```bash
docker compose up --build
```

Accès via http://localhost:8501

---

## 3. Reproductibilité

À paramètres et seed identiques, les sorties sont considérées conformes lorsque les métriques de validation sont équivalentes selon les tolérances configurées.

---

## 4. Limites

- Les corrélations sont préservées uniquement pour les paires validées par l’utilisateur
- Les regex trop restrictives peuvent réduire la diversité des données générées

---

## 5. Licence

À définir
