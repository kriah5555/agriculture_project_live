#!/bin/bash

# Required for psycopg2 to be installed properly

echo "Checking requirements"
required_packages=(python3-dev libpq-dev build-essential python3-venv)

for pkg in "${required_packages[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        echo "Installing $pkg..."
        sudo apt install -y "$pkg"
    fi
done

echo "Installing packages from requirements.txt"
pip install -r requirements.txt
echo "Done"