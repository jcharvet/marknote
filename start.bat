@echo off

REM Always check for missing dependencies (e.g., Pillow) before running the app
REM If requirements.txt has changed or any dependency is missing, install/upgrade all

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate (
    echo Activating virtual environment...
    call .venv\Scripts\activate
) else (
    echo No .venv found. You may need to create one with: python -m venv .venv
)

REM Always check requirements.txt timestamp
set NEED_INSTALL=0
if exist requirements.txt (
    if not exist .venv\.deps_installed (
        set NEED_INSTALL=1
    ) else (
        for %%F in (requirements.txt) do set REQTIME=%%~tF
        for %%F in (.venv\.deps_installed) do set INSTIME=%%~tF
        if "%REQTIME%" GTR "%INSTIME%" (
            set NEED_INSTALL=1
        )
    )
) else (
    echo No requirements.txt found.
)

REM Check for Pillow (PIL) and set NEED_INSTALL=1 if missing
python -c "import PIL" 2>NUL
if errorlevel 1 (
    echo Pillow not found, will install dependencies...
    set NEED_INSTALL=1
)

if %NEED_INSTALL%==1 (
    echo Installing/updating dependencies...
    pip install -r requirements.txt
    echo. > .venv\.deps_installed
) else (
    echo Dependencies are up to date.
)

REM Run the app
python main.py
