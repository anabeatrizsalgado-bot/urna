import http.server
import socketserver
import json
import os
import hashlib
import hmac
import time
import pandas as pd
from datetime import datetime

PORT = 8000
CHAVE = b"cyber-urna-2026"

def ler_txt(arquivo):
    if not os.path.exists(arquivo): return []
    with open(arquivo, "r", encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]

def obter_ultimo_hash():
    votos = ler_txt("votos.dat")
    if not votos: return "GENESIS_CYBER"
    return json.loads(votos[-1])["hash"]

def registrar_voto(numero, cargo):
    anterior = obter_ultimo_hash()
    payload = f"{numero}|{cargo}|{time.time_ns()}|{anterior}"
    h = hashlib.sha256(payload.encode()).hexdigest()
    with open("votos.dat", "a", encoding="utf-8") as f:
        f.write(json.dumps({"numero": numero, "cargo": cargo, "hash_anterior": anterior, "hash": h}) + "\n")

def apurar_com_pandas():
    votos_linhas = ler_txt("votos.dat")
    if not votos_linhas: return {"resultados": {}, "stats": {}, "partidos": {}}

    df_votos = pd.DataFrame([json.loads(l) for l in votos_linhas])
    cands_linhas = ler_txt("candidatos.txt")
    dados_cands = [l.split(";") for l in cands_linhas if len(l.split(";")) >= 4]
    df_cands = pd.DataFrame(dados_cands, columns=["numero", "nome", "cargo", "partido"])

    df_merged = df_votos.merge(df_cands, on=["numero", "cargo"], how="left")
    df_merged["nome"] = df_merged["nome"].fillna("NULO/BRANCO")
    df_merged["partido"] = df_merged["partido"].fillna("-")

    # Resultados por Cargo
    agrupado = df_merged.groupby(["cargo", "numero", "nome", "partido"]).size().reset_index(name="votos")
    resultados = {}
    for cargo in agrupado["cargo"].unique():
        df_cargo = agrupado[agrupado["cargo"] == cargo].sort_values(by="votos", ascending=False)
        resultados[cargo] = df_cargo.to_dict(orient="records")

    # Resultados por Partido (Nova Funcionalidade)
    partidos = df_merged[df_merged["partido"] != "-"].groupby("partido").size().reset_index(name="votos").sort_values(by="votos", ascending=False).to_dict(orient="records")

    total_eleitores = len(ler_txt("eleitores.txt"))
    compareceram = len(ler_txt("ja_votaram.dat"))

    return {
        "resultados": resultados,
        "partidos": partidos,
        "stats": {"total": total_eleitores, "compareceram": compareceram, "abstencoes": total_eleitores - compareceram}
    }

def gerar_bu():
    dados = apurar_com_pandas()
    if not dados["resultados"]: return "Sem votos."
    
    linhas = [f"BOLETIM OFICIAL DE URNA - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", "="*50]
    for cargo, cands in dados["resultados"].items():
        linhas.append(f"\nCARGO: {cargo.upper()}")
        for c in cands:
            linhas.append(f"  {c['numero']:>5} | {c['nome']:<20} | {c['votos']:>3} votos")
            
    texto = "\n".join(linhas)
    assinatura = hmac.new(CHAVE, texto.encode(), hashlib.sha256).hexdigest()
    
    with open("boletim.txt", "w", encoding="utf-8") as f:
        f.write(texto + f"\n\nASSINATURA HMAC-SHA256:\n{assinatura}\n")
    return "BU gerado com sucesso."

def verificar_cadeia():
    anterior = "GENESIS_CYBER"
    for l in ler_txt("votos.dat"):
        r = json.loads(l)
        if r["hash_anterior"] != anterior: return False
        anterior = r["hash"]
    return True

class UrnaHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            
            if self.path == '/api/dados':
                eleitores = {}
                for l in ler_txt("eleitores.txt"):
                    p = l.split(";")
                    if len(p) >= 2: eleitores[p[0]] = p[1]
                candidatos = []
                for l in ler_txt("candidatos.txt"):
                    p = l.split(";")
                    if len(p) >= 4: candidatos.append({"numero": p[0], "nome": p[1], "cargo": p[2], "partido": p[3]})
                self.wfile.write(json.dumps({"eleitores": eleitores, "candidatos": candidatos}).encode('utf-8'))
            elif self.path == '/api/resultados':
                self.wfile.write(json.dumps(apurar_com_pandas()).encode('utf-8'))
            elif self.path == '/api/auditar':
                self.wfile.write(json.dumps({"integridade": verificar_cadeia()}).encode('utf-8'))
            return
        super().do_GET()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        dados = json.loads(post_data)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()

        if self.path == '/api/votar':
            eid = dados.get("eid")
            votos = dados.get("votos", [])
            if eid in ler_txt("ja_votaram.dat"):
                res = {"status": "erro", "msg": "Você já votou."}
            else:
                for v in votos: registrar_voto(v["numero"], v["cargo"])
                with open("ja_votaram.dat", "a", encoding="utf-8") as f: f.write(eid + "\n")
                res = {"status": "ok"}
            self.wfile.write(json.dumps(res).encode('utf-8'))
        elif self.path == '/api/gerar_bu':
            msg = gerar_bu()
            self.wfile.write(json.dumps({"msg": msg}).encode('utf-8'))

print(f"⚡ Cyber-Urna rodando em http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), UrnaHandler) as httpd:
    httpd.serve_forever()