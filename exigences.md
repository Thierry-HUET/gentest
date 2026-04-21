# Spécification – Exigences formelles
## Midara v1.2.0 — Générateur de jeu de test statistiquement conforme

> Midara est le premier module du **Projet Anonyx** (Aperto Nota),
> dédié à la protection et à la maîtrise des données personnelles et sensibles.

---

## 1. Exigences générales

### REQ-GEN-01 – Nature du composant ✅

Le système SHALL être implémenté sous la forme d'une application conteneurisée, déployable via Docker, exposant une interface utilisateur web réalisée avec Streamlit et un CSS personnalisé (sans dépendance à un framework CSS externe).

### REQ-GEN-02 – Objectif ✅

Le système SHALL permettre la génération de jeux de données synthétiques respectant les statistiques et dépendances observées dans un jeu de données d'entrée, en préservant la confidentialité des données originales.

### REQ-GEN-03 – Environnement d'exécution ✅

Le système SHALL être développé en Python ≥ 3.14, géré via Poetry, et packagé dans une image Docker. Le package Python SHALL être nommé `anonyx` et le point d'entrée Streamlit SHALL être `src/anonyx/app.py`.

### REQ-GEN-04 – Projet Anonyx ✅

Midara SHALL s'inscrire dans le **Projet Anonyx**. Les modules suivants sont prévus :

| Module | Rôle |
|---|---|
| **Midara** | Génération de jeux de test synthétiques (ce module) |
| anonyx_Mask | Pseudonymisation de données |

---

## 2. Exigences d'entrées/sorties

### REQ-IO-01 – Formats supportés ✅

Le système SHALL supporter en entrée et en sortie les formats CSV, XLSX et Parquet.

### REQ-IO-02 – Détection du séparateur CSV ✅

Pour les fichiers CSV, le système SHALL détecter automatiquement le séparateur parmi les valeurs suivantes : virgule (`,`), point-virgule (`;`), tabulation (`\t`), pipe (`|`).

### REQ-IO-03 – Préservation du schéma ✅

Le système SHALL préserver les noms et l'ordre des colonnes du jeu original.

---

## 3. Exigences d'inférence de type

### REQ-TYPE-01 – Types reconnus ✅

Le système SHALL inférer automatiquement le type sémantique de chaque colonne parmi : `numeric`, `categorical`, `boolean`, `text`, `datetime`, `unknown`.

### REQ-TYPE-02 – Heuristique identifiant ✅

Le système SHALL détecter les colonnes numériques représentant des identifiants (MMSI, codes, index…) selon les critères suivants (OR) :
- Le nom de la colonne contient un mot-clé identifiant (`id`, `code`, `num`, `mmsi`, `ref`, `uuid`…)
- La colonne est de type entier avec une cardinalité > 80 %

Les colonnes identifiées SHALL être requalifiées en type `text` et rééchantillonnées sans conversion flottante parasite (pas de suffixe `.0`).

### REQ-TYPE-03 – Heuristique année ✅

Le système SHALL détecter les colonnes numériques représentant des années selon les critères suivants (AND) :
- Toutes les valeurs sont des entiers dans [1000, 2100]
- Le nom contient un mot-clé année (`annee`, `year`, `construction`, `fabrication`…) OU la cardinalité est ≤ 200

Les colonnes identifiées SHALL être requalifiées en type `categorical` et les valeurs SHALL être restituées comme entiers dans le jeu synthétique.

### REQ-TYPE-04 – Normalisation des clés catégorielles pour les dates ✅

Le système SHALL normaliser les clés du dictionnaire `value_counts` pour les colonnes catégorielles contenant des valeurs de type `Timestamp` : la clé SHALL être produite via `str(k.date())` afin d'éviter le suffixe `00:00:00` et garantir la correspondance avec les valeurs affichées dans l'interface.

---

## 4. Exigences statistiques

### REQ-STA-01 – Colonnes numériques ✅

Le système SHALL respecter min, max, moyenne, écart-type, quantiles (Q25, Q50, Q75) et taux de nulls avec une tolérance par défaut de ±5 % par rapport aux valeurs observées sur le jeu d'origine. Cette tolérance SHALL être configurable par l'utilisateur via l'interface (1 % à 20 %).

### REQ-STA-02 – Colonnes catégorielles ✅

Le système SHALL respecter les distributions de modalités en utilisant la divergence de Jensen-Shannon (JS) comme métrique de référence. La valeur seuil par défaut SHALL être JS ≤ 0,05, configurable par l'utilisateur (0,01 à 0,20).

### REQ-STA-03 – Colonnes texte ✅

Le système SHALL générer des valeurs conformes aux regex définies par colonne. Le taux minimal de conformité par défaut SHALL être de 95 %, configurable par l'utilisateur (50 % à 100 %). En l'absence de regex, le système SHALL rééchantillonner depuis les valeurs originales.

---

## 5. Corrélations inter-colonnes

### REQ-COR-01 – Détection de sensibilité ✅

Le système SHALL calculer un score de sensibilité pour chaque paire de colonnes numériques selon les règles suivantes :
- Coefficient de Pearson par défaut
- Coefficient de Spearman si l'écart |Pearson − Spearman| > 0,15
- Une paire est signalée comme sensible si |r| > 0,7

### REQ-COR-02 – Validation utilisateur ✅

Le système SHALL présenter à l'utilisateur les paires détectées comme sensibles et lui permettre de sélectionner celles à contraindre lors de la génération.

### REQ-COR-03 – Implémentation ✅

Le système SHALL appliquer les contraintes de corrélation via une copule gaussienne (décomposition de Cholesky) sur les paires validées par l'utilisateur.

---

## 5bis. Statistiques bivariées

### REQ-BIV-01 – Matrice d’association généralisée ✅

Le système SHALL calculer un score d’association normalisé [0,1] pour toutes les paires de colonnes éligibles (type `numeric`, `categorical`, `boolean`). La mesure utilisée SHALL dépendre des types des deux colonnes :

| Paire | Mesure | Intervalle |
|---|---|---|
| Numérique × Numérique | r² de Pearson | [0, 1] |
| Catégoriel × Catégoriel | V de Cramér | [0, 1] |
| Numérique × Catégoriel | η² (rapport de corrélation) | [0, 1] |
| Booléen × * | traité comme catégoriel | — |
| Texte / Datetime × * | exclu | — |

Les colonnes ayant moins de 5 valeurs non nulles SHALL être exclues.

### REQ-BIV-02 – Filtrage spectral (Kaiser) ✅

Le système SHALL filtrer les colonnes peu informatives par décomposition spectrale de la matrice d’association :
- Décomposition propre (`numpy.linalg.eigh`) de la matrice N×N
- Sélection des axes significatifs selon le critère de Kaiser : valeurs propres λ > 1
- Calcul de la contribution de chaque colonne aux axes significatifs (cos²)
- Conservation des colonnes dont la contribution ≥ contribution moyenne
- Fallback : si aucune VP > 1, conserver l’axe principal (VP maximale)

### REQ-BIV-03 – Heatmap triangulaire ✅

L’interface SHALL afficher une heatmap triangulaire des associations sur les colonnes retenues :
- **Triangle supérieur** : scores d’association du jeu original (palette bleu)
- **Triangle inférieur** : scores d’association du jeu synthétique + Δ (palette orange) — affiché après génération uniquement
- **Diagonale** : valeur 1.000 (fond neutre)
- Chaque cellule SHALL afficher le score et le type de mesure (r², V, η²)

### REQ-BIV-04 – Cache et performance ✅

Le calcul bivarié sur le jeu original SHALL être mis en cache dans la session (clé = nom du fichier) afin d’éviter un recalcul à chaque rechargement de page. Le calcul sur le jeu synthétique SHALL être déclenché uniquement lors de la génération.

---

## 6. Interface utilisateur

### REQ-UI-01 – Structure ✅

L'interface SHALL être organisée en 6 blocs séquentiels :

| # | Bloc | Statut |
|---|---|---|
| ① | Vue par colonne (profil + type + résultat + regex) | ✅ |
| ② | Corrélations sensibles | ✅ |
| ③ | Génération | ✅ |
| ④ | Qualité du jeu de test (score, métriques, colonnes KO, heatmap) | ✅ |
| ⑤ | Rapport détaillé (conformité colonne par colonne) | ✅ |
| ⑥ | Export | ✅ |

### REQ-UI-02 – Vue par colonne ✅

Chaque colonne SHALL disposer d'un expander affichant côte à côte le profil original et le résultat synthétique après génération. L'expander SHALL s'ouvrir automatiquement si la colonne est non conforme (KO).

Le bloc ① SHALL afficher son titre (`section_header`) **hors** de l'accordéon. L'accordéon intérieur SHALL porter le label `Détail des colonnes` et son titre SHALL inclure le nombre de colonnes et le statut global (KO / tout OK).

### REQ-UI-03 – Signalement des heuristiques ✅

L'interface SHALL signaler visuellement les colonnes requalifiées par heuristique :
- Badge `⚠ identifiant` pour les colonnes requalifiées en texte
- Badge `📅 année` pour les colonnes requalifiées en catégoriel

### REQ-UI-04 – Bloc qualité ✅

Le bloc ④ SHALL afficher :
- Une barre de progression du score global de conformité
- 4 cartes métriques : score global, colonnes conformes, corrélations OK, lignes générées — colorées selon le statut (vert si conforme, rouge sinon)
- Un tableau des colonnes KO avec nom, type et motif
- La heatmap des corrélations contraintes
- Un aperçu du jeu synthétique (expander replié par défaut)

### REQ-UI-05 – Logo sidebar ✅

Le logo produit affiché en haut de la sidebar SHALL être rendu sur fond blanc avec des coins arrondis (`border-radius: 10px`) pour assurer la lisibilité quelle que soit la couleur de fond de la sidebar.

---

## 7. Validation

### REQ-VAL-01 – Rapport ✅

Le système SHALL produire un rapport de conformité indiquant :
- La conformité globale (score synthétique en %)
- La conformité par colonne avec motif KO concis (≤ 3 mots)
- La conformité par paire de colonnes validée

Le rapport SHALL être exportable au format HTML.

### REQ-VAL-02 – Motifs KO ✅

| Type | Motif KO |
|---|---|
| Numérique | Libellés des métriques en échec (ex : `moyenne dérivée, Q75 dérivé`) |
| Catégoriel | `distribution divergente` |
| Texte | `regex non conforme` |
| Corrélation | `corrélation non préservée` |

---

## 8. Qualité du code

### REQ-QUA-01 – Suppression du code mort ✅

Le code SHALL ne pas contenir de fonctions, imports ou constantes inutilisés. Les éléments suivants ont été supprimés lors du nettoyage v1.1.0 :
- `from typing import Optional` (natif Python 3.10+)
- `COLOR_ACCENT` (non consommé)
- `card()` dans `components.py` (non appelée)
- Appel redondant à `_enrich_text_profile` dans `build_report`
- Fichier `_warnings.py` orphelin (non importé)

### REQ-QUA-02 – Élimination des calculs redondants ✅

Les heuristiques `_is_likely_identifier`, `_is_likely_year` et `_is_integer_valued` SHALL être calculées une seule fois par colonne dans `profile_dataframe` et transmises à `infer_column_type` via paramètres optionnels, afin d'éviter les doubles appels.

---

## 9. Versionnement

Le fichier `VERSION` à la racine du projet fait référence. La version courante est **1.2.0**.
