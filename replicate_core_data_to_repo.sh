#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Replicate core app data from this repository into another repository.

Usage:
  ./replicate_core_data_to_repo.sh --target-repo /path/to/target/repo [options]

  ./replicate_core_data_to_repo.sh /path/to/target/repo [options]

  ./replicate_core_data_to_repo.sh

Options:
  --target-repo PATH      Destination repository path.
  --source-repo PATH      Source repository path (default: script directory).
  --python BIN            Python executable (default: python).
  --source-manage PATH    Source manage.py relative to source repo (default: manage.py).
  --target-manage PATH    Target manage.py relative to target repo (default: manage.py).
  --fixture PATH          Fixture output file path.
                          Default: /tmp/sensore_core_data_<timestamp>.json
  --keep-target-data      Keep existing target data (skip delete). Import may fail on conflicts.
  --skip-migrate          Skip target migrate step.
  --forget-target         Remove saved default target path and exit.
  --yes                   Skip confirmation prompt when deleting target data.
  --help                  Show this help.

Notes:
- This script expects compatible Django models in both repos.
- By default, it deletes target core.User rows before import (cascades dependent core data).
- Run this from an activated virtual environment that can run both repositories.
- If target path is omitted in an interactive shell, the script prompts for it.
- Target path is saved to .replicate_target_repo for future single-command runs.
EOF
}

SOURCE_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_REPO=""
PYTHON_BIN="python"
SOURCE_MANAGE_REL="manage.py"
TARGET_MANAGE_REL="manage.py"
FIXTURE_PATH="/tmp/sensore_core_data_$(date +%Y%m%d_%H%M%S).json"
KEEP_TARGET_DATA=0
SKIP_MIGRATE=0
ASSUME_YES=0
FORGET_TARGET=0
TARGET_FROM_CACHE=0
TARGET_CACHE_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-repo=*)
      TARGET_REPO="${1#*=}"
      shift
      ;;
    --target-repo)
      TARGET_REPO="${2:-}"
      shift 2
      ;;
    --source-repo=*)
      SOURCE_REPO="${1#*=}"
      shift
      ;;
    --source-repo)
      SOURCE_REPO="${2:-}"
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
    --source-manage=*)
      SOURCE_MANAGE_REL="${1#*=}"
      shift
      ;;
    --source-manage)
      SOURCE_MANAGE_REL="${2:-}"
      shift 2
      ;;
    --target-manage=*)
      TARGET_MANAGE_REL="${1#*=}"
      shift
      ;;
    --target-manage)
      TARGET_MANAGE_REL="${2:-}"
      shift 2
      ;;
    --fixture=*)
      FIXTURE_PATH="${1#*=}"
      shift
      ;;
    --fixture)
      FIXTURE_PATH="${2:-}"
      shift 2
      ;;
    --keep-target-data)
      KEEP_TARGET_DATA=1
      shift
      ;;
    --skip-migrate)
      SKIP_MIGRATE=1
      shift
      ;;
    --forget-target)
      FORGET_TARGET=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
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
    -*)
      echo "Unknown argument: $1"
      echo
      usage
      exit 1
      ;;
    *)
      if [[ -z "$TARGET_REPO" ]]; then
        TARGET_REPO="$1"
      else
        echo "Unexpected positional argument: $1"
        echo
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

TARGET_CACHE_FILE="$SOURCE_REPO/.replicate_target_repo"

if [[ $FORGET_TARGET -eq 1 ]]; then
  if [[ -f "$TARGET_CACHE_FILE" ]]; then
    rm -f "$TARGET_CACHE_FILE"
    echo "Removed saved target path: $TARGET_CACHE_FILE"
  else
    echo "No saved target path found."
  fi
  exit 0
fi

if [[ -z "$TARGET_REPO" && -f "$TARGET_CACHE_FILE" ]]; then
  TARGET_REPO="$(head -n 1 "$TARGET_CACHE_FILE" | tr -d '\r' | sed 's/[[:space:]]*$//')"
  if [[ -n "$TARGET_REPO" ]]; then
    TARGET_FROM_CACHE=1
    echo "Using saved target repo: $TARGET_REPO"
  fi
fi

if [[ -z "$TARGET_REPO" ]]; then
  if [[ -t 0 ]]; then
    echo "No target repository path provided."
    read -r -p "Enter target repo path: " TARGET_REPO
  fi
fi

if [[ -z "$TARGET_REPO" ]]; then
  echo "Error: target repository path is required."
  echo "Example: ./replicate_core_data_to_repo.sh --target-repo /path/to/target/repo"
  echo "Tip: once you provide a target, it is saved and future runs need no arguments."
  echo
  usage
  exit 1
fi

if [[ ! -d "$SOURCE_REPO" ]]; then
  echo "Error: source repo path does not exist: $SOURCE_REPO"
  exit 1
fi

if [[ ! -d "$TARGET_REPO" ]]; then
  echo "Error: target repo path does not exist: $TARGET_REPO"
  if [[ $TARGET_FROM_CACHE -eq 1 ]]; then
    echo "The saved target path is stale. Reset it with: ./replicate_core_data_to_repo.sh --forget-target"
  fi
  exit 1
fi

SOURCE_REPO="$(cd "$SOURCE_REPO" && pwd)"
TARGET_REPO="$(cd "$TARGET_REPO" && pwd)"

if [[ "$TARGET_REPO" == "$SOURCE_REPO" ]]; then
  echo "Error: target repo cannot be the same as source repo."
  exit 1
fi

printf '%s\n' "$TARGET_REPO" > "$TARGET_CACHE_FILE"
echo "Saved default target repo to $TARGET_CACHE_FILE"

SOURCE_MANAGE_PATH="$SOURCE_REPO/$SOURCE_MANAGE_REL"
TARGET_MANAGE_PATH="$TARGET_REPO/$TARGET_MANAGE_REL"

if [[ ! -f "$SOURCE_MANAGE_PATH" ]]; then
  echo "Error: source manage.py not found at $SOURCE_MANAGE_PATH"
  exit 1
fi

if [[ ! -f "$TARGET_MANAGE_PATH" ]]; then
  echo "Error: target manage.py not found at $TARGET_MANAGE_PATH"
  exit 1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: python executable not found: $PYTHON_BIN"
  exit 1
fi

mkdir -p "$(dirname "$FIXTURE_PATH")"

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

echo "Step 1/5: Exporting source data to fixture..."
(
  cd "$SOURCE_REPO"
  "$PYTHON_BIN" "$SOURCE_MANAGE_PATH" dumpdata "${MODELS[@]}" --indent 2 --output "$FIXTURE_PATH"
)

if [[ ! -s "$FIXTURE_PATH" ]]; then
  echo "Error: fixture file was not created or is empty: $FIXTURE_PATH"
  exit 1
fi

echo "Fixture created: $FIXTURE_PATH"

echo "Step 2/5: Source snapshot"
(
  cd "$SOURCE_REPO"
  "$PYTHON_BIN" "$SOURCE_MANAGE_PATH" shell -c "$COUNT_SNIPPET"
)

if [[ $SKIP_MIGRATE -eq 0 ]]; then
  echo "Step 3/5: Running target migrations..."
  (
    cd "$TARGET_REPO"
    "$PYTHON_BIN" "$TARGET_MANAGE_PATH" migrate --noinput
  )
else
  echo "Step 3/5: Skipping target migrations (--skip-migrate)"
fi

if [[ $KEEP_TARGET_DATA -eq 0 ]]; then
  if [[ $ASSUME_YES -eq 0 ]]; then
    echo
    echo "About to delete all target core.User rows before importing data."
    echo "Target repo: $TARGET_REPO"
    read -r -p "Continue? [y/N]: " reply
    if [[ "${reply,,}" != "y" ]]; then
      echo "Aborted by user."
      exit 1
    fi
  fi

  echo "Step 4/5: Clearing target data (core.User cascade delete)..."
  (
    cd "$TARGET_REPO"
    "$PYTHON_BIN" "$TARGET_MANAGE_PATH" shell -c "from core.models import User; deleted, _ = User.objects.all().delete(); print('Deleted objects:', deleted)"
  )
else
  echo "Step 4/5: Keeping existing target data (--keep-target-data)"
fi

echo "Step 5/5: Loading fixture into target repo..."
(
  cd "$TARGET_REPO"
  "$PYTHON_BIN" "$TARGET_MANAGE_PATH" loaddata "$FIXTURE_PATH"
)

echo "Target snapshot after import:"
(
  cd "$TARGET_REPO"
  "$PYTHON_BIN" "$TARGET_MANAGE_PATH" shell -c "$COUNT_SNIPPET"
)

echo

echo "Replication complete."
