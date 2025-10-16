"""
Script de Teste - Evolution API Go Mobi
========================================

Este script testa a integração com WhatsApp via Evolution API.

Comandos disponíveis:
- python test_evolution_gomobi.py criar      → Cria instância do WhatsApp
- python test_evolution_gomobi.py qrcode     → Obtém QR Code para conectar
- python test_evolution_gomobi.py status     → Verifica se está conectado
- python test_evolution_gomobi.py enviar     → Envia mensagem de teste

Primeiro cria a instancia no Manager do Evolution - https://go-mobi-whatsapp.onrender.com/manager
Depois gera o QR code com o comando 2 acima. 
Depois vai no manager e visualiza o QRCode para ler no smartphone.
Ai já vai ficar conectado. Pode dar o comando de status para validar.
Pronto para testar.


Autor: Manus AI
Data: 14 de outubro de 2025
"""

import requests
import sys
import json

# ============================================
# CONFIGURAÇÕES - NÃO ALTERE
# ============================================
API_URL = "https://go-mobi-whatsapp.onrender.com"
API_KEY = "GoMobi2025SecretKeyWhatsapp!@#"
INSTANCE_NAME = "gomobi"

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def print_header(title):
    """Imprime cabeçalho formatado"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_success(message):
    """Imprime mensagem de sucesso"""
    print(f"✅ {message}")


def print_error(message):
    """Imprime mensagem de erro"""
    print(f"❌ {message}")


def print_info(message):
    """Imprime mensagem informativa"""
    print(f"ℹ️  {message}")


def get_headers():
    """Retorna headers para requisições"""
    return {
        'apikey': API_KEY,
        'Content-Type': 'application/json'
    }


# ============================================
# COMANDOS
# ============================================

def criar_instancia():
    """Cria uma nova instância do WhatsApp"""
    print_header("CRIAR INSTÂNCIA DO WHATSAPP")
    
    print_info("Criando instância 'gomobi' na Evolution API...")
    print_info(f"URL: {API_URL}")
    print()
    
    try:
        url = f"{API_URL}/instance/create"
        
        data = {
            "instanceName": INSTANCE_NAME,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        
        response = requests.post(
            url,
            headers=get_headers(),
            json=data,
            timeout=30
        )
        
        if response.status_code == 201:
            print_success("Instância criada com sucesso!")
            print()
            
            result = response.json()
            
            # Mostra informações
            if 'instance' in result:
                print("📋 Informações da Instância:")
                print(f"   Nome: {result['instance'].get('instanceName', 'N/A')}")
                print(f"   Status: {result['instance'].get('status', 'N/A')}")
            
            print()
            print_info("Próximo passo: Execute 'python test_evolution_gomobi.py qrcode'")
            
        elif response.status_code == 409:
            print_info("Instância já existe! Isso é normal.")
            print()
            print_info("Próximo passo: Execute 'python test_evolution_gomobi.py qrcode'")
            
        else:
            print_error(f"Erro ao criar instância: {response.status_code}")
            print(f"Resposta: {response.text}")
            
    except requests.exceptions.Timeout:
        print_error("Timeout ao conectar com a API")
        print_info("O servidor pode estar dormindo. Tente novamente em 1 minuto.")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Erro de conexão: {e}")
        
    except Exception as e:
        print_error(f"Erro inesperado: {e}")


def obter_qrcode():
    """Obtém o QR Code para conectar o WhatsApp"""
    print_header("OBTER QR CODE PARA CONECTAR WHATSAPP")
    
    print_info("Solicitando QR Code...")
    print()
    
    try:
        url = f"{API_URL}/instance/connect/{INSTANCE_NAME}"
        
        response = requests.get(
            url,
            headers=get_headers(),
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Tenta extrair o QR Code
            qrcode_found = False
            
            if 'qrcode' in result:
                qr_data = result['qrcode']
                
                if isinstance(qr_data, dict) and 'code' in qr_data:
                    qrcode_base64 = qr_data['code']
                    qrcode_found = True
                elif isinstance(qr_data, str):
                    qrcode_base64 = qr_data
                    qrcode_found = True
            
            elif 'base64' in result:
                qrcode_base64 = result['base64']
                qrcode_found = True
            
            if qrcode_found:
                print_success("QR Code obtido com sucesso!")
                print()
                print("📱 COMO CONECTAR:")
                print()
                print("1. Abra o WhatsApp no seu celular")
                print("2. Vá em: Configurações → Aparelhos conectados")
                print("3. Toque em: Conectar um aparelho")
                print("4. Acesse o link abaixo no navegador:")
                print()
                print("   🔗 https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" + qrcode_base64)
                print()
                print("5. Escaneie o QR Code que aparecer")
                print()
                print_info("Após escanear, execute: python test_evolution_gomobi.py status")
                
            else:
                # Pode estar já conectado
                print_info("Não foi possível obter QR Code.")
                print_info("Possíveis motivos:")
                print("   1. WhatsApp já está conectado")
                print("   2. Instância não foi criada ainda")
                print()
                print_info("Execute 'python test_evolution_gomobi.py status' para verificar")
                
        else:
            print_error(f"Erro ao obter QR Code: {response.status_code}")
            print(f"Resposta: {response.text}")
            
    except requests.exceptions.Timeout:
        print_error("Timeout ao conectar com a API")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Erro de conexão: {e}")
        
    except Exception as e:
        print_error(f"Erro inesperado: {e}")


def verificar_status():
    """Verifica o status da conexão com WhatsApp"""
    print_header("VERIFICAR STATUS DA CONEXÃO")
    
    print_info("Verificando conexão com WhatsApp...")
    print()
    
    try:
        url = f"{API_URL}/instance/connectionState/{INSTANCE_NAME}"
        
        response = requests.get(
            url,
            headers=get_headers(),
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if 'instance' in result:
                state = result['instance'].get('state', 'unknown')
                
                print("📊 Status da Conexão:")
                print(f"   Instância: {INSTANCE_NAME}")
                print(f"   Estado: {state}")
                print()
                
                if state == 'open':
                    print_success("WhatsApp está CONECTADO! 🎉")
                    print()
                    print_info("Próximo passo: Execute 'python test_evolution_gomobi.py enviar'")
                    
                elif state == 'close':
                    print_error("WhatsApp está DESCONECTADO")
                    print()
                    print_info("Execute 'python test_evolution_gomobi.py qrcode' para conectar")
                    
                else:
                    print_info(f"Estado atual: {state}")
                    print()
                    print_info("Execute 'python test_evolution_gomobi.py qrcode' para conectar")
                    
            else:
                print_error("Não foi possível obter o status")
                print(f"Resposta: {json.dumps(result, indent=2)}")
                
        elif response.status_code == 404:
            print_error("Instância não encontrada")
            print()
            print_info("Execute 'python test_evolution_gomobi.py criar' primeiro")
            
        else:
            print_error(f"Erro ao verificar status: {response.status_code}")
            print(f"Resposta: {response.text}")
            
    except requests.exceptions.Timeout:
        print_error("Timeout ao conectar com a API")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Erro de conexão: {e}")
        
    except Exception as e:
        print_error(f"Erro inesperado: {e}")


def enviar_mensagem():
    """Envia uma mensagem de teste"""
    print_header("ENVIAR MENSAGEM DE TESTE")
    
    print("Digite o número de telefone (com DDD, sem espaços):")
    print("Exemplo: 11999999999")
    print()
    
    telefone = input("📱 Telefone: ").strip()
    
    if not telefone:
        print_error("Telefone não pode estar vazio")
        return
    
    # Remove caracteres não numéricos
    telefone = ''.join(filter(str.isdigit, telefone))
    
    if len(telefone) < 10:
        print_error("Telefone inválido. Use o formato: 11999999999")
        return
    
    # Adiciona código do país se não tiver
    if not telefone.startswith('55'):
        telefone = '55' + telefone
    
    # Adiciona sufixo do WhatsApp
    telefone_whatsapp = telefone + '@s.whatsapp.net'
    
    print()
    print_info(f"Enviando mensagem para: {telefone}")
    print()
    
    mensagem = """🤖 *Mensagem de Teste - Go Mobi*

Olá! Se você recebeu esta mensagem, significa que a integração com WhatsApp está funcionando perfeitamente! ✅

Este é um teste automático do sistema Go Mobi.

_Mensagem enviada via Evolution API_"""
    
    try:
        url = f"{API_URL}/message/sendText/{INSTANCE_NAME}"
        
        data = {
            "number": telefone_whatsapp,
            "textMessage": {
                "text": mensagem
            }
        }
        
        response = requests.post(
            url,
            headers=get_headers(),
            json=data,
            timeout=30
        )
        
        if response.status_code == 201 or response.status_code == 200:
            print_success("Mensagem enviada com sucesso! 🎉")
            print()
            print_info("Verifique o WhatsApp no celular")
            
            result = response.json()
            if 'key' in result:
                print()
                print("📋 Detalhes do Envio:")
                print(f"   ID: {result['key'].get('id', 'N/A')}")
            
        else:
            print_error(f"Erro ao enviar mensagem: {response.status_code}")
            print(f"Resposta: {response.text}")
            print()
            print_info("Verifique se o WhatsApp está conectado: python test_evolution_gomobi.py status")
            
    except requests.exceptions.Timeout:
        print_error("Timeout ao enviar mensagem")
        
    except requests.exceptions.RequestException as e:
        print_error(f"Erro de conexão: {e}")
        
    except Exception as e:
        print_error(f"Erro inesperado: {e}")


def mostrar_ajuda():
    """Mostra ajuda com os comandos disponíveis"""
    print_header("TESTE DA EVOLUTION API - GO MOBI")
    
    print("📱 Este script testa a integração com WhatsApp")
    print()
    print("🔧 Comandos disponíveis:")
    print()
    print("  python test_evolution_gomobi.py criar    → Cria instância do WhatsApp")
    print("  python test_evolution_gomobi.py qrcode   → Obtém QR Code para conectar")
    print("  python test_evolution_gomobi.py status   → Verifica se está conectado")
    print("  python test_evolution_gomobi.py enviar   → Envia mensagem de teste")
    print()
    print("📋 Fluxo recomendado:")
    print()
    print("  1. python test_evolution_gomobi.py criar")
    print("  2. python test_evolution_gomobi.py qrcode")
    print("  3. Escaneie o QR Code com o WhatsApp")
    print("  4. python test_evolution_gomobi.py status")
    print("  5. python test_evolution_gomobi.py enviar")
    print()
    print("⚙️  Configuração atual:")
    print(f"   API URL: {API_URL}")
    print(f"   Instância: {INSTANCE_NAME}")
    print()


# ============================================
# MAIN
# ============================================

def main():
    """Função principal"""
    
    if len(sys.argv) < 2:
        mostrar_ajuda()
        return
    
    comando = sys.argv[1].lower()
    
    if comando == 'criar':
        criar_instancia()
    
    elif comando == 'qrcode':
        obter_qrcode()
    
    elif comando == 'status':
        verificar_status()
    
    elif comando == 'enviar':
        enviar_mensagem()
    
    elif comando in ['ajuda', 'help', '-h', '--help']:
        mostrar_ajuda()
    
    else:
        print_error(f"Comando desconhecido: {comando}")
        print()
        print("Use: python test_evolution_gomobi.py ajuda")


if __name__ == '__main__':
    main()

