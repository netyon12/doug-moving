/**
 * JavaScript para Dashboard do Motorista
 * =======================================
 * 
 * Funcionalidades:
 * - KPIs expansíveis
 * - Ações de viagens (aceitar, cancelar, iniciar, finalizar)
 * - Toggle de disponibilidade
 * - Navegação para detalhes
 * 
 * Autor: Sistema Go Mobi (Doug Manus)
 * Data: 2025-11-12
 */

// ========================================================================
// KPIS EXPANSÍVEIS
// ========================================================================

/**
 * Expande ou recolhe detalhes de um KPI
 * @param {string} kpiId - ID do KPI (agendadas, andamento, finalizadas, disponiveis)
 */
function toggleKPI(kpiId) {
    const detalhes = document.getElementById(`kpi-${kpiId}`);
    const icon = document.getElementById(`icon-${kpiId}`);
    const card = document.getElementById(`kpi-card-${kpiId}`);
    
    if (!detalhes || !icon || !card) {
        console.error(`Elementos do KPI ${kpiId} não encontrados`);
        return;
    }
    
    if (detalhes.classList.contains('show')) {
        // Recolher
        detalhes.classList.remove('show');
        card.classList.remove('expanded');
        
        // Log para debug
        console.log(`KPI ${kpiId} recolhido`);
    } else {
        // Expandir
        detalhes.classList.add('show');
        card.classList.add('expanded');
        
        // Log para debug
        console.log(`KPI ${kpiId} expandido`);
    }
}

// ========================================================================
// NAVEGAÇÃO
// ========================================================================

/**
 * Navega para página de detalhes da viagem
 * @param {number} viagemId - ID da viagem
 */
function verDetalhesViagem(viagemId) {
    if (!viagemId) {
        console.error('ID da viagem não fornecido');
        return;
    }
    
    console.log(`Navegando para detalhes da viagem #${viagemId}`);
    window.location.href = `/motorista/viagens/${viagemId}`;
}

// ========================================================================
// AÇÕES DE VIAGENS
// ========================================================================

/**
 * Aceita uma viagem disponível
 * @param {number} viagemId - ID da viagem
 */
function aceitarViagem(viagemId) {
    if (!viagemId) {
        console.error('ID da viagem não fornecido');
        return;
    }
    
    if (!confirm('Deseja aceitar esta viagem?')) {
        return;
    }
    
    console.log(`Aceitando viagem #${viagemId}...`);
    
    fetch(`/motorista/viagens/${viagemId}/aceitar`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Viagem aceita com sucesso');
            alert('Viagem aceita com sucesso!');
            location.reload();
        } else {
            console.error('Erro ao aceitar viagem:', data.message);
            alert('Erro ao aceitar viagem: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
        alert('Erro ao aceitar viagem. Verifique sua conexão.');
    });
}

/**
 * Cancela uma viagem agendada
 * @param {number} viagemId - ID da viagem
 */
function cancelarViagem(viagemId) {
    if (!viagemId) {
        console.error('ID da viagem não fornecido');
        return;
    }
    
    if (!confirm('Deseja realmente cancelar esta viagem?')) {
        return;
    }
    
    console.log(`Cancelando viagem #${viagemId}...`);
    
    fetch(`/motorista/viagens/${viagemId}/cancelar`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Viagem cancelada com sucesso');
            alert('Viagem cancelada com sucesso!');
            location.reload();
        } else {
            console.error('Erro ao cancelar viagem:', data.message);
            alert('Erro ao cancelar viagem: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
        alert('Erro ao cancelar viagem. Verifique sua conexão.');
    });
}

/**
 * Inicia uma viagem agendada
 * @param {number} viagemId - ID da viagem
 */
function iniciarViagem(viagemId) {
    if (!viagemId) {
        console.error('ID da viagem não fornecido');
        return;
    }
    
    if (!confirm('Deseja iniciar esta viagem?')) {
        return;
    }
    
    console.log(`Iniciando viagem #${viagemId}...`);
    
    fetch(`/motorista/viagens/${viagemId}/iniciar`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Viagem iniciada com sucesso');
            alert('Viagem iniciada com sucesso!');
            location.reload();
        } else {
            console.error('Erro ao iniciar viagem:', data.message);
            alert('Erro ao iniciar viagem: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
        alert('Erro ao iniciar viagem. Verifique sua conexão.');
    });
}

/**
 * Finaliza uma viagem em andamento
 * @param {number} viagemId - ID da viagem
 */
function finalizarViagem(viagemId) {
    if (!viagemId) {
        console.error('ID da viagem não fornecido');
        return;
    }
    
    if (!confirm('Deseja finalizar esta viagem?')) {
        return;
    }
    
    console.log(`Finalizando viagem #${viagemId}...`);
    
    fetch(`/motorista/viagens/${viagemId}/finalizar`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Viagem finalizada com sucesso');
            alert('Viagem finalizada com sucesso!');
            location.reload();
        } else {
            console.error('Erro ao finalizar viagem:', data.message);
            alert('Erro ao finalizar viagem: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
        alert('Erro ao finalizar viagem. Verifique sua conexão.');
    });
}

// ========================================================================
// DISPONIBILIDADE DO MOTORISTA
// ========================================================================

/**
 * Alterna status de disponibilidade do motorista (online/offline)
 */
function toggleDisponibilidade() {
    console.log('Alternando disponibilidade...');
    
    fetch('/motorista/toggle_disponibilidade', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Disponibilidade alterada:', data.message);
            alert(data.message);
            location.reload();
        } else {
            console.error('Erro ao alterar disponibilidade:', data.message);
            alert('Erro ao alterar disponibilidade: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Erro na requisição:', error);
        alert('Erro ao alterar disponibilidade. Verifique sua conexão.');
    });
}

// ========================================================================
// UTILITÁRIOS
// ========================================================================

/**
 * Formata valor monetário para exibição
 * @param {number} valor - Valor numérico
 * @returns {string} Valor formatado (ex: "R$ 58,00")
 */
function formatarValor(valor) {
    if (!valor || isNaN(valor)) {
        return 'R$ 0,00';
    }
    
    return 'R$ ' + parseFloat(valor).toFixed(2).replace('.', ',');
}

/**
 * Formata horário para exibição
 * @param {string} horario - Horário no formato HH:MM:SS
 * @returns {string} Horário formatado (ex: "12:10")
 */
function formatarHorario(horario) {
    if (!horario) {
        return 'N/A';
    }
    
    // Se já está no formato HH:MM, retorna direto
    if (horario.length === 5 && horario.includes(':')) {
        return horario;
    }
    
    // Se está no formato HH:MM:SS, remove os segundos
    if (horario.length === 8 && horario.includes(':')) {
        return horario.substring(0, 5);
    }
    
    return horario;
}

/**
 * Obtém cor do badge baseado no tipo de corrida
 * @param {string} tipo - Tipo de corrida (entrada, saida, desligamento)
 * @returns {string} Classe CSS para o badge
 */
function getCorTipoCorrida(tipo) {
    const tipos = {
        'entrada': 'entrada',
        'saida': 'saida',
        'desligamento': 'desligamento'
    };
    
    return tipos[tipo.toLowerCase()] || 'entrada';
}

/**
 * Obtém cor do status da viagem
 * @param {string} status - Status da viagem
 * @returns {string} Classe CSS para o status
 */
function getCorStatus(status) {
    const statusMap = {
        'pendente': 'status-pendente',
        'agendada': 'status-agendada',
        'em andamento': 'status-em-andamento',
        'finalizada': 'status-finalizada',
        'cancelada': 'status-cancelada'
    };
    
    return statusMap[status.toLowerCase()] || 'status-pendente';
}

// ========================================================================
// INICIALIZAÇÃO
// ========================================================================

/**
 * Inicializa o dashboard quando a página carrega
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard do Motorista carregado');
    
    // Adiciona listeners para eventos de teclado (acessibilidade)
    document.querySelectorAll('.stat-card-mobile').forEach(card => {
        card.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                card.click();
            }
        });
    });
    
    // Log de estatísticas para debug
    const stats = {
        agendadas: document.querySelector('.stat-agendadas .stat-value')?.textContent,
        andamento: document.querySelector('.stat-andamento .stat-value')?.textContent,
        finalizadas: document.querySelector('.stat-finalizadas .stat-value')?.textContent,
        disponiveis: document.querySelector('.stat-disponiveis .stat-value')?.textContent
    };
    
    console.log('Estatísticas:', stats);
    
    // Adiciona atributo tabindex para acessibilidade
    document.querySelectorAll('.stat-card-mobile').forEach((card, index) => {
        card.setAttribute('tabindex', index + 1);
        card.setAttribute('role', 'button');
        card.setAttribute('aria-expanded', 'false');
    });
    
    console.log('Dashboard inicializado com sucesso');
});

// ========================================================================
// TRATAMENTO DE ERROS GLOBAL
// ========================================================================

/**
 * Captura erros não tratados
 */
window.addEventListener('error', function(e) {
    console.error('Erro não tratado:', e.error);
});

/**
 * Captura promessas rejeitadas não tratadas
 */
window.addEventListener('unhandledrejection', function(e) {
    console.error('Promise rejeitada não tratada:', e.reason);
});

// ========================================================================
// EXPORTAÇÕES (para uso em outros scripts, se necessário)
// ========================================================================

// Torna funções disponíveis globalmente
window.dashboardMotorista = {
    toggleKPI,
    verDetalhesViagem,
    aceitarViagem,
    cancelarViagem,
    iniciarViagem,
    finalizarViagem,
    toggleDisponibilidade,
    formatarValor,
    formatarHorario,
    getCorTipoCorrida,
    getCorStatus
};

console.log('motorista_dashboard.js carregado');
