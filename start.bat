@echo off
REM GrapeAncestry v1.0.0 launcher — same contract as start.sh
setlocal
cd /d "%~dp0"

if not exist input mkdir input
if not exist output mkdir output
if not exist settings mkdir settings

set IMAGE=grapeancestry:1.0.0
set NAME=grapeancestry
set TAR=grapeancestry-v1.0.0-amd64.tar

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker is required. Install Docker Desktop and retry.
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker is not running. Start Docker Desktop and retry.
  exit /b 1
)

docker image inspect %IMAGE% >nul 2>&1
if errorlevel 1 (
  if exist "%TAR%" (
    echo Loading %TAR% ...
    docker load -i "%TAR%"
  ) else (
    echo Image %IMAGE% not found and %TAR% is missing.
    echo A docs-only clone cannot produce a working fat image. Place %TAR% here.
    if exist Dockerfile (
      echo Trying docker build --platform linux/amd64 ...
      docker build --platform linux/amd64 -t %IMAGE% .
    ) else (
      exit /b 1
    )
  )
)

docker rm -f %NAME% >nul 2>&1

echo Starting %NAME% on :8501 and :8502 ...
docker run -d --name %NAME% -p 8501:8501 -p 8502:8502 -v "%cd%\input:/input" -v "%cd%\output:/output" -v "%cd%\settings:/settings" %IMAGE%

echo UI:     http://127.0.0.1:8501
echo Report: http://127.0.0.1:8502
start http://127.0.0.1:8501
