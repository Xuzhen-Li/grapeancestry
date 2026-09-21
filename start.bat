@echo off
REM GrapeAncestry v1.0.0 — NEVER docker push the fat image (panel inside).
REM Prefer start.sh on macOS/Linux/Colima (sets --user host uid for bind mounts).
setlocal
cd /d "%~dp0"

if not exist input mkdir input
if not exist output mkdir output
if not exist settings mkdir settings
REM world-writable mounts so container can write auth.json / reports
icacls input /grant Everyone:(OI)(CI)F >nul 2>&1
icacls output /grant Everyone:(OI)(CI)F >nul 2>&1
icacls settings /grant Everyone:(OI)(CI)F >nul 2>&1

set IMAGE=grapeancestry:1.0.0
set NAME=grapeancestry
set TAR=grapeancestry-v1.0.0-amd64.tar
if "%ALLOW_INCOMPLETE%"=="" set ALLOW_INCOMPLETE=0

where docker >nul 2>&1
if errorlevel 1 (
  echo STOP: Docker is required. Install Docker Desktop and retry.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo STOP: Docker is not running. Start Docker Desktop and retry.
  exit /b 1
)

docker image inspect %IMAGE% >nul 2>&1
if errorlevel 1 (
  if exist "%TAR%" (
    echo Loading %TAR% ...
    docker load -i "%TAR%"
    docker image inspect %IMAGE% >nul 2>&1
    if errorlevel 1 (
      echo STOP: Loaded tar but tag %IMAGE% is missing.
      exit /b 1
    )
  ) else (
    echo Image %IMAGE% not found and %TAR% is missing.
    echo A docs-only GitHub clone cannot produce a working fat image.
    if not "%ALLOW_INCOMPLETE%"=="1" (
      echo STOP: Refusing incomplete build. Place %TAR% next to this script, or set ALLOW_INCOMPLETE=1.
      exit /b 1
    )
    if not exist Dockerfile (
      echo STOP: No Dockerfile and no tar.
      exit /b 1
    )
    echo ALLOW_INCOMPLETE=1 — building incomplete image ...
    docker build --platform linux/amd64 -t %IMAGE% .
    if errorlevel 1 (
      echo STOP: docker build failed.
      exit /b 1
    )
    docker image inspect %IMAGE% >nul 2>&1
    if errorlevel 1 (
      echo STOP: docker build did not produce tag %IMAGE%.
      exit /b 1
    )
  )
)

docker rm -f %NAME% >nul 2>&1
echo Starting %NAME% on :8501 and :8502 ...
echo NEVER docker push %IMAGE%.
REM Docker Desktop on Windows usually maps binds as writable; HOME=/tmp avoids writing under /home/mambauser.
docker run -d --name %NAME% -e HOME=/tmp -p 8501:8501 -p 8502:8502 -v "%cd%\input:/input" -v "%cd%\output:/output" -v "%cd%\settings:/settings" %IMAGE%
if errorlevel 1 (
  echo STOP: docker run failed.
  exit /b 1
)
echo UI:     http://127.0.0.1:8501
echo Report: http://127.0.0.1:8502
start http://127.0.0.1:8501
