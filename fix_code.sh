#!/bin/bash


SUDO_PASSWORD="debajeet"

MODEL="gpt-4o"
MAX_RETRIES=3
LOG_FILE="$HOME/.autoedit_strategy.log"

if [ $# -eq 0 ]; then
  echo "Usage: autoedit_fix.sh <command>"
  exit 1
fi

CMD="$*"
RETRY=0
OS=$(uname)

while [ "$RETRY" -lt "$MAX_RETRIES" ]; do
  echo "➡️ Running: $CMD"
  OUTPUT=$(bash -c "$CMD" 2>&1)
  STATUS=$?

  if [ "$STATUS" -eq 0 ]; then
    echo "✅ Success: $CMD"
    echo "====== $(date) ======" >> "$LOG_FILE"
    echo "✅ $CMD" >> "$LOG_FILE"
    exit 0
  fi

  echo "❌ Failed. Asking GPT to fix or patch a file..."

  GPT_RESPONSE=$(openai api chat.completions.create \
    -m "$MODEL" \
    -g user "You're a terminal assistant on $OS. The user ran:\n\n$CMD\n\nIt failed with:\n$OUTPUT\n\nIf a code fix is needed, respond with:\nCOMMAND: <fixed command>\nSTRATEGY: <short explanation>\nFILE_CHANGE: <file path>\nPATCH:\n<updated content of file>")

  FIXED_CMD=$(echo "$GPT_RESPONSE" | awk -F'COMMAND: ' '/COMMAND:/ {print $2; exit}' | xargs)
  STRATEGY=$(echo "$GPT_RESPONSE" | awk -F'STRATEGY: ' '/STRATEGY:/ {print $2; exit}' | xargs)
  FILE=$(echo "$GPT_RESPONSE" | awk -F'FILE_CHANGE: ' '/FILE_CHANGE:/ {print $2; exit}' | xargs)

  if [ -z "$FIXED_CMD" ]; then
    echo "💬 GPT gave no valid fix."
    echo "$GPT_RESPONSE"
    exit 1
  fi

  echo "🛠️ Fix: $FIXED_CMD"
  echo "📘 Strategy: $STRATEGY"

  {
    echo "====== $(date) ======"
    echo "❌ Original: $CMD"
    echo "Error: $OUTPUT"
    echo "✅ Fix: $FIXED_CMD"
    echo "📘 Strategy: $STRATEGY"
  } >> "$LOG_FILE"

  # If a file needs to be changed, apply patch
  if [ -n "$FILE" ]; then
    PATCH_CONTENT=$(echo "$GPT_RESPONSE" | awk '/PATCH:/ {found=1; next} found {print}' | sed '/^$/q')
    echo "📄 GPT suggests updating $FILE"
    echo "$PATCH_CONTENT" > "$FILE"

    echo "💾 Overwrote $FILE with GPT patch" >> "$LOG_FILE"
  fi

  CMD="$FIXED_CMD"
  ((RETRY++))
done

echo "⚠️ Max retries ($MAX_RETRIES) reached."
