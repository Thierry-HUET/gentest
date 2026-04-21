# ==============================================================================
# Makefile – Anonyx·Gen
# ==============================================================================
# Usage :
#   make release    → commit, tag, push et GitHub Release (si gh disponible)
#   make commit     → commit simple (sans changement de version ni tag)
#   make push       → push branche courante + tags
#   make status     → affiche l'état git
#   make version    → affiche la version courante
#
# GitHub Release (make release) nécessite gh (GitHub CLI).
# Si gh n'est pas installé, le tag et le push sont effectués mais la release
# GitHub est ignorée avec un avertissement.
# Installation : https://cli.github.com
# ==============================================================================

.DEFAULT_GOAL := help

DATE    := $(shell date '+%Y-%m-%d %H:%M:%S')
VERSION := $(shell cat VERSION | tr -d '[:space:]')
BRANCH  := $(shell git rev-parse --abbrev-ref HEAD)
PROJECT := anonyx
ZIPNAME := $(PROJECT)-$(VERSION).zip

# Détection de gh (optionnel)
GH := $(shell command -v gh 2>/dev/null)

# ------------------------------------------------------------------------------
.PHONY: help
help:
	@echo ""
	@echo "  make release    Commit, tag v$(VERSION), push et GitHub Release"
	@echo "  make commit     Commit de tous les fichiers modifiés (sans tag)"
	@echo "  make push       Push branche courante + tags vers origin"
	@echo "  make status     État du dépôt git"
	@echo "  make version    Affiche la version courante"
	@echo ""
	@echo "  → Pour changer de version : éditer le fichier VERSION puis make release"
	@if [ -z "$(GH)" ]; then \
		echo "  ⚠ gh (GitHub CLI) non trouvé — la publication GitHub sera ignorée."; \
		echo "    Installation : https://cli.github.com"; \
	else \
		echo "  ✓ gh détecté : $(GH)"; \
	fi
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
	@# Synchronisation de pyproject.toml
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
	@echo "  Push terminé."
	@# GitHub Release (optionnelle — nécessite gh)
	@if [ -z "$(GH)" ]; then \
		echo ""; \
		echo "  ⚠ gh non disponible — GitHub Release ignorée."; \
		echo "    Pour publier : installer gh (https://cli.github.com) puis relancer make release."; \
	else \
		echo "→ Génération de l'asset ZIP..."; \
		git archive --format=zip --output "$(ZIPNAME)" "v$(VERSION)"; \
		echo "  Asset créé : $(ZIPNAME)"; \
		echo "→ Publication de la GitHub Release..."; \
		if gh release view "v$(VERSION)" >/dev/null 2>&1; then \
			echo "  Release v$(VERSION) existe déjà — remplacement de l'asset..."; \
			gh release upload "v$(VERSION)" "$(ZIPNAME)" --clobber; \
		else \
			gh release create "v$(VERSION)" "$(ZIPNAME)" \
				--title "v$(VERSION)" \
				--notes "Release v$(VERSION)" \
				--target "$(BRANCH)"; \
		fi; \
		echo ""; \
		echo "  ✓ Release v$(VERSION) publiée avec asset $(ZIPNAME)."; \
	fi
