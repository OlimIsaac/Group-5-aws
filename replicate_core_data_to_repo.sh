#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="import"
PYTHON_BIN="python"
MANAGE_PATH="$SCRIPT_DIR/manage.py"
FIXTURE_PATH="$SCRIPT_DIR/sample_data/core_data_replica.json"
ASSUME_YES=0
SKIP_MIGRATE=0
KEEP_EXISTING=0

MODELS=(
  core.User
  core.ClinicianProfile
  core.PatientProfile
  core.ClinicianPatientAssignment
  core.SensorData
  core.PressureFrame
  core.Comment
  core.Feedback
  core.PainZoneReport
  core.HeatmapAnnotation
)

COUNT_SNIPPET="from core.models import User, ClinicianPatientAssignment, SensorData, PressureFrame, Comment, Feedback, PainZoneReport, HeatmapAnnotation; print('users=' + str(User.objects.count()) + ', assignments=' + str(ClinicianPatientAssignment.objects.count()) + ', sensor_data=' + str(SensorData.objects.count()) + ', pressure_frames=' + str(PressureFrame.objects.count()) + ', comments=' + str(Comment.objects.count()) + ', feedback=' + str(Feedback.objects.count()) + ', pain_reports=' + str(PainZoneReport.objects.count()) + ', annotations=' + str(HeatmapAnnotation.objects.count()))"

usage() {
  cat <<'EOF'
Cross-machine data replication for this repository.

Usage:
  ./replicate_core_data_to_repo.sh export [options]
  ./replicate_core_data_to_repo.sh import [options]
  ./replicate_core_data_to_repo.sh status [options]
  ./replicate_core_data_to_repo.sh [options]      # same as import

Options:
  --fixture PATH         Fixture file path.
                         Default: sample_data/core_data_replica.json
  --python BIN           Python executable (default: python)
  --manage PATH          manage.py path (default: ./manage.py)
  --yes                  Skip confirmation before deleting existing core data
  --skip-migrate         Skip migrate before import
  --keep-existing        Keep current DB rows before loaddata (may cause conflicts)
  --help                 Show this help

Workflow:
  Source machine:
    1) ./replicate_core_data_to_repo.sh export
    2) git add sample_data/core_data_replica.json && git commit && git push

  Target machine:
    1) git pull
    2) ./replicate_core_data_to_repo.sh

Notes:
- This script works within one repo clone and is meant for transport via GitHub.
- Default import deletes core.User first (cascade) unless --keep-existing is used.
EOF
}

abs_path() {
  local path="$1"
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$SCRIPT_DIR/$path"
  fi
}

print_snapshot() {
  echo "Current DB snapshot:"
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" "$MANAGE_PATH" shell -c "$COUNT_SNIPPET")
}

confirm_import_delete() {
  if [[ $ASSUME_YES -eq 1 ]]; then
    return 0
  fi

  if [[ ! -t 0 ]]; then
    echo "Error: refusing to delete existing data in non-interactive mode without --yes."
    exit 1
  fi

  echo
  echo "About to delete all core.User rows (cascade) before import."
  read -r -p "Continue? [y/N]: " reply
  if [[ "${reply,,}" != "y" ]]; then
    echo "Aborted by user."
    exit 1
  fi
}

do_export() {
  mkdir -p "$(dirname "$FIXTURE_PATH")"

  echo "Exporting data to fixture: $FIXTURE_PATH"
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" "$MANAGE_PATH" dumpdata "${MODELS[@]}" --indent 2 --output "$FIXTURE_PATH")

  if [[ ! -s "$FIXTURE_PATH" ]]; then
    echo "Error: fixture is missing or empty: $FIXTURE_PATH"
    exit 1
  fi

  print_snapshot
  echo
  echo "Export complete. Commit and push this fixture for the other machine:"
  echo "  git add $(realpath --relative-to="$SCRIPT_DIR" "$FIXTURE_PATH" 2>/dev/null || echo "$FIXTURE_PATH")"
  echo "  git commit -m \"Add core data fixture\""
  echo "  git push"
}

do_import() {
  if [[ ! -f "$FIXTURE_PATH" ]]; then
    echo "Error: fixture file not found: $FIXTURE_PATH"
    echo "On the source machine, run: ./replicate_core_data_to_repo.sh export"
    echo "Then commit/push the fixture and git pull here."
    exit 1
  fi

  if [[ $SKIP_MIGRATE -eq 0 ]]; then
    echo "Running migrations..."
    (cd "$SCRIPT_DIR" && "$PYTHON_BIN" "$MANAGE_PATH" migrate --noinput)
  else
    echo "Skipping migrate (--skip-migrate)."
  fi

  if [[ $KEEP_EXISTING -eq 0 ]]; then
    confirm_import_delete
    echo "Clearing existing core data (core.User cascade delete)..."
    (cd "$SCRIPT_DIR" && "$PYTHON_BIN" "$MANAGE_PATH" shell -c "from core.models import User; deleted, _ = User.objects.all().delete(); print('Deleted objects:', deleted)")
  else
    echo "Keeping existing rows (--keep-existing)."
  fi

  echo "Loading fixture..."
  (cd "$SCRIPT_DIR" && "$PYTHON_BIN" "$MANAGE_PATH" loaddata "$FIXTURE_PATH")

  print_snapshot
  echo "Import complete."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    export|import|status)
      MODE="$1"
      shift
      ;;
    --fixture=*)
      FIXTURE_PATH="$(abs_path "${1#*=}")"
      shift
      ;;
    --fixture)
      FIXTURE_PATH="$(abs_path "${2:-}")"
      shift 2
      ;;
    --python=*)
      PYTHON_BIN="${1#*=}"
      shift
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --manage=*)
      MANAGE_PATH="$(abs_path "${1#*=}")"
      shift
      ;;
    --manage)
      MANAGE_PATH="$(abs_path "${2:-}")"
      shift 2
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --skip-migrate)
      SKIP_MIGRATE=1
      shift
      ;;
    --keep-existing|--no-delete)
      KEEP_EXISTING=1
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Unknown argument: $1"
      echo
      usage
      exit 1
      ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: python executable not found: $PYTHON_BIN"
  exit 1
fi

if [[ ! -f "$MANAGE_PATH" ]]; then
  echo "Error: manage.py not found: $MANAGE_PATH"
  exit 1
fi

if [[ "$MODE" == "status" ]]; then
  echo "Script directory: $SCRIPT_DIR"
  echo "manage.py: $MANAGE_PATH"
  echo "fixture: $FIXTURE_PATH"
  if [[ -f "$FIXTURE_PATH" ]]; then
    echo "fixture exists: yes"
  else
    echo "fixture exists: no"
  fi
  print_snapshot
  exit 0
fi

if [[ "$MODE" == "export" ]]; then
  do_export
  exit 0
fi

do_import
