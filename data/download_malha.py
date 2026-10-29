"""
Baixa a malha municipal do estado de Sao Paulo (UF 35) e salva como GeoJSON
para uso no painel.

Fonte principal: API de Malhas Territoriais do IBGE (servicodados v4), que
retorna GeoJSON com um poligono por municipio (propriedade 'codarea' = codigo
do municipio de 7 digitos). E a mesma base geografica usada pela geobr.

Fallback: biblioteca geobr (read_municipality), caso a API esteja indisponivel.

Saida: data/malha_sp.geojson  (Feature.properties.codarea = cod_mun)

Nao inventa dados: se ambos falharem, imprime a URL/erro e encerra != 0.
"""
import os
import sys
import json

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "malha_sp.geojson")

URL_IBGE = (
    "https://servicodados.ibge.gov.br/api/v4/malhas/estados/35"
    "?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=intermediaria"
)


def via_ibge() -> bool:
    print(f"[malha] baixando de: {URL_IBGE}")
    try:
        r = requests.get(URL_IBGE, timeout=180)
        r.raise_for_status()
        geojson = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"[malha] FALHA via IBGE.\n  URL: {URL_IBGE}\n  Erro: {e}")
        return False

    feats = geojson.get("features", [])
    if not feats:
        print("[malha] FALHA via IBGE: GeoJSON sem features.")
        return False

    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    print(f"[malha] OK (IBGE): {len(feats)} municipios -> {SAIDA}")
    return True


def via_geobr() -> bool:
    print("[malha] tentando fallback via geobr.read_municipality(code_muni='SP', year=2022)")
    try:
        import geobr
        gdf = geobr.read_municipality(code_muni="SP", year=2022).to_crs(epsg=4326)
        gdf["geometry"] = gdf["geometry"].simplify(0.002, preserve_topology=True)
        gdf = gdf.rename(columns={"code_muni": "codarea"})
        gdf["codarea"] = gdf["codarea"].astype("int64").astype(str)
        gdf.to_file(SAIDA, driver="GeoJSON")
    except Exception as e:  # noqa: BLE001
        print(f"[malha] FALHA via geobr.\n  Erro: {e}")
        return False
    print(f"[malha] OK (geobr): {len(gdf)} municipios -> {SAIDA}")
    return True


def main() -> int:
    if via_ibge() or via_geobr():
        return 0
    print("[malha] FALHA: nao foi possivel obter a malha municipal de SP.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
