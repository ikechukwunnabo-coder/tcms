#!/usr/bin/env bash
# Local/CI verification for TCMS (Linux/macOS). Usage:
#   ./scripts/verify.sh [--skip-tests] [--skip-deploy-check]
set -euo pipefail

cd "$(dirname "$0")/.."
export USE_SQLITE="${USE_SQLITE:-true}"
skip_tests=0
skip_deploy=0
for arg in "$@"; do
  case "$arg" in
    --skip-tests) skip_tests=1 ;;
    --skip-deploy-check) skip_deploy=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ "$skip_tests" -eq 0 ]; then
  echo "==> Django test suite"
  python manage.py test
fi

echo "==> Ruff lint"
python -m ruff check apps config scripts

echo "==> Django system check"
python manage.py check

echo "==> Migration drift"
python manage.py makemigrations --check --dry-run

echo "==> OpenAPI schema"
python manage.py spectacular --file schema.yml

if [ "$skip_deploy" -eq 0 ]; then
  echo "==> Production deploy check"
  saved_settings="${DJANGO_SETTINGS_MODULE-}"
  saved_secret="${SECRET_KEY-}"
  saved_hosts="${ALLOWED_HOSTS-}"
  DJANGO_SETTINGS_MODULE=config.settings.prod \
    SECRET_KEY="verify-only-not-a-production-secret-0123456789-abcdefghij" \
    ALLOWED_HOSTS="tcms.example.com" \
    python manage.py check --deploy
  export DJANGO_SETTINGS_MODULE="$saved_settings"
  export SECRET_KEY="$saved_secret"
  export ALLOWED_HOSTS="$saved_hosts"
fi

echo "All verification checks passed."
