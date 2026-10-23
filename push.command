#!/bin/bash
# Double-click in Finder (or run ./push.command) to commit and push everything.
cd "$(dirname "$0")" || exit 1

read -r -p "Commit message: " message
if [ -z "$message" ]; then
    message="$(date +%Y%m%d-%H%M)"
    echo "Empty message, using: $message"
fi

git add -A
if git diff --cached --quiet; then
    echo "Nothing new to commit."
else
    git commit -m "$message" || exit 1
fi
git push -u origin main

echo
read -r -p "Done. Press Enter to close..."
