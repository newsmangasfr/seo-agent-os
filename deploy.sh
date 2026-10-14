#!/usr/bin/env bash
# ============================================================
# deploy.sh — déploiement Agent OS SANS PERTE de données
#
# Problème xCloud : pour prendre le nouveau code il faut recréer le
# site (le redeploy ne re-tire pas le git), ce qui remet le volume à
# zéro. Ce script sauvegarde la base AVANT et la restaure APRÈS.
#
# Usage :  ./deploy.sh
# ============================================================
set -e
cd "$(dirname "$0")"

echo "== 1. Sauvegarde de la base de données actuelle =="
python deploy_helper.py backup || echo "(pas de base à sauvegarder — premier déploiement)"

echo "== 2. Recréation du site (clone propre du dernier commit) =="
python deploy_helper.py recreate

echo "== 3. Restauration de la base sauvegardée =="
python deploy_helper.py restore || echo "(rien à restaurer)"

echo "== Terminé. Ouvre https://agentos.1wp.site et reconnecte-toi si besoin. =="
