-- ============================================
-- MIGRAÇÃO: Módulo Financeiro
-- Data: 2024-10-13
-- Descrição: Criação das tabelas para Contas a Receber e Contas a Pagar
-- ============================================

-- Tabela: Contas a Receber (Títulos das Empresas)
CREATE TABLE IF NOT EXISTS fin_contas_receber (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_titulo VARCHAR(50) UNIQUE NOT NULL,
    empresa_id INTEGER NOT NULL,
    valor_total DECIMAL(10, 2) NOT NULL,
    data_emissao DATE NOT NULL,
    data_vencimento DATE NOT NULL,
    data_recebimento DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'Aberto',  -- Aberto, Recebido, Vencido, Cancelado
    numero_nota_fiscal VARCHAR(100),
    observacoes TEXT,
    created_by_user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresa(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);

-- Tabela: Viagens vinculadas ao título a receber
CREATE TABLE IF NOT EXISTS fin_receber_viagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_receber_id INTEGER NOT NULL,
    viagem_id INTEGER NOT NULL,
    valor_viagem DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conta_receber_id) REFERENCES fin_contas_receber(id) ON DELETE CASCADE,
    FOREIGN KEY (viagem_id) REFERENCES viagem(id),
    UNIQUE(conta_receber_id, viagem_id)  -- Evita duplicação
);

-- Tabela: Contas a Pagar (Títulos dos Motoristas)
CREATE TABLE IF NOT EXISTS fin_contas_pagar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_titulo VARCHAR(50) UNIQUE NOT NULL,
    motorista_id INTEGER NOT NULL,
    valor_total DECIMAL(10, 2) NOT NULL,
    data_emissao DATE NOT NULL,
    data_vencimento DATE NOT NULL,
    data_pagamento DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'Aberto',  -- Aberto, Pago, Vencido, Cancelado
    forma_pagamento VARCHAR(50),  -- PIX, Transferência, Dinheiro, etc.
    comprovante_pagamento VARCHAR(255),  -- Caminho do arquivo
    observacoes TEXT,
    created_by_user_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (motorista_id) REFERENCES motorista(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);

-- Tabela: Viagens vinculadas ao título a pagar
CREATE TABLE IF NOT EXISTS fin_pagar_viagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_pagar_id INTEGER NOT NULL,
    viagem_id INTEGER NOT NULL,
    valor_repasse DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conta_pagar_id) REFERENCES fin_contas_pagar(id) ON DELETE CASCADE,
    FOREIGN KEY (viagem_id) REFERENCES viagem(id),
    UNIQUE(conta_pagar_id, viagem_id)  -- Evita duplicação
);

-- Índices para melhorar performance
CREATE INDEX IF NOT EXISTS idx_fin_receber_empresa ON fin_contas_receber(empresa_id);
CREATE INDEX IF NOT EXISTS idx_fin_receber_status ON fin_contas_receber(status);
CREATE INDEX IF NOT EXISTS idx_fin_receber_vencimento ON fin_contas_receber(data_vencimento);

CREATE INDEX IF NOT EXISTS idx_fin_pagar_motorista ON fin_contas_pagar(motorista_id);
CREATE INDEX IF NOT EXISTS idx_fin_pagar_status ON fin_contas_pagar(status);
CREATE INDEX IF NOT EXISTS idx_fin_pagar_vencimento ON fin_contas_pagar(data_vencimento);

CREATE INDEX IF NOT EXISTS idx_fin_receber_viagens_conta ON fin_receber_viagens(conta_receber_id);
CREATE INDEX IF NOT EXISTS idx_fin_receber_viagens_viagem ON fin_receber_viagens(viagem_id);

CREATE INDEX IF NOT EXISTS idx_fin_pagar_viagens_conta ON fin_pagar_viagens(conta_pagar_id);
CREATE INDEX IF NOT EXISTS idx_fin_pagar_viagens_viagem ON fin_pagar_viagens(viagem_id);

-- ============================================
-- FIM DA MIGRAÇÃO
-- ============================================

