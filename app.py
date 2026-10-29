"""
Painel "Desertos de atendimento" - Seguranca Publica (hackathon MVP).

Cruza a taxa de violencia contra a mulher por municipio de Sao Paulo
(ocorrencias por 100 mil mulheres) com a presenca de Delegacia de Defesa
da Mulher (DDM), destacando municipios com taxa ALTA e SEM DDM.

Fontes:
  - Populacao de mulheres por municipio: IBGE, Censo 2022 (API SIDRA, tab. 9514).
  - Malha municipal: IBGE, API de Malhas Territoriais v4.
  - Ocorrencias e presenca de DDM: SSP-SP, Portal da Transparencia (dados
    criminais), agregados por municipio neste projeto.

Privacidade: somente dados agregados por municipio. Sem dados individuais
e sem enderecos de delegacias ou de casas-abrigo.
"""
import json
import os
import sys

import pandas as pd
import streamlit as st

AQUI = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(AQUI, "data")

# Reaproveita a reconciliacao de nomes SSP<->IBGE do pacote de dados.
sys.path.insert(0, DATA)
from nomes import fingerprint  # noqa: E402

ARQ_POP = os.path.join(DATA, "populacao_mulheres_sp.csv")
ARQ_MALHA = os.path.join(DATA, "malha_sp.geojson")
ARQ_OCO = os.path.join(DATA, "ocorrencias_mulher_sp.csv")
ARQ_DDM = os.path.join(DATA, "delegacias_mulher_sp.csv")

st.set_page_config(page_title="Mapa da Violência Contra a Mulher - SP", layout="wide")

# Oculta APENAS o botao "Deploy". O menu dos tres pontinhos continua
# visivel, pois e nele que fica a opcao de tema claro/escuro (Settings).
st.markdown(
    """
    <style>
    [data-testid="stAppDeployButton"] {display: none;}
    .stDeployButton {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def carregar_populacao():
    df = pd.read_csv(ARQ_POP, dtype={"cod_mun": str})
    df["chave"] = df["municipio"].map(fingerprint)
    return df


@st.cache_data(show_spinner=False)
def carregar_malha():
    with open(ARQ_MALHA, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def carregar_ocorrencias():
    if not os.path.exists(ARQ_OCO):
        return None
    df = pd.read_csv(ARQ_OCO)
    df["chave"] = df["municipio"].map(fingerprint)
    return df


@st.cache_data(show_spinner=False)
def carregar_ddm():
    if not os.path.exists(ARQ_DDM):
        return None
    df = pd.read_csv(ARQ_DDM)
    df["chave"] = df["municipio"].map(fingerprint)
    return df


def construir_base(pop, oco, ddm, anos_sel, naturezas_sel):
    """Monta a tabela por municipio: ocorrencias, populacao, taxa e DDM."""
    base = pop[["cod_mun", "municipio", "pop_mulheres", "chave"]].copy()

    if oco is not None:
        f = oco[oco["ano"].isin(anos_sel)]
        if naturezas_sel:
            f = f[f["natureza"].isin(naturezas_sel)]
        agg = f.groupby("chave", as_index=False)["ocorrencias"].sum()
        base = base.merge(agg, on="chave", how="left")
    else:
        base["ocorrencias"] = pd.NA

    base["ocorrencias"] = pd.to_numeric(base.get("ocorrencias"), errors="coerce")

    if ddm is not None:
        base = base.merge(ddm[["chave", "tem_ddm"]], on="chave", how="left")
        base["tem_ddm"] = base["tem_ddm"].fillna(0).astype(int)
    else:
        base["tem_ddm"] = pd.NA

    base["taxa_100k"] = (base["ocorrencias"] / base["pop_mulheres"]) * 100_000
    base["taxa_100k"] = base["taxa_100k"].round(1)
    return base


# ---------------------------------------------------------------------------
# Cabecalho
# ---------------------------------------------------------------------------
st.title("Mapa da Violência Contra a Mulher")
st.caption(
    "Violencia contra a mulher por municipio de Sao Paulo (ocorrencias por "
    "100 mil mulheres) cruzada com a presenca de Delegacia de Defesa da Mulher (DDM)."
)

# Avisos de contexto e canais de ajuda sempre visiveis.
col_a, col_b = st.columns(2)
with col_a:
    st.error("**Ligue 180** - Central de Atendimento a Mulher (denuncia e orientacao, 24h, gratuito).")
with col_b:
    st.error("**Ligue 190** - Policia Militar, para emergencias e risco imediato.")

st.warning(
    "**Atencao a subnotificacao.** Os numeros refletem apenas ocorrencias "
    "**registradas** pela policia. Grande parte da violencia contra a mulher "
    "nao e denunciada, entao taxas baixas podem indicar subnotificacao, e nao "
    "ausencia de violencia. Use os dados como indicador, nao como medida exata."
)

# ---------------------------------------------------------------------------
# Carregamento
# ---------------------------------------------------------------------------
try:
    pop = carregar_populacao()
except FileNotFoundError:
    st.stop()

malha = carregar_malha() if os.path.exists(ARQ_MALHA) else None
oco = carregar_ocorrencias()
ddm = carregar_ddm()

if oco is None:
    st.info(
        "Dados de ocorrencias da SSP-SP ainda nao disponiveis em "
        "`data/ocorrencias_mulher_sp.csv`. Rode `python data/download_ocorrencias.py`. "
        "Exibindo apenas populacao e malha."
    )

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
st.sidebar.header("Filtros")

if oco is not None:
    anos = sorted(oco["ano"].unique().tolist())
    anos_sel = st.sidebar.multiselect("Ano", anos, default=anos)
    naturezas = sorted(oco["natureza"].unique().tolist())
    naturezas_sel = st.sidebar.multiselect(
        "Natureza (vazio = todas)", naturezas, default=[]
    )
else:
    anos_sel, naturezas_sel = [], []

base = construir_base(pop, oco, ddm, anos_sel, naturezas_sel)

limite = st.sidebar.slider(
    "Limite de taxa 'alta' (ocorrencias por 100 mil mulheres)",
    min_value=0,
    max_value=int(base["taxa_100k"].max()) if base["taxa_100k"].notna().any() else 100,
    value=int(base["taxa_100k"].median()) if base["taxa_100k"].notna().any() else 0,
    help="Municipios acima deste limite sao considerados de taxa alta.",
)

pop_min = st.sidebar.number_input(
    "Populacao minima de mulheres (reduz ruido de municipios pequenos)",
    min_value=0, value=0, step=1000,
)

# ---------------------------------------------------------------------------
# Desertos de atendimento: taxa alta E sem DDM
# ---------------------------------------------------------------------------
st.subheader("Desertos de atendimento")

tem_dados = oco is not None and ddm is not None and base["taxa_100k"].notna().any()

if tem_dados:
    desertos = base[
        (base["taxa_100k"] >= limite)
        & (base["tem_ddm"] == 0)
        & (base["pop_mulheres"] >= pop_min)
    ].sort_values("taxa_100k", ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric("Municipios analisados", f"{base['taxa_100k'].notna().sum()}")
    c2.metric("Municipios sem DDM", f"{int((base['tem_ddm'] == 0).sum())}")
    c3.metric("Desertos (taxa alta + sem DDM)", f"{len(desertos)}")

    st.markdown(
        "Municipios com **taxa de violencia igual ou acima do limite** e "
        "**sem Delegacia de Defesa da Mulher** atuando no municipio:"
    )
    st.dataframe(
        desertos[["municipio", "pop_mulheres", "ocorrencias", "taxa_100k"]]
        .rename(columns={
            "municipio": "Municipio",
            "pop_mulheres": "Mulheres (Censo 2022)",
            "ocorrencias": "Ocorrencias",
            "taxa_100k": "Taxa / 100 mil",
        }),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "A identificacao de desertos precisa dos dados de ocorrencias e de DDM "
        "da SSP-SP. Rode o script de download para habilitar esta secao."
    )

# ---------------------------------------------------------------------------
# Mapa
# ---------------------------------------------------------------------------
st.subheader("Mapa - taxa por municipio")

if malha is not None and base["taxa_100k"].notna().any():
    import pydeck as pdk

    taxa_por_cod = dict(zip(base["cod_mun"].astype(str), base["taxa_100k"]))
    ddm_por_cod = dict(zip(base["cod_mun"].astype(str), base["tem_ddm"]))
    nome_por_cod = dict(zip(base["cod_mun"].astype(str), base["municipio"]))

    tmax = base["taxa_100k"].max() or 1.0
    feats = []
    for ft in malha["features"]:
        cod = str(ft["properties"].get("codarea", "")).strip()
        taxa = taxa_por_cod.get(cod)
        tem = ddm_por_cod.get(cod)
        props = dict(ft["properties"])
        props["municipio"] = nome_por_cod.get(cod, cod)
        props["taxa"] = None if pd.isna(taxa) else float(taxa)
        props["ddm"] = "Sim" if tem == 1 else ("Nao" if tem == 0 else "?")
        # Cor: vermelho intenso para taxa alta; cinza se sem dado.
        if taxa is None or pd.isna(taxa):
            props["cor"] = [200, 200, 200]
        else:
            inten = min(1.0, float(taxa) / float(tmax))
            props["cor"] = [230, int(120 * (1 - inten)), int(120 * (1 - inten))]
        feats.append({**ft, "properties": props})

    geo = {"type": "FeatureCollection", "features": feats}
    camada = pdk.Layer(
        "GeoJsonLayer",
        geo,
        pickable=True,
        stroked=True,
        filled=True,
        get_fill_color="properties.cor",
        get_line_color=[80, 80, 80],
        line_width_min_pixels=0.3,
    )
    view = pdk.ViewState(latitude=-22.5, longitude=-48.6, zoom=5.4)
    tooltip = {"text": "{municipio}\nTaxa/100 mil: {taxa}\nDDM: {ddm}"}
    st.pydeck_chart(pdk.Deck(layers=[camada], initial_view_state=view, tooltip=tooltip))
    st.caption("Tons mais escuros de vermelho = taxa mais alta. Cinza = sem dado de ocorrencia.")
else:
    st.info("Mapa disponivel quando houver malha municipal e dados de taxa.")

# ---------------------------------------------------------------------------
# Tabela completa
# ---------------------------------------------------------------------------
with st.expander("Ver todos os municipios"):
    st.dataframe(
        base[["municipio", "pop_mulheres", "ocorrencias", "taxa_100k", "tem_ddm"]]
        .rename(columns={
            "municipio": "Municipio",
            "pop_mulheres": "Mulheres (Censo 2022)",
            "ocorrencias": "Ocorrencias",
            "taxa_100k": "Taxa / 100 mil",
            "tem_ddm": "Tem DDM (1/0)",
        })
        .sort_values("Taxa / 100 mil", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "Dados agregados por municipio. Nao sao exibidos dados individuais nem "
    "enderecos de delegacias ou de casas-abrigo. Fontes: IBGE (Censo 2022, "
    "malhas) e SSP-SP (Portal da Transparencia)."
)
