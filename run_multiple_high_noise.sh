#!/bin/bash

# Pfad zum Python-Interpreter im Virtual Environment
# BITTE PRÜFEN: Ist dies der korrekte Pfad auf dem Remote-System?
# Wir nutzen den absoluten Pfad, damit 'sudo' die richtige Umgebung nutzt.
VENV_PATH="$HOME/venv-mininet"
PYTHON_EXEC="$VENV_PATH/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "ACHTUNG: Virtual Environment nicht gefunden unter $VENV_PATH"
    echo "Falle zurück auf System-Python (kann zu Fehlern führen, wenn Abhängigkeiten fehlen)..."
    PYTHON_EXEC="python3"
else
    echo "Nutze Virtual Environment: $PYTHON_EXEC"
fi

# Schleife von 1 bis 9
for i in {1..5}
do
    echo "Starte Durchlauf Nr. $i von 9..."

    # Erster Befehl (Run Series High Noise)
    sudo $PYTHON_EXEC tools/run_series.py --experiments config/experiments_high_noise.json

    # Zweiter Befehl (Launch No Noise)
    #sudo $PYTHON_EXEC tools/launch_no_noise.py

    echo "Durchlauf $i beendet."
    echo "---------------------------"
done

echo "Alle 9 Durchläufe wurden abgeschlossen."
echo "---------------------------"
echo "Job erledigt."
