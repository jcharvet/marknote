#!/bin/bash
sudo apt-get update
sudo apt-get install libxcb-cursor0 libgl1 libegl1
set -e

# Step 1: Detect platform and required venv activate script
OS_TYPE="$(uname -s)"
if [[ "$OS_TYPE" == "Linux" || "$OS_TYPE" == "Darwin" ]]; then
    VENV_ACTIVATE=".venv/bin/activate"
    VENV_TYPE="unix"
else
    VENV_ACTIVATE=".venv/Scripts/activate"
    VENV_TYPE="win"
fi

# Step 2: Check if correct venv exists; if not, recreate it
RECREATE_VENV=0
if [ ! -d ".venv" ]; then
    echo "No .venv found. Creating virtual environment..."
    RECREATE_VENV=1
elif [ "$VENV_TYPE" = "unix" ] && [ ! -f ".venv/bin/activate" ]; then
    echo "Existing .venv is not compatible with Linux/macOS. Recreating..."
    rm -rf .venv
    RECREATE_VENV=1
elif [ "$VENV_TYPE" = "win" ] && [ ! -f ".venv/Scripts/activate" ]; then
    echo "Existing .venv is not compatible with Windows. Recreating..."
    rm -rf .venv
    RECREATE_VENV=1
fi

if [ $RECREATE_VENV -eq 1 ]; then
    python3 -m venv .venv
    VENV_STATUS=$?
    if [ $VENV_STATUS -ne 0 ]; then
        echo "Failed to create virtual environment."
        echo "If you see a message about 'ensurepip' or missing 'venv', try: sudo apt install python3-venv"
        exit 1
    fi
fi

# Step 3: Activate the correct venv
if [ -f "$VENV_ACTIVATE" ]; then
    echo "Activating virtual environment ($VENV_ACTIVATE)..."
    source "$VENV_ACTIVATE"
else
    echo "Could not find a valid venv activate script ($VENV_ACTIVATE). Aborting."
    echo "Check if venv was created correctly and if you have permissions."
    exit 1
fi

# Step 3: Install dependencies if needed
if [ -f requirements.txt ]; then
    if [ ! -f .venv/.deps_installed ]; then
        echo "No previous dependency install detected. Installing all dependencies..."
        python3 -m pip install --upgrade pip
        python3 -m pip install -r requirements.txt || { echo "Dependency installation failed."; exit 1; }
        touch .venv/.deps_installed
    else
        REQTIME=$(stat -c %Y requirements.txt)
        INSTIME=$(stat -c %Y .venv/.deps_installed)
        if [ "$REQTIME" -gt "$INSTIME" ]; then
            echo "requirements.txt has changed. Updating dependencies..."
            python3 -m pip install --upgrade pip
            python3 -m pip install -r requirements.txt || { echo "Dependency installation failed."; exit 1; }
            touch .venv/.deps_installed
        else
            echo "Dependencies are up to date."
        fi
    fi
else
    echo "No requirements.txt found."
fi

# Step 4: Check for required Qt system libraries on Linux
if [[ "$OS_TYPE" == "Linux" ]]; then
    # Define package alternatives for modern and legacy distros
    QT_LIBS=(
        libxcb-cursor0
        libxcb-xinerama0
        libxcb-xinput0
        libxcb-icccm4
        libxcb-image0
        libxcb-keysyms1
        libxcb-render-util0
        mesa-utils
        libxkbcommon-x11-0
    )
    # Only check for modern Mesa packages on Linux Mint/Ubuntu
    GL_LIB="libgl1"
    EGL_LIB="libegl1"
    if ! apt-cache policy "$GL_LIB" | grep -q 'Candidate: (none)'; then
        QT_LIBS+=("$GL_LIB")
    fi
    if ! apt-cache policy "$EGL_LIB" | grep -q 'Candidate: (none)'; then
        QT_LIBS+=("$EGL_LIB")
    fi

    MISSING_LIBS=""
    for LIB in "${QT_LIBS[@]}"; do
        # Only check non-empty, valid package names (alphanumeric, dash, underscore, dot, plus)
        if [[ -n "$LIB" && "$LIB" =~ ^[a-zA-Z0-9._+-]+$ ]]; then
            if ! dpkg -s "$LIB" >/dev/null 2>&1; then
                MISSING_LIBS+="$LIB "
            fi
        fi
    done
    if [ -n "$MISSING_LIBS" ]; then
        echo -e "\n[ERROR] Missing required Qt system libraries: $MISSING_LIBS"
        echo "Please install them with:"
        echo "  sudo apt-get install $MISSING_LIBS"
        echo "After installing, re-run this script."
        exit 1
    fi
fi

# Step 5: Run the app
python3 main.py
