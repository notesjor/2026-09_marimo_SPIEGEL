# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo>=0.24.0",
#     "plotly==7.0.0",
#     "polars==1.44.1",
#     "pyarrow==25.0.1",
#     "statsmodels==0.15.0",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    import marimo as mo
    import pandas as pd
    import polars as pl
    import plotly.express as px
    import urllib.request
    import pathlib
    import io

    # Speicherort abrufen
    loc = mo.notebook_location()

    # Prüfen, ob wir im Web (WASM) oder lokal (Path) sind
    is_wasm = sys.platform == "emscripten"

    if is_wasm: 
        # --- WASM / BROWSER MODUS ---    
        base_url = str(loc).rstrip("/")

        # Wörterbuch via HTTP laden
        dict_url = f"{base_url}/public/dict.tsv"
        dictionary = {}
        with urllib.request.urlopen(dict_url) as response:
            inhalt = response.read().decode('utf-8')
            for zeile in inhalt.splitlines():
                split = zeile.strip().split("\t")
                if len(split) == 2:
                    dictionary[split[0].strip()] = split[1].strip()

        # Daten via HTTP laden
        data_url = f"{base_url}/public/data.tsv"
        with urllib.request.urlopen(data_url) as response:
            csv_data = response.read()
            df = pl.read_csv(io.BytesIO(csv_data), separator="\t")

    else: 
        # --- LOKALER MODUS (Windows/Mac/Linux) ---    
        # Hier nutzen wir jetzt korrekt pathlib.Path statt nur Path
        base_path = pathlib.Path(loc)

        # Wörterbuch lokal laden
        dict_path = base_path / "public" / "dict.tsv"
        dictionary = {}
        with open(dict_path, "r", encoding="utf-8") as datei:
            for zeile in datei:
                split = zeile.strip().split("\t")
                if len(split) == 2:
                    dictionary[split[0].strip()] = split[1].strip()

        # Daten lokal laden
        data_path = base_path / "public" / "data.tsv"
        df = pl.read_csv(data_path, separator="\t")
    return df, dictionary, mo, pl, px


@app.cell
def _(mo):
    mo.md("""
    Eingabe der maskform - oder * (für alle)
    """)
    return


@app.cell
def _(mo):
    maskform_input = mo.ui.text(label="maskform:", debounce=True)
    maskform_input
    return (maskform_input,)


@app.cell
def _(dictionary, maskform_input, mo):
    mo.stop(not maskform_input.value, "Bitte geben Sie eine maskform ein und drücken Sie abschließend Enter.")

    if maskform_input.value == "*":
        q1 = list(dictionary.keys())
        q2 = list(dictionary.values())
    elif "," in maskform_input.value:
        q1 = [x.strip() for x in maskform_input.value.split(",")]
        q1clean = []
        for x in q1:
            x = x.strip()            
            if x not in dictionary:
                continue
            q1clean.append(x)
        q1 = q1clean
        q2 = [dictionary[x] for x in q1]
    else:
        q1 = []
        q1.append(maskform_input.value.strip())
        q2 = []
        q2.append(dictionary[maskform_input.value.strip()])

    print(f"q1 = {q1} / q2 = {q2}")
    return q1, q2


@app.cell
def _(maskform_input, mo):
    mo.stop(not maskform_input.value)

    spiegel_select = mo.ui.dropdown(
        options=[
            "Bitte auswählen...",
            "Nur SPIEGEL",
            "Nur SPIEGEL-ONLINE",
            "SPIEGEL + SPIEGEL-Online",
        ],
        value="Bitte auswählen...",
        label="Auswahl:",
    )
    spiegel_select
    return (spiegel_select,)


@app.cell
def _(maskform_input, mo, q1):
    mo.stop(not maskform_input.value)

    checkbox = None
    if len(q1) < 10:
        checkbox = mo.ui.checkbox(label="Werte separieren?")

    checkbox
    return (checkbox,)


@app.cell
def _(checkbox):
    separate = False
    if checkbox != None:
        separate = checkbox.value
    return (separate,)


@app.cell
def _(df, maskform_input, mo, pl, px, q1, q2, separate, spiegel_select):
    mo.stop(not maskform_input.value)

    if spiegel_select.value == "Bitte auswählen...":
        mo.md("ℹ️ *Bitte treffen Sie eine Auswahl, um fortzufahren.*")
        mo.stop(spiegel_select.value)

    mo.md(f"🎉 Es wurde **{spiegel_select.value}** ausgewählt. Starte Verarbeitung...")
    qS = "S" if spiegel_select.value == "Nur SPIEGEL" else "SOL"

    if spiegel_select.value != "SPIEGEL + SPIEGEL-Online":
        df_filtered = df.filter(pl.col("Quelle") == qS)
    else:
        df_filtered = df

    if separate:
        tmp = (
        df_filtered.filter(pl.col("Wort").is_in(q1 + q2)))
    else:
        tmp = (
        df_filtered.filter(pl.col("Wort").is_in(q1 + q2))
            .with_columns(
                pl.when(pl.col("Wort").is_in(q1))
                .then(pl.lit("mask"))
                .otherwise(pl.lit("fem"))
                .alias("Wort")
            )
            .group_by(["Jahr", "Wort"])
            .agg(pl.sum("Frequenz"))
        )

    tmp_with_trend = (
        tmp.sort(["Wort", "Jahr"])
        .with_columns(
            pl.col("Frequenz")
            .rolling_mean(window_size=5, min_periods=1)
            .over("Wort")
            .alias("Frequenz_Trend")
        )
    )

    # erstelle einen Scatter-Plot mit Plotly Express - x = Jahr, y = Frequenz, Farbe = Wort - ergänze eine Trendlinie über 5 Jahre (gleitender Durchschnitt)
    fig = px.scatter(
        tmp_with_trend, 
        x="Jahr",
        y="Frequenz",
        color="Wort",
        color_discrete_map={"mask": "#0e36c7", "fem": "#c91026"},
        title=f"Frequenzverlauf",
        labels={"Jahr": "Jahr", "Frequenz": "Frequenz (ppm)", "Wort": "Wort"},
    )

    fig_trend = px.line(
        tmp_with_trend,
        x="Jahr",
        y="Frequenz_Trend",
        color="Wort",
        color_discrete_map={"mask": "#4d70f0", "fem": "#e04c5e"},
    )
    fig_trend.update_traces(line=dict(width=3, dash="solid"), opacity=0.8)

    fig.add_traces(fig_trend.data)

    fig
    return


if __name__ == "__main__":
    app.run()
