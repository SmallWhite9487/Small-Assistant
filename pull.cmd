@echo off
cd /d "%~dp0"

echo Pulling latest changes...
git pull origin main --rebase

set /p msg="Please enter update info: "

git add .
git commit -m "%msg%"
git push

echo Done!
pause