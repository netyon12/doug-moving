#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
CRIAR TABELAS EM NOVO BANCO DE DADOS
=============================================================================

Este script cria todas as tabelas necessárias em um novo banco de dados
para uma nova empresa do sistema Go Mobi.

USO:
    python criar_tabelas_novo_banco.py

O script irá solicitar:
    1. Host do banco (ex: dpg-xxx.render.com)
    2. Nome do banco (ex: db_nsg_homolog)
    3. Usuário do banco
    4. Senha do banco
    5. Porta (padrão: 5432)

IMPORTANTE:
    - O banco de dados já deve existir no servidor (apenas vazio)
    - Execute este script na pasta raiz do projeto
    - Certifique-se de ter as dependências instaladas (psycopg2, sqlalchemy)

=============================================================================
"""

import sys
import os

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import getpass


def print_header():
    """Exibe cabeçalho do script."""
    print("\n" + "=" * 70)
    print("  🏗️  CRIAR TABELAS EM NOVO BANCO DE DADOS - GO MOBI")
    print("=" * 70)
    print()


def get_connection_info():
    """Solicita informações de conexão ao usuário."""
    print("📝 Informe os dados de conexão do NOVO banco:\n")
    
    db_host = input("   Host do banco (ex: dpg-xxx.render.com): ").strip()
    db_name = input("   Nome do banco (ex: db_nsg_homolog): ").strip()
    db_user = input("   Usuário do banco: ").strip()
    db_pass = getpass.getpass("   Senha do banco: ").strip()
    db_port = input("   Porta (pressione Enter para 5432): ").strip() or "5432"
    
    return {
        'host': db_host,
        'name': db_name,
        'user': db_user,
        'password': db_pass,
        'port': db_port
    }


def test_connection(db_info):
    """Testa a conexão com o banco de dados."""
    print("\n🔄 Testando conexão...")
    
    db_url = f"postgresql://{db_info['user']}:{db_info['password']}@{db_info['host']}:{db_info['port']}/{db_info['name']}"
    
    try:
        engine = create_engine(db_url, echo=False)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("✅ Conexão estabelecida com sucesso!")
        return engine
    except Exception as e:
        print(f"❌ Erro ao conectar: {str(e)}")
        return None


def get_all_tables_ddl():
    """Retorna o DDL de todas as tabelas do sistema."""
    
    # DDL das tabelas na ordem correta (respeitando foreign keys)
    ddl = """
-- ============================================================
-- TABELAS DO SISTEMA GO MOBI
-- Gerado automaticamente pelo script criar_tabelas_novo_banco.py
-- ============================================================

-- 1. Tabela de Empresa (base para todas as outras)
CREATE TABLE IF NOT EXISTS empresa (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    cnpj VARCHAR(20),
    endereco VARCHAR(300),
    telefone VARCHAR(20),
    email VARCHAR(100),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Campos Multi-Tenant
    slug_licenciado VARCHAR(50) UNIQUE,
    is_banco_local BOOLEAN DEFAULT TRUE,
    db_host VARCHAR(255),
    db_port INTEGER DEFAULT 5432,
    db_name VARCHAR(100),
    db_user VARCHAR(100),
    db_pass VARCHAR(255)
);

-- 2. Tabela de Usuários
CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    email VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'colaborador',
    nome VARCHAR(200),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    empresa_id INTEGER REFERENCES empresa(id),
    empresas_acesso TEXT
);

-- 3. Tabela de Plantas
CREATE TABLE IF NOT EXISTS planta (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabela de Centro de Custo
CREATE TABLE IF NOT EXISTS centro_custo (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50),
    nome VARCHAR(200) NOT NULL,
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Tabela de Turnos
CREATE TABLE IF NOT EXISTS turno (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    horario_inicio TIME,
    horario_fim TIME,
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Tabela de Blocos
CREATE TABLE IF NOT EXISTS bloco (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    planta_id INTEGER REFERENCES planta(id),
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Tabela de Bairros
CREATE TABLE IF NOT EXISTS bairro (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    cidade VARCHAR(100),
    uf VARCHAR(2),
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Tabela de Gerentes
CREATE TABLE IF NOT EXISTS gerente (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id),
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(150),
    telefone VARCHAR(20),
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Tabela de Supervisores
CREATE TABLE IF NOT EXISTS supervisor (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id),
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(150),
    telefone VARCHAR(20),
    gerente_id INTEGER REFERENCES gerente(id),
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Tabela de Colaboradores
CREATE TABLE IF NOT EXISTS colaborador (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id),
    matricula VARCHAR(50),
    nome VARCHAR(200) NOT NULL,
    cpf VARCHAR(14),
    email VARCHAR(150),
    telefone VARCHAR(20),
    endereco VARCHAR(300),
    bairro VARCHAR(100),
    cidade VARCHAR(100),
    uf VARCHAR(2),
    cep VARCHAR(10),
    centro_custo_id INTEGER REFERENCES centro_custo(id),
    turno_id INTEGER REFERENCES turno(id),
    bloco_id INTEGER REFERENCES bloco(id),
    supervisor_id INTEGER REFERENCES supervisor(id),
    empresa_id INTEGER REFERENCES empresa(id),
    status VARCHAR(20) DEFAULT 'Ativo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Tabela de Motoristas
CREATE TABLE IF NOT EXISTS motorista (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id),
    nome VARCHAR(200) NOT NULL,
    cpf_cnpj VARCHAR(20),
    endereco VARCHAR(300),
    nro VARCHAR(20),
    bairro VARCHAR(100),
    cidade VARCHAR(100),
    uf VARCHAR(2),
    telefone VARCHAR(20),
    email VARCHAR(150),
    chave_pix VARCHAR(100),
    status VARCHAR(20) DEFAULT 'Ativo',
    -- Campos do veículo
    veiculo_nome VARCHAR(100),
    veiculo_placa VARCHAR(10),
    veiculo_cor VARCHAR(50),
    veiculo_ano INTEGER,
    veiculo_km DECIMAL(10,2),
    veiculo_obs TEXT,
    -- Campos Multi-Tenant
    empresas_acesso TEXT,
    empresa_padrao_slug VARCHAR(50),
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. Tabela de Solicitações
CREATE TABLE IF NOT EXISTS solicitacao (
    id SERIAL PRIMARY KEY,
    colaborador_id INTEGER REFERENCES colaborador(id),
    tipo_corrida VARCHAR(50),
    data_viagem DATE,
    horario_entrada TIME,
    horario_saida TIME,
    horario_desligamento TIME,
    origem VARCHAR(300),
    destino VARCHAR(300),
    observacao TEXT,
    status VARCHAR(50) DEFAULT 'Pendente',
    solicitante VARCHAR(200),
    viagem_id INTEGER,
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Tabela de Viagens
CREATE TABLE IF NOT EXISTS viagem (
    id SERIAL PRIMARY KEY,
    motorista_id INTEGER REFERENCES motorista(id),
    data_viagem DATE,
    horario_entrada TIME,
    horario_saida TIME,
    horario_desligamento TIME,
    tipo_corrida VARCHAR(50),
    origem VARCHAR(300),
    destino VARCHAR(300),
    km_inicial DECIMAL(10,2),
    km_final DECIMAL(10,2),
    km_total DECIMAL(10,2),
    valor_km DECIMAL(10,2),
    valor_total DECIMAL(10,2),
    valor_pedagio DECIMAL(10,2),
    valor_estacionamento DECIMAL(10,2),
    observacao TEXT,
    status VARCHAR(50) DEFAULT 'Pendente',
    data_inicio TIMESTAMP,
    data_finalizacao TIMESTAMP,
    planta_id INTEGER REFERENCES planta(id),
    bloco_id INTEGER REFERENCES bloco(id),
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. Atualizar foreign key de solicitacao para viagem
ALTER TABLE solicitacao 
ADD CONSTRAINT fk_solicitacao_viagem 
FOREIGN KEY (viagem_id) REFERENCES viagem(id) 
ON DELETE SET NULL;

-- 15. Tabela de Viagem Hora Parada
CREATE TABLE IF NOT EXISTS viagem_hora_parada (
    id SERIAL PRIMARY KEY,
    viagem_id INTEGER REFERENCES viagem(id),
    hora_inicio TIME,
    hora_fim TIME,
    motivo VARCHAR(200),
    observacao TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 16. Tabela de Configurações
CREATE TABLE IF NOT EXISTS configuracao (
    id SERIAL PRIMARY KEY,
    chave VARCHAR(100) UNIQUE NOT NULL,
    valor TEXT,
    descricao VARCHAR(300),
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 17. Tabela de Auditoria
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    user_email VARCHAR(150),
    action VARCHAR(100),
    table_name VARCHAR(100),
    record_id INTEGER,
    old_values TEXT,
    new_values TEXT,
    ip_address VARCHAR(50),
    user_agent TEXT,
    empresa_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 18. Tabela de Auditoria de Viagens
CREATE TABLE IF NOT EXISTS viagem_auditoria (
    id SERIAL PRIMARY KEY,
    viagem_id INTEGER REFERENCES viagem(id),
    user_id INTEGER,
    user_email VARCHAR(150),
    acao VARCHAR(100),
    campo_alterado VARCHAR(100),
    valor_anterior TEXT,
    valor_novo TEXT,
    observacao TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 19. Tabela de Fretados
CREATE TABLE IF NOT EXISTS fretado (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    tipo VARCHAR(50),
    capacidade INTEGER,
    placa VARCHAR(10),
    motorista_id INTEGER REFERENCES motorista(id),
    rota TEXT,
    horario_saida TIME,
    horario_retorno TIME,
    dias_semana VARCHAR(50),
    valor_mensal DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'Ativo',
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 20. Tabela de Contas a Receber
CREATE TABLE IF NOT EXISTS fin_contas_receber (
    id SERIAL PRIMARY KEY,
    descricao VARCHAR(300),
    valor DECIMAL(10,2),
    data_vencimento DATE,
    data_recebimento DATE,
    status VARCHAR(50) DEFAULT 'Pendente',
    observacao TEXT,
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 21. Tabela de Contas a Pagar
CREATE TABLE IF NOT EXISTS fin_contas_pagar (
    id SERIAL PRIMARY KEY,
    descricao VARCHAR(300),
    valor DECIMAL(10,2),
    data_vencimento DATE,
    data_pagamento DATE,
    status VARCHAR(50) DEFAULT 'Pendente',
    motorista_id INTEGER REFERENCES motorista(id),
    observacao TEXT,
    empresa_id INTEGER REFERENCES empresa(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 22. Tabelas de Associação (Many-to-Many)

-- Gerente-Planta
CREATE TABLE IF NOT EXISTS gerente_planta (
    gerente_id INTEGER REFERENCES gerente(id),
    planta_id INTEGER REFERENCES planta(id),
    PRIMARY KEY (gerente_id, planta_id)
);

-- Supervisor-Bloco
CREATE TABLE IF NOT EXISTS supervisor_bloco (
    supervisor_id INTEGER REFERENCES supervisor(id),
    bloco_id INTEGER REFERENCES bloco(id),
    PRIMARY KEY (supervisor_id, bloco_id)
);

-- Colaborador-Bairro
CREATE TABLE IF NOT EXISTS colaborador_bairro (
    colaborador_id INTEGER REFERENCES colaborador(id),
    bairro_id INTEGER REFERENCES bairro(id),
    PRIMARY KEY (colaborador_id, bairro_id)
);

-- Viagem-Solicitacao
CREATE TABLE IF NOT EXISTS viagem_solicitacao (
    viagem_id INTEGER REFERENCES viagem(id),
    solicitacao_id INTEGER REFERENCES solicitacao(id),
    PRIMARY KEY (viagem_id, solicitacao_id)
);

-- ============================================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_viagem_data ON viagem(data_viagem);
CREATE INDEX IF NOT EXISTS idx_viagem_status ON viagem(status);
CREATE INDEX IF NOT EXISTS idx_viagem_motorista ON viagem(motorista_id);
CREATE INDEX IF NOT EXISTS idx_viagem_empresa ON viagem(empresa_id);

CREATE INDEX IF NOT EXISTS idx_solicitacao_data ON solicitacao(data_viagem);
CREATE INDEX IF NOT EXISTS idx_solicitacao_status ON solicitacao(status);
CREATE INDEX IF NOT EXISTS idx_solicitacao_empresa ON solicitacao(empresa_id);

CREATE INDEX IF NOT EXISTS idx_colaborador_empresa ON colaborador(empresa_id);
CREATE INDEX IF NOT EXISTS idx_motorista_empresa ON motorista(empresa_id);
CREATE INDEX IF NOT EXISTS idx_motorista_cpf ON motorista(cpf_cnpj);

CREATE INDEX IF NOT EXISTS idx_user_email ON "user"(email);
CREATE INDEX IF NOT EXISTS idx_user_role ON "user"(role);

-- ============================================================
-- FIM DO SCRIPT
-- ============================================================
"""
    return ddl


def create_tables(engine):
    """Cria todas as tabelas no banco de dados."""
    print("\n🔄 Criando tabelas...")
    
    ddl = get_all_tables_ddl()
    
    try:
        with engine.begin() as conn:  # Usar begin() para transação automática
            # Executar DDL completo de uma vez
            conn.execute(text(ddl))
            
            print("\n✅ Todas as tabelas criadas com sucesso!")
            return True
            
    except Exception as e:
        error_msg = str(e)
        
        # Se o erro for sobre tabelas já existentes, tentar criar individualmente
        if 'already exists' in error_msg.lower():
            print("\n⚠️  Algumas tabelas já existem. Criando as faltantes...")
            return create_tables_individually(engine, ddl)
        else:
            print(f"❌ Erro ao criar tabelas: {error_msg}")
            return False


def create_tables_individually(engine, ddl):
    """Cria tabelas individualmente (fallback)."""
    statements = ddl.split(';')
    count_success = 0
    count_skip = 0
    count_error = 0
    
    with engine.begin() as conn:
        for statement in statements:
            statement = statement.strip()
            if not statement or statement.startswith('--'):
                continue
            
            try:
                conn.execute(text(statement))
                count_success += 1
                
                # Mostrar progresso
                if 'CREATE TABLE' in statement.upper():
                    table_name = statement.split('EXISTS')[1].split('(')[0].strip() if 'EXISTS' in statement else 'tabela'
                    print(f"   ✅ Criada: {table_name}")
                elif 'CREATE INDEX' in statement.upper():
                    print(f"   ✅ Índice criado")
                    
            except Exception as e:
                error_msg = str(e)
                if 'already exists' in error_msg.lower():
                    count_skip += 1
                else:
                    count_error += 1
                    if 'does not exist' not in error_msg.lower():  # Ignorar erros de tabela não existe para índices
                        print(f"   ⚠️  Erro: {error_msg[:100]}")
    
    print(f"\n✅ Sucesso: {count_success} | ⚠️  Já existiam: {count_skip} | ❌ Erros: {count_error}")
    return count_success > 0 or count_skip > 0


def verify_tables(engine):
    """Verifica as tabelas criadas."""
    print("\n🔍 Verificando tabelas criadas...")
    
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Tabelas encontradas ({len(tables)}):")
        for table in sorted(tables):
            print(f"   • {table}")
        
        return len(tables) > 0
        
    except Exception as e:
        print(f"❌ Erro ao verificar tabelas: {str(e)}")
        return False


def main():
    """Função principal."""
    print_header()
    
    # 1. Obter informações de conexão
    db_info = get_connection_info()
    
    # 2. Testar conexão
    engine = test_connection(db_info)
    if not engine:
        print("\n❌ Não foi possível conectar ao banco. Verifique as credenciais.")
        sys.exit(1)
    
    # 3. Confirmar criação
    print("\n" + "-" * 50)
    print(f"📦 Banco: {db_info['name']}")
    print(f"🖥️  Host: {db_info['host']}")
    print("-" * 50)
    
    confirm = input("\n⚠️  Deseja criar as tabelas neste banco? (s/n): ").strip().lower()
    if confirm != 's':
        print("\n❌ Operação cancelada pelo usuário.")
        sys.exit(0)
    
    # 4. Criar tabelas
    success = create_tables(engine)
    
    if success:
        # 5. Verificar tabelas
        verify_tables(engine)
        
        print("\n" + "=" * 70)
        print("  ✅ TABELAS CRIADAS COM SUCESSO!")
        print("=" * 70)
        print("\n📝 Próximos passos:")
        print("   1. Acesse o sistema como Admin")
        print("   2. Configure a empresa no cadastro de empresas")
        print("   3. Comece a cadastrar os dados (plantas, blocos, etc.)")
        print()
    else:
        print("\n❌ Houve erros na criação das tabelas. Verifique os logs acima.")
        sys.exit(1)


if __name__ == '__main__':
    main()
