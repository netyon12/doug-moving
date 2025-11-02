/**
 * Feedback Visual - Go Mobi
 * 
 * Funções globais para feedback visual em ações do sistema.
 * Usa SweetAlert2 para modais e toasts.
 * 
 * @author Go Mobi Team
 * @version 1.0
 */

// =============================================================================
// LOADING (Bloqueante)
// =============================================================================

/**
 * Mostra loading bloqueante com mensagem customizada
 * @param {string} message - Mensagem a ser exibida (padrão: "Processando...")
 */
function showLoading(message = 'Processando...') {
    Swal.fire({
        title: message,
        allowOutsideClick: false,
        allowEscapeKey: false,
        allowEnterKey: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
}

/**
 * Esconde loading bloqueante
 */
function hideLoading() {
    Swal.close();
}

// =============================================================================
// MENSAGENS MODAIS (Bloqueantes)
// =============================================================================

/**
 * Mostra mensagem de sucesso (modal bloqueante)
 * @param {string} message - Mensagem a ser exibida
 * @param {number} timer - Tempo em ms para fechar automaticamente (0 = não fecha)
 */
function showSuccess(message = 'Operação realizada com sucesso!', timer = 2000) {
    return Swal.fire({
        icon: 'success',
        title: 'Sucesso!',
        text: message,
        timer: timer,
        showConfirmButton: timer === 0,
        timerProgressBar: timer > 0
    });
}

/**
 * Mostra mensagem de erro (modal bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showError(message = 'Erro ao realizar operação') {
    return Swal.fire({
        icon: 'error',
        title: 'Erro',
        text: message,
        confirmButtonText: 'OK',
        confirmButtonColor: '#d33'
    });
}

/**
 * Mostra mensagem de aviso (modal bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showWarning(message) {
    return Swal.fire({
        icon: 'warning',
        title: 'Atenção',
        text: message,
        confirmButtonText: 'OK',
        confirmButtonColor: '#f0ad4e'
    });
}

/**
 * Mostra mensagem de informação (modal bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showInfo(message) {
    return Swal.fire({
        icon: 'info',
        title: 'Informação',
        text: message,
        confirmButtonText: 'OK'
    });
}

// =============================================================================
// CONFIRMAÇÕES
// =============================================================================

/**
 * Mostra modal de confirmação
 * @param {string} title - Título da confirmação
 * @param {string} text - Texto explicativo
 * @param {string} confirmButtonText - Texto do botão confirmar (padrão: "Sim, confirmar")
 * @returns {Promise} Promise que resolve com {isConfirmed: boolean}
 */
function showConfirm(title, text, confirmButtonText = 'Sim, confirmar') {
    return Swal.fire({
        title: title,
        text: text,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: confirmButtonText,
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        reverseButtons: true
    });
}

/**
 * Mostra modal de confirmação de exclusão
 * @param {string} itemName - Nome do item a ser excluído
 * @returns {Promise} Promise que resolve com {isConfirmed: boolean}
 */
function showDeleteConfirm(itemName = 'este item') {
    return Swal.fire({
        title: 'Tem certeza?',
        text: `Deseja realmente excluir ${itemName}? Esta ação não pode ser desfeita.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sim, excluir',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#d33',
        cancelButtonColor: '#6c757d',
        reverseButtons: true
    });
}

// =============================================================================
// TOAST NOTIFICATIONS (Não-bloqueantes)
// =============================================================================

/**
 * Configuração base para toasts
 */
const Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer);
        toast.addEventListener('mouseleave', Swal.resumeTimer);
    }
});

/**
 * Mostra toast de sucesso (não-bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showToastSuccess(message = 'Operação realizada com sucesso!') {
    Toast.fire({
        icon: 'success',
        title: message
    });
}

/**
 * Mostra toast de erro (não-bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showToastError(message = 'Erro ao realizar operação') {
    Toast.fire({
        icon: 'error',
        title: message
    });
}

/**
 * Mostra toast de aviso (não-bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showToastWarning(message) {
    Toast.fire({
        icon: 'warning',
        title: message
    });
}

/**
 * Mostra toast de informação (não-bloqueante)
 * @param {string} message - Mensagem a ser exibida
 */
function showToastInfo(message) {
    Toast.fire({
        icon: 'info',
        title: message
    });
}

// =============================================================================
// HELPERS PARA FORMULÁRIOS
// =============================================================================

/**
 * Mostra loading ao submeter formulário
 * @param {string} formId - ID do formulário
 * @param {string} message - Mensagem de loading (padrão: "Salvando...")
 */
function showFormLoading(formId, message = 'Salvando...') {
    showLoading(message);
}

/**
 * Processa resposta de AJAX de formulário
 * @param {object} response - Resposta do servidor
 * @param {string} successMessage - Mensagem de sucesso customizada
 * @param {string} redirectUrl - URL para redirecionar após sucesso (opcional)
 */
function handleFormResponse(response, successMessage = 'Salvo com sucesso!', redirectUrl = null) {
    hideLoading();
    
    if (response.success) {
        showSuccess(successMessage).then(() => {
            if (redirectUrl) {
                window.location.href = redirectUrl;
            }
        });
    } else {
        showError(response.message || 'Erro ao salvar');
    }
}

/**
 * Processa erro de AJAX de formulário
 * @param {object} xhr - Objeto XMLHttpRequest
 */
function handleFormError(xhr) {
    hideLoading();
    
    let errorMsg = 'Erro ao processar requisição. Tente novamente.';
    
    if (xhr.responseJSON && xhr.responseJSON.message) {
        errorMsg = xhr.responseJSON.message;
    } else if (xhr.status === 403) {
        errorMsg = 'Acesso negado. Você não tem permissão para realizar esta ação.';
    } else if (xhr.status === 404) {
        errorMsg = 'Recurso não encontrado.';
    } else if (xhr.status === 500) {
        errorMsg = 'Erro interno do servidor. Contate o administrador.';
    }
    
    console.error('Erro:', xhr);
    showError(errorMsg);
}

// =============================================================================
// EXEMPLO DE USO
// =============================================================================

/**
 * Exemplo de uso em formulário:
 * 
 * $('#formColaborador').on('submit', function(e) {
 *     e.preventDefault();
 *     
 *     showFormLoading('formColaborador', 'Salvando colaborador...');
 *     
 *     $.ajax({
 *         url: $(this).attr('action'),
 *         type: 'POST',
 *         data: $(this).serialize(),
 *         success: function(response) {
 *             handleFormResponse(response, 'Colaborador salvo!', '/colaboradores');
 *         },
 *         error: function(xhr) {
 *             handleFormError(xhr);
 *         }
 *     });
 * });
 * 
 * Exemplo de uso em botão de exclusão:
 * 
 * $('.btn-delete').on('click', function(e) {
 *     e.preventDefault();
 *     const itemId = $(this).data('id');
 *     const itemName = $(this).data('name');
 *     
 *     showDeleteConfirm(itemName).then((result) => {
 *         if (result.isConfirmed) {
 *             showLoading('Excluindo...');
 *             
 *             $.ajax({
 *                 url: `/colaboradores/${itemId}/delete`,
 *                 type: 'DELETE',
 *                 success: function(response) {
 *                     handleFormResponse(response, 'Excluído com sucesso!');
 *                     // Recarregar página ou remover linha da tabela
 *                     location.reload();
 *                 },
 *                 error: handleFormError
 *             });
 *         }
 *     });
 * });
 * 
 * Exemplo de uso de toast:
 * 
 * // Após ação rápida (não precisa bloquear tela)
 * showToastSuccess('Colaborador ativado!');
 * showToastWarning('Atenção: prazo próximo do vencimento');
 * showToastInfo('Nova mensagem recebida');
 */
