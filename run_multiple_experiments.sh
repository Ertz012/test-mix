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
for i in {1..9}
do
    echo "Starte Durchlauf Nr. $i von 9..."

    # Erster Befehl (Run Series High Noise)
    sudo $PYTHON_EXEC tools/run_series.py --experiments config/experiments_high_noise.json

    # Zweiter Befehl (Launch No Noise)
    sudo $PYTHON_EXEC tools/launch_no_noise.py

    echo "Durchlauf $i beendet."
    echo "---------------------------"
done

echo "Alle 9 Durchläufe wurden abgeschlossen."
echo "---------------------------"
echo "Starte automatische Analyse (kann abgebrochen und später fortgesetzt werden)..."

# Analyse mit 4 Workern starten
# Wir nutzen hier keinen 'sudo' für die Analyse, es sei denn es ist nötig für Dateirechte.
# Da die Logs mit sudo erstellt wurden, gehören sie root. Wir brauchen also sudo zum Lesen/Schreiben der Ergebnisse.
sudo $PYTHON_EXEC tools/analysis/run_analysis_pipeline.py logs --workers 4

echo "Job erledigt."