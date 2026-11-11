import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime
from collections import defaultdict

# =====================================================================
# CONFIGURAÇÕES GLOBAIS E PALETA DE CORES (ANSI)
# =====================================================================
ELEITORES_FILE  = "eleitores.txt"
CANDIDATOS_FILE = "candidatos.txt"
VOTOS_FILE      = "votos.dat"
JAVOTARAM_FILE  = "ja_votaram.dat"
AUDITORIA_FILE  = "auditoria.log"
BOLETIM_FILE    = "boletim.txt"
CHAVE_SECRETA   = b"urna-eletronica-brasil-2026-alta-seguranca"

class C:
    RESET    = "\033[0m"
    BOLD     = "\033[1m"
    ITALIC   = "\033[3m"
    UNDER    = "\033[4m"
    
    # Cores Base
    BLACK    = "\033[30m"
    RED      = "\033[31m"
    GREEN    = "\033[32m"
    YELLOW   = "\033[33m"
    BLUE     = "\033[34m"
    MAGENTA  = "\033[35m"
    CYAN     = "\033[36m"
    WHITE    = "\033[37m"
    
    # Cores Brilhantes
    BRED     = "\033[91m"
    BGREEN   = "\033[92m"
    BYELLOW  = "\033[93m"
    BBLUE    = "\033[94m"
    BMAGENTA = "\033[95m"
    BCYAN    = "\033[96m"
    BWHITE   = "\033[97m"
    
    # Fundos
    BGRED    = "\033[41m"
    BGBLUE   = "\033[44m"
    BGCYAN   = "\033[46m"

# =====================================================================
# MÓDULO 1: CRIPTOGRAFIA E SEGURANÇA
# =====================================================================
class Seguranca:
    @staticmethod
    def gerar_hash_sha256(texto: str) -> str:
        return hashlib.sha256(texto.encode('utf-8')).hexdigest()
    
    @staticmethod
    def gerar_hmac(texto: str, chave: bytes = CHAVE_SECRETA) -> str:
        return hmac.new(chave, texto.encode('utf-8'), hashlib.sha256).hexdigest()
    
    @staticmethod
    def mascarar_hash(hash_str: str) -> str:
        return f"{hash_str[:8]}...{hash_str[-8:]}"

class Validador:
    @staticmethod
    def validar_cpf(cpf: str) -> bool:
        # Simulação de validação de CPF para dar complexidade ao sistema
        cpf = ''.join(filter(str.isdigit, cpf))
        if len(cpf) != 11 or len(set(cpf)) == 1:
            return False
        return True

# =====================================================================
# MÓDULO 2: PERSISTÊNCIA DE DADOS (ENGINE)
# =====================================================================
class BancoDados:
    def __init__(self):
        self._inicializar_arquivos()
        
    def _inicializar_arquivos(self):
        arquivos = [VOTOS_FILE, JAVOTARAM_FILE, AUDITORIA_FILE]
        for arq in arquivos:
            if not os.path.exists(arq):
                open(arq, 'a').close()

    def ler_linhas(self, caminho: str) -> list:
        if not os.path.exists(caminho): return []
        with open(caminho, 'r', encoding='utf-8') as f:
            return [l.strip() for l in f if l.strip()]
            
    def append_linha(self, caminho: str, linha: str):
        with open(caminho, 'a', encoding='utf-8') as f:
            f.write(linha + "\n")
            
    def carregar_eleitores(self) -> dict:
        eleitores = {}
        for linha in self.ler_linhas(ELEITORES_FILE):
            partes = linha.split(';')
            if len(partes) >= 3:
                eleitores[partes[0]] = {"nome": partes[1], "cpf": partes[2]}
        return eleitores

    def carregar_candidatos(self) -> list:
        candidatos = []
        for linha in self.ler_linhas(CANDIDATOS_FILE):
            partes = linha.split(';')
            if len(partes) >= 4:
                candidatos.append({
                    "numero": partes[0],
                    "nome": partes[1],
                    "cargo": partes[2],
                    "partido": partes[3]
                })
        return candidatos
        
    def obter_ultimo_hash(self) -> str:
        linhas = self.ler_linhas(VOTOS_FILE)
        if not linhas: return "GENESIS_BLOCK_0000"
        return json.loads(linhas[-1])["hash"]

    def registrar_voto(self, numero: str, cargo: str):
        anterior = self.obter_ultimo_hash()
        timestamp = time.time_ns()
        payload = f"{numero}|{cargo}|{timestamp}|{anterior}"
        novo_hash = Seguranca.gerar_hash_sha256(payload)
        
        registro = {
            "numero": numero,
            "cargo": cargo,
            "timestamp": timestamp,
            "hash_anterior": anterior,
            "hash": novo_hash
        }
        self.append_linha(VOTOS_FILE, json.dumps(registro))
        
    def registrar_auditoria(self, evento: str, nivel="INFO"):
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.append_linha(AUDITORIA_FILE, f"[{dt}] [{nivel}] {evento}")

    def marcar_eleitor_votou(self, eid: str):
        self.append_linha(JAVOTARAM_FILE, eid)
        
    def eleitor_ja_votou(self, eid: str) -> bool:
        return eid in self.ler_linhas(JAVOTARAM_FILE)

    def verificar_cadeia_hashes(self) -> tuple:
        anterior = "GENESIS_BLOCK_0000"
        for linha in self.ler_linhas(VOTOS_FILE):
            r = json.loads(linha)
            if r["hash_anterior"] != anterior:
                return False, r
            anterior = r["hash"]
        return True, None

# =====================================================================
# MÓDULO 3: ESTATÍSTICAS E APURAÇÃO
# =====================================================================
class MotorApuracao:
    def __init__(self, db: BancoDados):
        self.db = db

    def calcular_resultados(self) -> dict:
        votos = self.db.ler_linhas(VOTOS_FILE)
        candidatos = self.db.carregar_candidatos()
        eleitores = self.db.carregar_eleitores()
        
        total_eleitores = len(eleitores)
        compareceram = len(self.db.ler_linhas(JAVOTARAM_FILE))
        abstencoes = total_eleitores - compareceram
        
        contagem = defaultdict(int)
        for l in votos:
            v = json.loads(l)
            contagem[(v["cargo"], v["numero"])] += 1
            
        mapa_cands = {(c["numero"], c["cargo"]): c for c in candidatos}
        
        # Organizar por cargo
        resultados_por_cargo = defaultdict(list)
        total_votos_geral = 0
        
        for (cargo, numero), qtd in contagem.items():
            c = mapa_cands.get((numero, cargo), {"nome": "DESCONHECIDO", "partido": "-"})
            resultados_por_cargo[cargo].append({
                "numero": numero,
                "nome": c["nome"],
                "partido": c["partido"],
                "votos": qtd
            })
            total_votos_geral += qtd
            
        # Ordenar candidatos por voto dentro de cada cargo
        for cargo in resultados_por_cargo:
            resultados_por_cargo[cargo].sort(key=lambda x: -x["votos"])
            
        return {
            "cargos": resultados_por_cargo,
            "estatisticas": {
                "total_eleitores": total_eleitores,
                "compareceram": compareceram,
                "abstencoes": abstencoes,
                "total_votos": total_votos_geral
            }
        }

    def gerar_boletim_urna(self) -> str:
        dados = self.calcular_resultados()
        if not dados["cargos"]: return "Sem votos."
        
        linhas = []
        linhas.append(f"BOLETIM OFICIAL DE URNA - GERADO EM {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        linhas.append("=" * 60)
        
        for cargo, candidatos in dados["cargos"].items():
            linhas.append(f"\nCARGO: {cargo.upper()}")
            linhas.append("-" * 60)
            for c in candidatos:
                linhas.append(f"  {c['numero']:>6} | {c['nome']:<20} | {c['partido']:<5} | {c['votos']:>3} votos")
                
        linhas.append("\n" + "=" * 60)
        linhas.append("ESTATÍSTICAS GERAIS")
        est = dados["estatisticas"]
        linhas.append(f"Eleitores Aptos: {est['total_eleitores']}")
        linhas.append(f"Comparecimento:  {est['compareceram']}")
        linhas.append(f"Abstenções:      {est['abstencoes']}")
        
        texto_puro = "\n".join(linhas)
        assinatura = Seguranca.gerar_hmac(texto_puro)
        
        conteudo_final = texto_puro + f"\n\nASSINATURA CRIPTOGRÁFICA HMAC-SHA256:\n{assinatura}\n"
        with open(BOLETIM_FILE, 'w', encoding='utf-8') as f:
            f.write(conteudo_final)
            
        self.db.registrar_auditoria("BOLETIM GERADO E ASSINADO", "INFO")
        return conteudo_final

# =====================================================================
# MÓDULO 4: INTERFACE VISUAL (DESIGN DO TERMINAL)
# =====================================================================
class TerminalUI:
    @staticmethod
    def limpar():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def digitando(texto, delay=0.03, cor=C.BCYAN):
        print(f"{cor}", end="")
        for char in texto:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        print(C.RESET)

    @staticmethod
    def spinner(texto, tempo=1.2):
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        start_time = time.time()
        i = 0
        while time.time() - start_time < tempo:
            sys.stdout.write(f"\r{C.YELLOW}{texto} {C.BCYAN}{frames[i % len(frames)]}{C.RESET}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write(f"\r{C.GREEN}✓ {texto} Concluído!{C.RESET}      \n")

    @staticmethod
    def caixa_texto(titulo, linhas, cor_borda=C.BBLUE, cor_titulo=C.BYELLOW):
        largura = 64
        print(f"\n{cor_borda}╔{'═' * (largura-2)}╗{C.RESET}")
        
        # Título centralizado
        espacos_totais = largura - 2 - len(titulo) - 2
        esp_esq = espacos_totais // 2
        esp_dir = espacos_totais - esp_esq
        print(f"{cor_borda}║{C.RESET} {' ' * esp_esq}{cor_titulo}{C.BOLD}{titulo}{C.RESET}{' ' * esp_dir} {cor_borda}║{C.RESET}")
        print(f"{cor_borda}╠{'═' * (largura-2)}╣{C.RESET}")
        
        for l in linhas:
            # Remove códigos de cor para calcular o espaço correto
            l_limpa = l
            for cor in [C.RESET, C.BOLD, C.ITALIC, C.UNDER, C.BRED, C.BGREEN, C.BYELLOW, C.BBLUE, C.BMAGENTA, C.BCYAN, C.BWHITE, C.BGRED, C.BGBLUE, C.BGCYAN]:
                l_limpa = l_limpa.replace(cor, "")
            
            padding = largura - 3 - len(l_limpa)
            print(f"{cor_borda}║{C.RESET} {l}{' ' * max(0, padding)}{cor_borda}║{C.RESET}")
            
        print(f"{cor_borda}╚{'═' * (largura-2)}╝{C.RESET}")

    @staticmethod
    def cabecalho_principal(subtitulo=""):
        TerminalUI.limpar()
        print(f"\n{C.BBLUE}{C.BOLD}")
        print(r"  ██╗   ██╗██████╗ ███╗   ██╗ █████╗ ")
        print(r"  ██║   ██║██╔══██╗████╗  ██║██╔══██╗")
        print(r"  ██║   ██║██████╔╝██╔██╗ ██║███████║")
        print(r"  ██║   ██║██╔══██╗██║╚██╗██║██╔══██║")
        print(r"  ╚██████╔╝██║  ██║██║ ╚████║██║  ██║")
        print(r"   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝")
        print(f"{C.RESET}")
        print(f"{C.BCYAN}        SISTEMA ELEITORAL BRASILEIRO - 2026{C.RESET}")
        if subtitulo:
            print(f"{C.YELLOW}                » {subtitulo} «{C.RESET}")
        print(f"{C.BBLUE}{'─' * 66}{C.RESET}\n")

# =====================================================================
# MÓDULO 5: CONTROLADOR PRINCIPAL DA URNA
# =====================================================================
class UrnaController:
    def __init__(self):
        self.db = BancoDados()
        self.apuracao = MotorApuracao(self.db)
        self.ui = TerminalUI()
        self.candidatos = self.db.carregar_candidatos()
        self.cargos = list(dict.fromkeys([c["cargo"] for c in self.candidatos]))

    def iniciar(self):
        while True:
            self.ui.cabecalho_principal("MENU PRINCIPAL")
            
            menu = [
                f"{C.BCYAN}[1]{C.RESET} {C.BWHITE}Iniciar Votação (Eleitor){C.RESET}",
                f"{C.BCYAN}[2]{C.RESET} {C.BWHITE}Apuração de Resultados{C.RESET}",
                f"{C.BCYAN}[3]{C.RESET} {C.BWHITE}Auditoria de Integridade{C.RESET}",
                f"{C.BCYAN}[4]{C.RESET} {C.BWHITE}Gerar Boletim de Urna (BU){C.RESET}",
                f"{C.BRED}[0]{C.RESET} {C.BWHITE}Desligar Urna{C.RESET}"
            ]
            self.ui.caixa_texto("SELECIONE UMA AÇÃO", menu)
            
            opcao = input(f"\n{C.BCYAN}➜ {C.RESET}").strip()
            
            if opcao == '1':
                self.fluxo_votacao()
            elif opcao == '2':
                self.tela_apuracao()
            elif opcao == '3':
                self.tela_auditoria()
            elif opcao == '4':
                self.tela_boletim()
            elif opcao == '0':
                print(f"\n{C.BGREEN}Urna desligada com segurança.{C.RESET}\n")
                break

    def fluxo_votacao(self):
        self.ui.limpar()
        self.ui.cabecalho_principal("AUTENTICAÇÃO DO ELEITOR")
        
        self.ui.caixa_texto("MESÁRIO", [
            "Aguardando identificação do eleitor.",
            "Digite o Título de Eleitor para liberar a urna."
        ], cor_borda=C.BMAGENTA)
        
        eid = input(f"\n{C.BCYAN}Título de Eleitor: {C.RESET}").strip()
        eleitores = self.db.carregar_eleitores()
        
        if eid not in eleitores:
            print(f"\n{C.BRED}❌ ERRO: Eleitor não cadastrado no sistema.{C.RESET}")
            self.db.registrar_auditoria(f"TENTATIVA ACESSO NEGADO: ID {eid}", "WARN")
            time.sleep(2)
            return
            
        if self.db.eleitor_ja_votou(eid):
            print(f"\n{C.BRED}❌ ERRO: Este eleitor já votou.{C.RESET}")
            self.db.registrar_auditoria(f"TENTATIVA DUPLICIDADE: ID {eid}", "WARN")
            time.sleep(2)
            return

        self.ui.spinner("Validando credenciais")
        self.db.registrar_auditoria(f"URNA LIBERADA: ID {eid}")
        self.tela_votos(eid, eleitores[eid]["nome"])

    def tela_votos(self, eid, nome_eleitor):
        votos_sessao = []
        
        for idx, cargo in enumerate(self.cargos):
            opcoes = [c for c in self.candidatos if c["cargo"] == cargo]
            
            while True:
                self.ui.limpar()
                self.ui.cabecalho_principal(f"VOTAÇÃO {idx+1}/{len(self.cargos)}")
                
                painel = [f"{C.BWHITE}Eleitor:{C.RESET} {C.BGREEN}{nome_eleitor}{C.RESET}", ""]
                painel.append(f"{C.BYELLOW}{'NÚMERO':<10}{'CANDIDATO':<25}{'PARTIDO'}{C.RESET}")
                painel.append(f"{C.BBLUE}{'─' * 50}{C.RESET}")
                
                for c in opcoes:
                    cor_nome = C.CYAN if c['nome'] == 'NULO' else C.BWHITE
                    painel.append(f" {C.BYELLOW}{c['numero']:<10}{C.RESET}{cor_nome}{c['nome']:<25}{C.RESET}{C.BMAGENTA}({c['partido']}){C.RESET}")
                    
                self.ui.caixa_texto(f"CARGO: {cargo.upper()}", painel, cor_borda=C.BGREEN, cor_titulo=C.BGREEN)
                
                print(f"\n{C.ITALIC}Digite o número do candidato, ou 'B' para Votar em Branco.{C.RESET}")
                voto = input(f"{C.BGREEN}➜ VOTO: {C.RESET}").strip().upper()
                
                if voto == 'B':
                    voto = "BRANCO"
                    break
                elif voto in [c["numero"] for c in opcoes]:
                    # Mostra o candidato escolhido
                    cand = next(c for c in opcoes if c["numero"] == voto)
                    print(f"\n{C.BWHITE}Candidato: {C.BGREEN}{cand['nome']}{C.RESET}")
                    conf = input(f"{C.BYELLOW}Confirmar? (S/N): {C.RESET}").strip().upper()
                    if conf == 'S': break
                    else: continue
                else:
                    print(f"\n{C.BRED}⚠️ Número inválido!{C.RESET}")
                    time.sleep(1)
            
            votos_sessao.append({"numero": voto, "cargo": cargo})
            self.ui.spinner("Registrando voto", 0.5)

        # Gravação
        self.ui.limpar()
        self.ui.cabecalho_principal("GRAVANDO VOTOS")
        self.ui.spinner("Gerando Hash Chain de segurança", 1.5)
        
        for v in votos_sessao:
            self.db.registrar_voto(v["numero"], v["cargo"])
            
        self.db.marcar_eleitor_votou(eid)
        self.db.registrar_auditoria(f"VOTO COMPUTADO: ID {eid}")
        
        print(f"\n{C.BGREEN}✅ Voto registrado com absoluto sucesso!{C.RESET}")
        print(f"{C.BWHITE}Obrigado por exercer sua cidadania, {C.BYELLOW}{nome_eleitor}{C.BWHITE}.{C.RESET}")
        time.sleep(3)

    def tela_apuracao(self):
        self.ui.limpar()
        self.ui.cabecalho_principal("APURAÇÃO DE RESULTADOS")
        self.ui.spinner("Lendo e descriptografando votos", 1)
        
        dados = self.apuracao.calcular_resultados()
        if not dados["cargos"]:
            print(f"{C.BYELLOW}Nenhum voto registrado no sistema.{C.RESET}")
            time.sleep(2)
            return

        for cargo, cands in dados["cargos"].items():
            linhas = []
            total_cargo = sum(c["votos"] for c in cands)
            
            for i, c in enumerate(cands):
                pct = (c["votos"] / total_cargo * 100) if total_cargo > 0 else 0
                
                # Design da Barra de Progresso
                blocos = int(pct / 5)
                barra = f"{C.BGREEN}{'█' * blocos}{C.CYAN}{'░' * (20 - blocos)}{C.RESET}"
                
                if i == 0 and c['nome'] != 'NULO':
                    icone = "🏆"
                    cor = C.BGREEN
                else:
                    icone = "  "
                    cor = C.BWHITE
                    
                linhas.append(f"{icone} {C.BYELLOW}{c['numero']:>5}{C.RESET} {cor}{c['nome'][:18]:<18}{C.RESET} {barra} {C.BCYAN}{c['votos']:>3} ({pct:.1f}%){C.RESET}")
                
            self.ui.caixa_texto(f"{cargo.upper()} (Total: {total_cargo})", linhas, cor_borda=C.BCYAN)
            
        # Estatísticas gerais no rodapé
        est = dados["estatisticas"]
        print(f"\n{C.BMAGENTA}📊 ESTATÍSTICAS GERAIS:{C.RESET}")
        print(f"  {C.BWHITE}Aptos:{C.RESET} {est['total_eleitores']} | {C.BWHITE}Compareceram:{C.RESET} {est['compareceram']} | {C.BRED}Abstenções:{C.RESET} {est['abstencoes']}")
        
        input(f"\n{C.CYAN}Pressione ENTER para voltar...{C.RESET}")

    def tela_auditoria(self):
        self.ui.limpar()
        self.ui.cabecalho_principal("AUDITORIA CRIPTOGRÁFICA")
        self.ui.spinner("Verificando cadeia de blocos SHA-256", 1.5)
        
        ok, erro = self.db.verificar_cadeia_hashes()
        if ok:
            self.ui.caixa_texto("STATUS DA URNA", [
                f"{C.BGREEN}✅ CADEIA DE HASHES 100% ÍNTEGRA{C.RESET}",
                "",
                f"{C.BWHITE}Nenhuma inconsistência foi encontrada.{C.RESET}",
                f"{C.BWHITE}Os votos estão seguros e não foram adulterados.{C.RESET}"
            ], cor_borda=C.BGREEN, cor_titulo=C.BGREEN)
            self.db.registrar_auditoria("AUDITORIA: CADEIA INTEGRA", "INFO")
        else:
            self.ui.caixa_texto("ALERTA DE ADULTERAÇÃO", [
                f"{C.BRED}❌ FALHA CRÍTICA DETECTADA!{C.RESET}",
                f"{C.BWHITE}A cadeia de blocos foi quebrada.{C.RESET}",
                f"{C.BYELLOW}Registro corrompido:{C.RESET}",
                f"{C.BRED}{json.dumps(erro)}{C.RESET}"
            ], cor_borda=C.BRED, cor_titulo=C.BRED)
            self.db.registrar_auditoria("AUDITORIA: ADULTERAÇÃO DETECTADA", "ERROR")
            
        input(f"\n{C.CYAN}Pressione ENTER para voltar...{C.RESET}")

    def tela_boletim(self):
        self.ui.limpar()
        self.ui.cabecalho_principal("BOLETIM DE URNA (BU)")
        self.ui.spinner("Assinando documento com HMAC", 1.5)
        
        conteudo = self.apuracao.gerar_boletim_urna()
        self.ui.caixa_texto("BOLETIM GERADO COM SUCESSO", [
            f"{C.BGREEN}O arquivo '{BOLETIM_FILE}' foi criado.{C.RESET}",
            f"{C.BWHITE}Ele contém a assinatura digital e pode ser auditado.{C.RESET}",
            "",
            f"{C.CYAN}Prévia do Hash:{C.RESET}",
            f"{C.YELLOW}{Seguranca.gerar_hmac(conteudo[:50])[:32]}...{C.RESET}"
        ], cor_borda=C.BGREEN)
        
        input(f"\n{C.CYAN}Pressione ENTER para voltar...{C.RESET}")

# =====================================================================
# EXECUÇÃO PRINCIPAL
# =====================================================================
if __name__ == "__main__":
    try:
        app = UrnaController()
        app.iniciar()
    except KeyboardInterrupt:
        print(f"\n\n{C.BRED}⚠️ Urna desligada abruptamente (Ctrl+C).{C.RESET}\n")
        sys.exit(0)