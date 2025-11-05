# -*- coding: utf-8 -*-
import streamlit as st
import geopandas as gpd
import pyogrio
import folium
from streamlit_folium import st_folium
import tempfile
import os
import pandas as pd
import requests
import time

# ===============================================================
# CONFIGURAÇÃO BÁSICA
# ===============================================================
st.set_page_config(page_title="Interface Web - Loteamentos aprovados via REURB em Palmas/TO", layout="wide", page_icon="🌍")

# CSS customizado
st.markdown("""
    <style>
        html, body {
            margin: 0 !important;
            padding: 0 !important;
            height: 100% !important;
            overflow-y: scroll !important;  /* 🔹 garante rolagem e topo imediato */
        }

        .block-container {
            max-width: 1100px;
            margin: 0 auto !important;
            padding-top: 1rem !important;
            display: block !important;
            align-items: flex-start !important;  /* 🔹 evita centralização vertical */
            justify-content: flex-start !important;
        }

        /* Caixa de informações */
        .info-box {
            background-color: #F8F9F9;
            border: 1px solid #D5DBDB;
            border-radius: 10px;
            padding: 10px 20px;
            margin-top: 10px;
            font-family: Arial;
        }
        .info-box h4 {
            color: #1C2833;
            text-align: center;
            margin-bottom: 10px;
        }
        .info-box p {
            text-align: center;
            margin: 3px 0;
            font-size: 13px;
        }

        /* Tabelas centralizadas */
        .stDataFrame {
            text-align: center !important;
        }
        div[data-testid="stDataFrame"] table td,
        div[data-testid="stDataFrame"] table th {
            text-align: center !important;
            white-space: nowrap !important;
        }
    </style>
""", unsafe_allow_html=True)


# ===============================================================
# LOGO CENTRALIZADA E TÍTULO PRINCIPAL
# ===============================================================
st.markdown(
    """
    <div style='text-align:center; margin-top:15px; margin-bottom:10px;'>
        <img src="https://i.imgur.com/fm0z11P.jpeg" alt="Logo REURB">
    </div>

    <h1 style='
        text-align:center;
        font-size:22px;
        margin-top:2px;      /* 🔹 reduz o espaço superior */
        margin-bottom:2px;   /* 🔹 reduz o espaço inferior */
        padding-top:2px;     /* 🔹 evita corte no topo */
    '>
        🌍 Loteamentos aprovados via REURB em Palmas/TO
    </h1>
        <h1 style='
        text-align:center;
        font-size:22px;
        margin-top:2px;      /* 🔹 reduz o espaço superior */
        margin-bottom:2px;   /* 🔹 reduz o espaço inferior */
        padding-top:2px;     /* 🔹 evita corte no topo */
    '>
        Interface Web
    </h1>
    """,
    unsafe_allow_html=True
)



# ===============================================================
# SELECTBOX COM FONTE 17px
# ===============================================================
st.markdown(
    """
    <style>
        label[data-testid="stWidgetLabel"] p {
            font-size:17px !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

opcao_loteamento = st.selectbox(
    "🏘️ Selecione o Loteamento para visualizar o mapa:",
    ["Loteamento Machado Oeste I", "Loteamento Lago Norte"]
)


# Define o link conforme a escolha
if opcao_loteamento == "Loteamento Machado Oeste I":
    drive_url = "https://drive.google.com/uc?export=download&id=1CQzRJFkjk-KqOApkBSIEA3y-J3dbOX-3"
else:
    drive_url = "https://drive.google.com/uc?export=download&id=1R_DUJH1mrm8YmsOlxOCbRvWlxOA-PNjZ"

try:
    # ===============================================================
    # DOWNLOAD DO ARQUIVO COM BARRA DE PROGRESSO
    # ===============================================================
    progress_text = st.empty()
    progress_bar = st.progress(0)

    for percent in range(0, 30, 5):
        time.sleep(0.05)
        progress_bar.progress(percent)
        progress_text.text(f"Baixando dados... {percent}%")

    response = requests.get(drive_url, allow_redirects=True, stream=True)

    if response.status_code != 200:
        st.error(f"Erro ao baixar os dados (status {response.status_code}). Verifique se o link é público.")
    else:
        total = int(response.headers.get('content-length', 0))
        downloaded = 0

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gpkg") as tmp:
            for data in response.iter_content(chunk_size=8192):
                downloaded += len(data)
                tmp.write(data)
                if total > 0:
                    progress = int(30 + (downloaded / total) * 70)
                    progress_bar.progress(min(progress, 100))
                    progress_text.text(f"Baixando dados... {progress}%")
            temp_path = tmp.name

        progress_bar.progress(100)
        progress_text.markdown(
            "<div style='color:#1E8449; text-align:left; font-weight:bold;'>"
            "✅ Dados baixados com sucesso!"
            "</div>",
            unsafe_allow_html=True
        )

        time.sleep(0.5)

        # 🔹 Limpa a barra e o texto após carregar
        progress_bar.empty()
        progress_text.empty()


        # ===============================================================
        # LISTAR E LER CAMADA LOTES
        # ===============================================================
        layers_info = pyogrio.list_layers(temp_path)
        layers = [info[0] for info in layers_info]
        selected_layer = next((lyr for lyr in layers if "lote" in lyr.lower()), None)

        # (Mensagens removidas — sem fundo colorido)
        gdf = gpd.read_file(temp_path, layer=selected_layer, engine="pyogrio")

        for col in gdf.columns:
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)

        crs_info = ""
        crs_reproj = ""
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
            crs_reproj = "♻️ Reprojetado para WGS84 (EPSG:4326)."

        st.success(f"✅ {len(gdf)} Lotes carregados.")


        # ===============================================================
        # MAPA INTERATIVO — COM TOOLTIP AO PASSAR O MOUSE (em uma linha)
        # ===============================================================
        if not gdf.empty and gdf.geometry.notna().any():
            centroid = gdf.geometry.centroid
            mean_lat = centroid.y.mean()
            mean_lon = centroid.x.mean()

            # Cria coluna combinada "Quadra X, Lote Y"
            gdf["Descricao"] = gdf.apply(
                lambda row: f"Quadra {row.get('Quadra', '')}, Lote {row.get('Lote', '')}", axis=1
            )

            m = folium.Map(location=[mean_lat, mean_lon], zoom_start=16)

            # GeoJson com tooltip formatado em uma linha
            geojson = folium.GeoJson(
                gdf,
                name="Lotes",
                style_function=lambda x: {
                    "fillColor": "#D5D8DC",
                    "color": "#424949",
                    "weight": 1.5,
                    "fillOpacity": 0.5,
                },
                highlight_function=lambda x: {
                    "fillColor": "#85C1E9",
                    "color": "#154360",
                    "weight": 3,
                    "fillOpacity": 0.7,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["Descricao"],  # usa a coluna combinada
                    labels=False,
                    sticky=False,
                    style=("background-color: white; color: #1B2631; font-size: 11px; font-family: Arial;"),
                ),
            )
            geojson.add_to(m)
            folium.LayerControl().add_to(m)

            # Exibe mapa e captura o clique
            st.markdown(
                f"<h4 style='text-align:center; color:#1C2833; font-size:22px;'>📍 {opcao_loteamento}</h4>",
                unsafe_allow_html=True
            )

            map_output = st_folium(
                m,
                width=950,
                height=500,
                returned_objects=["last_active_drawing"],
                key="mapa_lotes"
            )


            # ===============================================================
            # EXIBIR INFORMAÇÕES DA FEIÇÃO CLICADA
            # ===============================================================
            if map_output and map_output.get("last_active_drawing"):
                feature = map_output["last_active_drawing"]
                props = feature.get("properties", {})

                quadra = props.get("Quadra", "—")
                logradouro = props.get("Logradouro", "—")
                lote = props.get("Lote", "—")

                st.markdown(
                    f"""
                    <div class='info-box' style="font-size:18px; font-family:Arial;">
                        <h4 style="text-align:center; font-size:18px; margin-bottom:10px;">
                            🧾 Informações do Lote Selecionado
                        </h4>
                        <p style="text-align:left; margin:3px 0; font-size:16px;">
                            <b>Loteamento:</b> {opcao_loteamento}
                        </p>
                        <p style="text-align:left; margin:3px 0; font-size:16px;">
                            <b>Quadra:</b> {quadra}
                        </p>
                        <p style="text-align:left; margin:3px 0; font-size:16px;">
                            <b>Lote:</b> {lote}
                        </p>
                        <p style="text-align:left; margin:3px 0; font-size:16px;">
                            <b>Logradouro:</b> {logradouro}
                        <p style="text-align:left; margin:3px 0; font-size:16px;">
                            <b>Matrícula:</b> {logradouro}
                        </p>

                        
                        
                    </div>

                    """,
                    unsafe_allow_html=True
                )


        else:
            st.warning("A camada selecionada não possui geometria válida.")

        # ===============================================================
        # TABELA DE ATRIBUTOS
        # ===============================================================
        st.markdown(
            "<h3 style='font-size:22px; font-weight:normal;'>📋 Quadras e Lotes aprovados pela REURB.</h3>",
            unsafe_allow_html=True
        )

        campos_desejados = ["Quadra", "Logradouro", "Lote"]
        campos_existentes = [c for c in campos_desejados if c in gdf.columns]

        if campos_existentes:
            df_mostrar = gdf[campos_existentes].head(50)
            st.dataframe(df_mostrar, use_container_width=True)
        else:
            st.warning("Nenhum dos campos 'Quadra', 'Logradouro' ou 'Lote' foi encontrado nesta camada.")

    os.remove(temp_path)

except Exception as e:
    st.error(f"Erro: {e}")

# ===============================================================
# RODAPÉ
# ===============================================================
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div style="text-align:center; font-size:11px; color:#555;">
        {crs_reproj}
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div style="text-align:center; color:#523D35; margin-top:20px; font-size:12px;">
        Desenvolvido para apoio aos processos de Regularização Fundiária Urbana (REURB)
    </div>
    """,
    unsafe_allow_html=True
)
