@echo off

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate (
    echo Activating virtual environment...
    call .venv\Scripts\activate
) else (
    echo No .venv found. You may need to create one with: python -m venv .venv
)

REM Install dependencies only if requirements.txt is newer than .venv\.deps_installed or if .deps_installed does not exist
if exist requirements.txt (
    if not exist .venv\.deps_installed (
        echo No previous dependency install detected. Installing all dependencies...
        pip install -r requirements.txt
        echo. > .venv\.deps_installed
    ) else (
        for %%F in (requirements.txt) do set REQTIME=%%~tF
        for %%F in (.venv\.deps_installed) do set INSTIME=%%~tF
        if "%REQTIME%" GTR "%INSTIME%" (
            echo requirements.txt has changed. Updating dependencies...
            pip install -r requirements.txt
            echo. > .venv\.deps_installed
        ) else (
            echo Dependencies are up to date.
        )
    )
) else (
    echo No requirements.txt found.
)

REM Run the app
python main.py
