"""
Baixa ocorrencias de violencia contra a mulher no estado de Sao Paulo,
2022 em diante, do Portal da Transparencia da SSP-SP e AGREGA por municipio.

Fonte (arquivos anuais, uma linha por BO):
  https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_<ANO>.xlsx

PRIVACIDADE: os arquivos originais contem dados individuais (endereco,
latitude/longitude, numero do BO). Este script NAO persiste nada disso.
Ele apenas CONTA ocorrencias por municipio e por natureza e grava somente
contagens agregadas. Os arquivos brutos sao apagados ao final.

Saidas:
  data/ocorrencias_mulher_sp.csv
    colunas: municipio, ano, natureza, ocorrencias
  data/delegacias_mulher_sp.csv
    colunas: municipio, tem_ddm   (derivado da coluna NOME_DELEGACIA do
    proprio dataset da SSP: municipios com uma delegacia cujo nome indica
    "Defesa da Mulher"/DDM. NAO contem enderecos.)

Nao inventa dados: se um ano falhar, imprime a URL tentada e o erro e
segue para os demais anos. Se nenhum ano funcionar, encerra com erro.
"""
import os
import re
import sys
import csv
import unicodedata
from collections import defaultdict

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "ocorrencias_mulher_sp.csv")
SAIDA_DDM = os.path.join(AQUI, "delegacias_mulher_sp.csv")

# Marcadores no nome da delegacia que indicam ser uma Delegacia de Defesa
# da Mulher (DDM). Checado sem acento e em maiuscula.
PADROES_DDM = ["DEFESA DA MULHER", "DELEG. DEF. MULHER", "DDM", "DEF MULHER", "DEFES MULHER"]

# Anos a processar. Pode ser sobrescrito pela linha de comando:
#   python download_ocorrencias.py 2023 2024
# Obs.: o ano corrente costuma estar INCOMPLETO no portal (ex.: so o 1o
# semestre). O painel sinaliza periodos incompletos.
ANOS = [2022, 2023, 2024, 2025]
URL_BASE = (
    "https://www.ssp.sp.gov.br/assets/estatistica/transparencia/"
    "spDados/SPDadosCriminais_{ano}.xlsx"
)

# Naturezas (coluna NATUREZA_APURADA / RUBRICA) consideradas violencia
# contra a mulher. IMPORTANTE: o arquivo SPDadosCriminais nao traz o sexo da
# vitima, entao NAO e possivel isolar mulheres em crimes nao-generados (ex.:
# lesao corporal atinge ambos os sexos). Por isso restringimos a naturezas
# predominantemente contra mulheres/meninas e a feminicidio, para nao
# superestimar. Casamos por substring, sem acento e em maiuscula.
PADROES_MULHER = [
    "FEMINICIDIO",
    "ESTUPRO",              # cobre "ESTUPRO" e "ESTUPRO DE VULNERAVEL"
    "IMPORTUNACAO SEXUAL",
    "VIOLENCIA DOMESTICA",
]


def sem_acento(txt: str) -> str:
    if txt is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(txt))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()


def eh_violencia_mulher(natureza_norm: str) -> bool:
    return any(p in natureza_norm for p in PADROES_MULHER)


def baixar(ano: int, destino: str, tentativas: int = 3) -> bool:
    url = URL_BASE.format(ano=ano)
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        print(f"[ocorrencias] baixando {ano} (tentativa {tentativa}/{tentativas}): {url}")
        try:
            with requests.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                total = 0
                with open(destino, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            total += len(chunk)
                print(f"[ocorrencias] {ano}: {total/1e6:.1f} MB baixados")
            return True
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            print(f"[ocorrencias] {ano}: falha na tentativa {tentativa}: {e}")
            import time
            time.sleep(5 * tentativa)
    print(f"[ocorrencias] FALHA no download de {ano}.\n  URL: {url}\n  Erro: {ultimo_erro}")
    return False


def agregar(destino: str, ano: int, contagem: dict, municipios_com_ddm: set,
            cod_mun_por_nome: dict) -> int:
    """Le o XLSX em modo streaming (read_only) e conta por municipio+natureza.
    Nao guarda nenhuma linha individual."""
    try:
        from openpyxl import load_workbook
    except Exception as e:  # noqa: BLE001
        print(f"[ocorrencias] openpyxl indisponivel: {e}")
        return 0

    try:
        wb = load_workbook(destino, read_only=True, data_only=True)

        # Um arquivo anual pode ter mais de uma aba de dados (ex.: JAN-JUN e
        # JUL-DEZ) alem de uma aba de glossario. Processamos TODAS as abas cujo
        # cabecalho contem as colunas esperadas.
        abas_dados = []
        for nome_aba in wb.sheetnames:
            cand = wb[nome_aba]
            it = cand.iter_rows(values_only=True)
            h = next(it, None)
            if not h:
                continue
            cols = {sem_acento(str(x)): i for i, x in enumerate(h) if x is not None}
            tem_mun = any(k in cols for k in ("NOME_MUNICIPIO", "MUNICIPIO", "CIDADE"))
            tem_nat = any(k in cols for k in ("NATUREZA_APURADA", "NATUREZA", "RUBRICA"))
            if tem_mun and tem_nat:
                abas_dados.append((nome_aba, cols, it))

        if not abas_dados:
            abas = ", ".join(wb.sheetnames)
            print(f"[ocorrencias] {ano}: nenhuma aba com colunas esperadas. Abas: {abas}")
            wb.close()
            return 0

        lidas = 0
        for nome_aba, idx, linhas in abas_dados:
            print(f"[ocorrencias] {ano}: processando aba '{nome_aba}'")

            def achar(*nomes):
                for n in nomes:
                    if n in idx:
                        return idx[n]
                return None

            i_mun = achar("NOME_MUNICIPIO", "MUNICIPIO", "CIDADE")
            i_nat = achar("NATUREZA_APURADA", "NATUREZA", "RUBRICA")
            i_del = achar("NOME_DELEGACIA", "DELEGACIA")
            i_cod = achar("CD_IBGE", "COD_IBGE", "CODIGO_IBGE")
            if i_mun is None or i_nat is None:
                continue

            for row in linhas:
                lidas += 1
                if i_mun >= len(row) or i_nat >= len(row):
                    continue
                municipio = row[i_mun]
                natureza = row[i_nat]
                if not municipio:
                    continue
                mun = str(municipio).strip().upper()

                cod = ""
                if i_cod is not None and i_cod < len(row) and row[i_cod] not in (None, ""):
                    cod = str(row[i_cod]).strip()
                    # CD_IBGE as vezes vem com 6 digitos (sem o DV) ou como float.
                    cod = cod.split(".")[0]
                    cod_mun_por_nome.setdefault(mun, cod)

                # Deteccao de DDM pelo nome da delegacia (dado agregado: so o
                # fato de existir uma DDM atuando no municipio, sem endereco).
                if i_del is not None and i_del < len(row) and row[i_del]:
                    del_norm = sem_acento(row[i_del])
                    if any(p in del_norm for p in PADROES_DDM):
                        municipios_com_ddm.add(mun)

                if not natureza:
                    continue
                nat_norm = sem_acento(natureza)
                if not eh_violencia_mulher(nat_norm):
                    continue
                contagem[(mun, ano, nat_norm)] += 1

        wb.close()
        print(f"[ocorrencias] {ano}: {lidas} linhas lidas (agregadas, sem persistir dados individuais)")
        return lidas
    except Exception as e:  # noqa: BLE001
        print(f"[ocorrencias] {ano}: FALHA ao processar XLSX.\n  Erro: {e}")
        return 0


def main() -> int:
    anos = [int(a) for a in sys.argv[1:]] if len(sys.argv) > 1 else ANOS
    contagem = defaultdict(int)
    municipios_com_ddm = set()
    cod_mun_por_nome = {}
    anos_ok = []
    for ano in anos:
        bruto = os.path.join(AQUI, f"_tmp_SPDadosCriminais_{ano}.xlsx")
        try:
            if baixar(ano, bruto):
                lidas = agregar(bruto, ano, contagem, municipios_com_ddm, cod_mun_por_nome)
                if lidas > 0:
                    anos_ok.append(ano)
        finally:
            # Remove o arquivo bruto (contem dados individuais) sempre.
            if os.path.exists(bruto):
                try:
                    os.remove(bruto)
                except OSError:
                    pass

    if not contagem:
        print("[ocorrencias] FALHA: nenhum ano processado com sucesso. Nada foi gravado.")
        return 1

    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["municipio", "cod_ibge", "ano", "natureza", "ocorrencias"])
        for (mun, ano, nat), n in sorted(contagem.items()):
            w.writerow([mun, cod_mun_por_nome.get(mun, ""), ano, nat, n])
    print(f"[ocorrencias] OK: anos {anos_ok} -> {SAIDA} ({len(contagem)} linhas agregadas)")

    # Grava a presenca de DDM por municipio (todos os municipios vistos nos
    # dados; tem_ddm=1 se uma DDM atua ali, 0 caso contrario).
    municipios_vistos = {mun for (mun, _, _) in contagem.keys()} | municipios_com_ddm
    with open(SAIDA_DDM, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["municipio", "cod_ibge", "tem_ddm"])
        for mun in sorted(municipios_vistos):
            w.writerow([mun, cod_mun_por_nome.get(mun, ""), 1 if mun in municipios_com_ddm else 0])
    print(f"[ocorrencias] OK: {len(municipios_com_ddm)} municipios com DDM -> {SAIDA_DDM}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
