import os
import pandas as pd
from nomes import fingerprint

AQUI = os.path.dirname(os.path.abspath(__file__))
pop = pd.read_csv(os.path.join(AQUI, "populacao_mulheres_sp.csv"), dtype={"cod_mun": str})
oco = pd.read_csv(os.path.join(AQUI, "ocorrencias_mulher_sp.csv"))
ddm = pd.read_csv(os.path.join(AQUI, "delegacias_mulher_sp.csv"))

pop["chave"] = pop["municipio"].map(fingerprint)
oco["chave"] = oco["municipio"].map(fingerprint)
ddm["chave"] = ddm["municipio"].map(fingerprint)

agg = oco.groupby("chave", as_index=False)["ocorrencias"].sum()
base = pop.merge(agg, on="chave", how="left").merge(
    ddm[["chave", "tem_ddm"]], on="chave", how="left"
)
base["tem_ddm"] = base["tem_ddm"].fillna(0).astype(int)
base["taxa_100k"] = (base["ocorrencias"] / base["pop_mulheres"] * 100_000).round(1)

print("municipios:", len(base))
print("com ocorrencia:", base["ocorrencias"].notna().sum())
print("com DDM:", int((base["tem_ddm"] == 1).sum()))
print("taxa mediana:", base["taxa_100k"].median())

lim = base["taxa_100k"].median()
des = base[(base["taxa_100k"] >= lim) & (base["tem_ddm"] == 0)]
print("desertos (taxa>=mediana e sem DDM):", len(des))
print(des.sort_values("taxa_100k", ascending=False)
      [["municipio", "pop_mulheres", "ocorrencias", "taxa_100k"]].head(8).to_string(index=False))
