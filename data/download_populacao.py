"""
Baixa a populacao de mulheres por municipio do estado de Sao Paulo (UF 35)
a partir do Censo 2022, via API SIDRA do IBGE (tabela 9514).

Saida: data/populacao_mulheres_sp.csv  (colunas: cod_mun, municipio, pop_mulheres)

Nao inventa dados: se o download falhar, imprime a URL tentada e o erro e
encerra com codigo diferente de zero (os demais scripts seguem).
"""
import os
import sys
import json
import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "populacao_mulheres_sp.csv")

# Tabela 9514 - Populacao residente, Censo 2022.
# n6/in n3 35  -> todos os municipios (n6) contidos na UF 35 (SP)
# v/93         -> variavel "Populacao residente"
# p/2022       -> ano 2022
# c2/5          -> Sexo = Mulheres
# c287/100362   -> Idade = Total (codigo correto do "Total"; "0" NAO e o total)
# c286/113635   -> Forma de declaracao da idade = Total
# /f/u          -> formato JSON com codigos E nomes (D1C=codigo, D1N=nome)
URL = (
    "https://apisidra.ibge.gov.br/values/t/9514/n6/in%20n3%2035/"
    "v/93/p/2022/c2/5/c287/100362/c286/113635/f/u"
)


def main() -> int:
    print(f"[populacao] baixando de: {URL}")
    try:
        resp = requests.get(URL, timeout=120)
        resp.raise_for_status()
        registros = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[populacao] FALHA no download.\n  URL: {URL}\n  Erro: {e}")
        return 1

    # O primeiro elemento e o cabecalho (dicionario de rotulos). Descartamos.
    linhas = []
    for reg in registros[1:]:
        cod = reg.get("D1C")       # codigo do municipio (7 digitos)
        nome = reg.get("D1N")      # "Adamantina - SP"
        valor = reg.get("V")       # populacao de mulheres
        if cod is None or valor in (None, "", "...", "-", "X"):
            continue
        municipio = nome.replace(" - SP", "").strip() if nome else ""
        try:
            pop = int(float(valor))
        except (TypeError, ValueError):
            continue
        linhas.append((cod.strip(), municipio, pop))

    if not linhas:
        print("[populacao] FALHA: resposta recebida sem registros utilizaveis.")
        return 1

    import csv
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cod_mun", "municipio", "pop_mulheres"])
        w.writerows(linhas)

    print(f"[populacao] OK: {len(linhas)} municipios -> {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
