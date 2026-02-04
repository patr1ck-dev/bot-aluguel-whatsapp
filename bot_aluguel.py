"""
Sistema de Gestão de Aluguéis via WhatsApp
Versão: 1.0.8
"""

import json
import requests
import schedule
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from pathlib import Path

class BotAluguelMotos:
    
    
    def __init__(self, config_file='config.json'):
       
        self.carregar_config(config_file)
        self.conectar_sheets()
        print("✅ Bot inicializado com sucesso!")
    
    def carregar_config(self, config_file):
       
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Evolution API
            self.api_url = config['evolution_api']['url']
            self.api_key = config['evolution_api']['api_key']
            self.instance_name = config['evolution_api']['instance_name']
            
            # Administradores
            self.admin_pai = config['administradores']['pai']
            self.admin_irmao = config['administradores']['irmao']
            
            # Chave PIX
            self.chave_pix = config['chave_pix']
            
            # Google Sheets
            self.sheet_id = config['google_sheets']['spreadsheet_id']
            self.credentials_file = config['google_sheets']['credentials_file']
            
            print("✅ Configurações carregadas")
            
        except FileNotFoundError:
            print("❌ Arquivo config.json não encontrado!")
            self.criar_config_exemplo()
            raise
        except Exception as e:
            print(f"❌ Erro ao carregar config: {e}")
            raise
    
    def criar_config_exemplo(self):
       
        config_exemplo = {
            "evolution_api": {
                "url": "https://sua-evolution-api.com",
                "api_key": "SUA_API_KEY_AQUI",
                "instance_name": "nome_da_instancia"
            },
            "administradores": {
                "pai": "5511999999999",
                "irmao": "5511988888888"
            },
            "chave_pix": "sua.chave@pix.com",
            "google_sheets": {
                "spreadsheet_id": "ID_DA_SUA_PLANILHA",
                "credentials_file": "credentials.json"
            }
        }
        
        with open('config_exemplo.json', 'w', encoding='utf-8') as f:
            json.dump(config_exemplo, f, indent=4, ensure_ascii=False)
        
        print("📝 Arquivo 'config_exemplo.json' criado. Renomeie para 'config.json' e preencha.")
    
    def conectar_sheets(self):
        """Conecta ao Google Sheets"""
        try:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            
            client = gspread.authorize(creds)
            self.planilha = client.open_by_key(self.sheet_id)
            self.sheet = self.planilha.sheet1
            
            print("✅ Conectado ao Google Sheets")
            
        except FileNotFoundError:
            print(f"❌ Arquivo {self.credentials_file} não encontrado!")
            print("📖 Como obter credentials.json:")
            print("   1. Acesse: https://console.cloud.google.com/")
            print("   2. Crie um projeto")
            print("   3. Ative a API do Google Sheets")
            print("   4. Crie credenciais de Conta de Serviço")
            print("   5. Baixe o JSON e renomeie para 'credentials.json'")
            raise
        except Exception as e:
            print(f"❌ Erro ao conectar Sheets: {e}")
            raise
    
    def obter_clientes(self):
    
        try:
            # Esperado: Nome | WhatsApp | Valor
            dados = self.sheet.get_all_records()
            clientes = []
            
            for linha in dados:
                cliente = {
                    'nome': linha.get('Nome', ''),
                    'whatsapp': str(linha.get('WhatsApp', '')).strip(),
                    'valor': str(linha.get('Valor', '0')).replace('R$', '').strip()
                }
                
                # Validar dados
                if cliente['nome'] and cliente['whatsapp']:
                    clientes.append(cliente)
            
            print(f"✅ {len(clientes)} clientes carregados")
            return clientes
            
        except Exception as e:
            print(f"❌ Erro ao ler planilha: {e}")
            return []
    
    def enviar_mensagem(self, numero, mensagem):
        
        try:
            url = f"{self.api_url}/message/sendText/{self.instance_name}"
            
            headers = {
                'Content-Type': 'application/json',
                'apikey': self.api_key
            }
            
            payload = {
                'number': numero,
                'text': mensagem
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 201 or response.status_code == 200:
                print(f"✅ Mensagem enviada para {numero}")
                return True
            else:
                print(f"❌ Erro ao enviar para {numero}: {response.status_code}")
                print(f"   Resposta: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao enviar mensagem: {e}")
            return False
    
    def enviar_imagem(self, numero, imagem_path, legenda=''):
       
        try:
            url = f"{self.api_url}/message/sendMedia/{self.instance_name}"
            
            headers = {
                'apikey': self.api_key
            }
            
            # Ler imagem como base64
            import base64
            with open(imagem_path, 'rb') as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            payload = {
                'number': numero,
                'mediatype': 'image',
                'media': img_base64,
                'caption': legenda
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code in [200, 201]:
                print(f"✅ Imagem enviada para {numero}")
                return True
            else:
                print(f"❌ Erro ao enviar imagem: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erro ao enviar imagem: {e}")
            return False
    
    def executar_cobranca(self):
       
        print("\n" + "="*50)
        print(f"🕐 Iniciando cobrança - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("="*50)
        
        clientes = self.obter_clientes()
        
        if not clientes:
            print("⚠️ Nenhum cliente para cobrar")
            return
        
        enviados = 0
        erros = 0
        
        for cliente in clientes:
            mensagem = f"""Olá {cliente['nome']},

O vencimento da sua diária de R$ {cliente['valor']} é às 23:00.

💳 Segue a chave Pix para pagamento:
{self.chave_pix}

📸 Por favor, envie o comprovante aqui após o pagamento.

Obrigado! 🏍️"""
            
            if self.enviar_mensagem(cliente['whatsapp'], mensagem):
                enviados += 1
                time.sleep(2)  # Delay para não spammar
            else:
                erros += 1
        
        print("\n" + "-"*50)
        print(f"✅ Cobranças enviadas: {enviados}")
        print(f"❌ Erros: {erros}")
        print("-"*50 + "\n")
    
    def processar_webhook(self, dados_webhook):
       
        try:
            # Extrair informações do webhook
            event_type = dados_webhook.get('event', '')
            
            # Verificar se é mensagem recebida
            if event_type != 'messages.upsert':
                return
            
            mensagem = dados_webhook.get('data', {})
            
            # Informações da mensagem
            remetente = mensagem.get('key', {}).get('remoteJid', '')
            tipo_msg = mensagem.get('message', {}).get('messageType', '')
            
            # Limpar número (remover @s.whatsapp.net)
            numero_cliente = remetente.replace('@s.whatsapp.net', '')
            
            # Verificar se é cliente cadastrado
            clientes = self.obter_clientes()
            cliente_encontrado = None
            
            for cliente in clientes:
                if cliente['whatsapp'] in numero_cliente:
                    cliente_encontrado = cliente
                    break
            
            if not cliente_encontrado:
                print(f"⚠️ Mensagem de número não cadastrado: {numero_cliente}")
                return
            
            # Se for imagem, processar
            if tipo_msg == 'imageMessage':
                self.processar_comprovante(numero_cliente, cliente_encontrado, mensagem)
            
            # Se for texto, orientar
            elif tipo_msg == 'conversation' or tipo_msg == 'extendedTextMessage':
                resposta = "📸 Por favor, envie a foto do comprovante para que meu pai e meu irmão possam validar seu pagamento."
                self.enviar_mensagem(numero_cliente, resposta)
            
        except Exception as e:
            print(f"❌ Erro ao processar webhook: {e}")
    
    def processar_comprovante(self, numero_cliente, cliente, mensagem):
        """Processa comprovante recebido e encaminha para admins"""
        try:
            print(f"\n📸 Comprovante recebido de {cliente['nome']}")
            
            # Baixar imagem
            imagem_data = mensagem.get('message', {}).get('imageMessage', {})
            media_url = imagem_data.get('url', '')
            
            if not media_url:
                print("❌ URL da imagem não encontrada")
                return
            
            # Salvar imagem localmente
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            nome_arquivo = f"comprovante_{cliente['nome']}_{timestamp}.jpg"
            caminho_imagem = os.path.join('comprovantes', nome_arquivo)
            
            # Criar pasta se não existir
            Path('comprovantes').mkdir(exist_ok=True)
            
            # Baixar imagem
            headers = {'apikey': self.api_key}
            response = requests.get(media_url, headers=headers)
            
            if response.status_code == 200:
                with open(caminho_imagem, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ Comprovante salvo: {nome_arquivo}")
                
                # Encaminhar para administradores
                legenda = f"""✅ Comprovante recebido de {cliente['nome']}

📱 WhatsApp: {numero_cliente}
💰 Valor: R$ {cliente['valor']}
🕐 Recebido em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}

Por favor, dar baixa no sistema."""
                
                # Enviar para o pai
                self.enviar_imagem(self.admin_pai, caminho_imagem, legenda)
                time.sleep(1)
                
                # Enviar para o irmão
                self.enviar_imagem(self.admin_irmao, caminho_imagem, legenda)
                
                # Confirmar recebimento ao cliente
                confirmacao = f"✅ Comprovante recebido, {cliente['nome']}! Obrigado. Meu pai e meu irmão já foram notificados e vão validar o pagamento."
                self.enviar_mensagem(numero_cliente, confirmacao)
                
                print("✅ Comprovante encaminhado aos administradores")
            else:
                print(f"❌ Erro ao baixar imagem: {response.status_code}")
            
        except Exception as e:
            print(f"❌ Erro ao processar comprovante: {e}")
    
    def agendar_cobrancas(self):
       
        schedule.every().day.at("22:30").do(self.executar_cobranca)
        print("⏰ Cobrança agendada para 22:30 todos os dias")
    
    def iniciar(self):
        """Inicia o bot"""
        print("\n" + "="*50)
        print("🤖 BOT DE GESTÃO DE ALUGUÉIS")
        print("="*50)
        print(f"✅ Sistema iniciado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"✅ Próxima cobrança: Hoje às 22:30")
        print(f"✅ Administradores:")
        print(f"   👨 Pai: {self.admin_pai}")
        print(f"   👦 Irmão: {self.admin_irmao}")
        print("="*50 + "\n")
        
        # Agendar cobrança
        self.agendar_cobrancas()
        
        # Loop principal
        print(!)
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Verifica a cada 1 minuto
        except KeyboardInterrupt:
            print("\n\n⚠️ Bot encerrado pelo usuário")
            print("Até logo! 👋")

# Função auxiliar para testar cobrança manualmente
def testar_cobranca():
    
    bot = BotAluguelMotos()
    print("\n🧪 MODO DE TESTE - Executando cobrança agora\n")
    bot.executar_cobranca()

if __name__ == "__main__":
    # Para rodar normalmente
    bot = BotAluguelMotos()
    bot.iniciar()
    
    # Para testar (comente a linha acima e descomente abaixo)
    # testar_cobranca()
