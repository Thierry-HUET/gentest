# ==============================================================================
# Makefile – Anonyx·Gen
# ==============================================================================
# Usage :
#   make release    → commit, tag et push avec la version du fichier VERSION
#   make commit     → commit simple (sans changement de version ni tag)
#   make push       → push branche courante + tags
#   make status     → affiche l'état git
#   make version    → affiche la version courante
#
# Prérequis pour make release avec GitHub Release : gh (GitHub CLI) installé
# Pour changer de version : éditer le fichier VERSION, puis lancer make release
# ==============================================================================

.DEFAULT_GOAL := help

# Horodatage ISO 8601 local
DATE := $(shell date '+%Y-%m-%d %H:%M:%S')

# Version lue depuis le fichier VERSION
VERSION := $(shell cat VERSION | tr -d '[:space:]')

# Branche courante
BRANCH := $(shell git rev-parse --abbrev-ref HEAD)

# Nom du projet et archive
PROJECT := anonyx
ZIPNAME := $(PROJECT)-$(VERSION).zip

# ------------------------------------------------------------------------------
.PHONY: help
help:
	@echo ""
	@echo "  make release    Commit, tag v$(VERSION) et push  (version lue depuis VERSION)"
	@echo "  make commit     Commit de tous les fichiers modifiés (sans tag)"
	@echo "  make push       Push branche courante + tags vers origin"
	@echo "  make status     État du dépôt git"
	@echo "  make version    Affiche la version courante"
	@echo ""
	@echo "  → Pour changer de version : éditer le fichier VERSION puis make release"
	@echo ""

# ------------------------------------------------------------------------------
.PHONY: version
version:
	@echo "Version courante : $(VERSION)"

# ------------------------------------------------------------------------------
.PHONY: status
status:
	@git status

# ------------------------------------------------------------------------------
.PHONY: commit
commit:
	@echo "→ Ajout de tous les fichiers modifiés..."
	@git add -A
	@git diff --cached --quiet \
		&& echo "  Rien à committer." \
		|| git commit -m "[$(DATE)] mise à jour"
	@echo "  Branche : $(BRANCH)"

# ------------------------------------------------------------------------------
.PHONY: push
push:
	@echo "→ Push vers origin/$(BRANCH) (avec tags)..."
	@git push origin $(BRANCH) --tags
	@echo "  Push terminé."

# ------------------------------------------------------------------------------
.PHONY: release
release:
	@echo "→ Version : $(VERSION)"
	@# Synchronisation de pyproject.toml avec le fichier VERSION
	@CURRENT=$$(grep '^version' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	 sed -i.bak "s/^version = \"$$CURRENT\"/version = \"$(VERSION)\"/" pyproject.toml \
	 && rm -f pyproject.toml.bak
	@echo "  pyproject.toml synchronisé."
	@# Commit
	@git add -A
	@git diff --cached --quiet \
		&& echo "  Rien à committer." \
		|| git commit -m "[$(DATE)] release $(VERSION)"
	@# Tag annoté
	@if git rev-parse "v$(VERSION)" >/dev/null 2>&1; then \
		echo "  ⚠ Tag v$(VERSION) déjà existant — skippé."; \
	else \
		git tag -a "v$(VERSION)" -m "[$(DATE)] release $(VERSION)"; \
		echo "  Tag v$(VERSION) créé."; \
	fi
	@# Push branche + tags
	@git push origin $(BRANCH) --tags
	@# Génération de l'asset ZIP
	@echo "→ Génération de l'asset ZIP..."
	@git archive --format=zip --output "$(ZIPNAME)" "v$(VERSION)"
	@echo "  Asset créé : $(ZIPNAME)"
	@# Publication GitHub Release via gh CLI
	@echo "→ Publication de la GitHub Release..."
	@if gh release view "v$(VERSION)" >/dev/null 2>&1; then \
		echo "  Release v$(VERSION) existe déjà — remplacement de l'asset..."; \
		gh release upload "v$(VERSION)" "$(ZIPNAME)" --clobber; \
	else \
		echo "  Création de la release v$(VERSION)..."; \
		gh release create "v$(VERSION)" "$(ZIPNAME)" \
			--title "v$(VERSION)" \
			--notes "Release v$(VERSION)" \
			--target "$(BRANCH)"; \
	fi
	@echo ""
	@echo "  ✓ Release v$(VERSION) publiée avec asset $(ZIPNAME)."
