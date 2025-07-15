import csv
import random

def generate_test_data(filename="test_meldungen.csv", count=100):
    """
    Generates a CSV file with sample SAP PM notification texts of varying quality.
    """
    
    # Templates for different quality levels
    templates = {
        "excellent": [
            "Pumpe {p_id} an Anlage {a_id} zeigte starke Vibrationen. Ursache: Lagerschaden antriebsseitig durch mangelnde Schmierung. Lager getauscht (Material: {m_id}), neu geschmiert. Probelauf über 4h war erfolgreich.",
            "Leckage am Flansch des Wärmetauschers WT-{wt_id}. Dichtung (Material: {m_id}) war porös und wurde ersetzt. Dichtheitsprüfung mit 10 bar bestanden. Anlage wieder in Betrieb.",
            "Motor M-{m_id} des Förderbands FB-{fb_id} überhitzt. Thermische Überlastung durch blockiertes Getriebe. Getriebe gereinigt und neu gefettet. Motor läuft wieder im normalen Temperaturbereich."
        ],
        "good": [
            "Ventil V-{v_id} schließt nicht vollständig. Spindel wurde nachgezogen und justiert. Ventil ist jetzt wieder dicht.",
            "SPS-Steuerung der Abfüllanlage A-{a_id} meldet Fehlercode {e_code}. Neustart der Steuerung hat das Problem behoben. Ursache unklar, Anlage zur Beobachtung.",
            "Filter F-{f_id} in der Hydraulikleitung verstopft. Filterelement wurde gereinigt und wieder eingesetzt. Druck wieder im Sollbereich."
        ],
        "medium": [
            "Pumpe {p_id} macht Geräusche. Wurde überprüft und repariert.",
            "Leck an Leitung L-{l_id}. Dichtung getauscht.",
            "Motor M-{m_id} läuft nicht. Elektriker hat es repariert.",
            "Anlage {a_id} steht. Problem behoben."
        ],
        "poor": [
            "Pumpe kaputt.",
            "Repariert.",
            "Fehler.",
            "Anlage steht.",
            "Ölverlust.",
            "Dichtung undicht."
        ],
        "realistic_messy": [
            "Dichtung an Pumpe P{p_id} leckt, getauscht. alles ok.",
            "Motor von Band {fb_id} zu heiss. neu gestartet.",
            "Vibration an A-{a_id}, lager wohl defekt. geprüft.",
            "Druckverlust an V{v_id}. scheint wieder zu gehen."
        ]
    }

    headers = ["id", "meldungstext"]
    rows = []

    for i in range(1, count + 1):
        quality = random.choices(list(templates.keys()), weights=[15, 30, 30, 15, 10], k=1)[0]
        template = random.choice(templates[quality])
        
        # Populate templates with random data
        text = template.format(
            p_id=random.randint(100, 999),
            a_id=random.choice(["A42", "B7", "C11"]),
            m_id=random.randint(100000, 999999),
            wt_id=random.randint(1, 20),
            fb_id=random.randint(1, 5),
            v_id=random.randint(10, 50),
            e_code=random.choice(["E-404", "E-501", "E-21B"]),
            l_id=random.randint(1, 100),
            f_id=random.randint(1, 100)
        )
        
        rows.append({"id": i, "meldungstext": text})

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Successfully created '{filename}' with {len(rows)} entries.")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

if __name__ == "__main__":
    # Generate only 5 test messages
    generate_test_data(count=5)
