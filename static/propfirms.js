// ============================================================================
// ANÁLISIS PROPFIRMS
// ============================================================================

let propfirmEAs = [];
let propfirmHistory = [];
let propfirmConfig = {
    capital: 100000,
    risk: 2500,
    threshold1: 8,
    threshold2: 5,
    ddDaily: 5,
    ddMax: 10
};

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
function initPropfirms() {
    console.log('🎯 Inicializando Análisis Propfirms...');
    
    // Cargar EAs desde localStorage
    const saved = localStorage.getItem('propfirmEAs');
    if (saved) {
        propfirmEAs = JSON.parse(saved);
        renderPropfirmEAsList();
    }
    
    // ✅ CARGAR HISTORIAL
    const savedHistory = localStorage.getItem('propfirmHistory');
    if (savedHistory) {
        propfirmHistory = JSON.parse(savedHistory);
        loadLastSimulation(); // Cargar última simulación automáticamente
    }
    
    // Marcar capital seleccionado por defecto (100k)
    document.querySelectorAll('.capital-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-cyan-600');
        btn.classList.add('bg-gray-800');
        if (btn.textContent.trim() === '100k') {
            btn.classList.add('active', 'bg-cyan-600');
            btn.classList.remove('bg-gray-800');
        }
    });
    
    // Marcar riesgo seleccionado por defecto (2500)
    document.querySelectorAll('.risk-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-cyan-600');
        btn.classList.add('bg-gray-800');
        if (btn.textContent.trim() === '$2500') {
            btn.classList.add('active', 'bg-cyan-600');
            btn.classList.remove('bg-gray-800');
        }
    });
    
    renderHistorySelector(); 
}
// ============================================================================
// SELECCIÓN DE CAPITAL Y RIESGO
// ============================================================================
function selectCapital(amount, event) {
    propfirmConfig.capital = amount;
    document.getElementById('selectedCapital').value = amount;
    
    // Actualizar UI - Desactivar todos
    document.querySelectorAll('.capital-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-cyan-600');
        btn.classList.add('bg-gray-800');
    });
    
    // Activar el clicado
    event.target.classList.remove('bg-gray-800');
    event.target.classList.add('active', 'bg-cyan-600');
    
    console.log(`💰 Capital seleccionado: $${amount}`);
}

function selectRisk(amount, event) {
    propfirmConfig.risk = amount;
    document.getElementById('selectedRisk').value = amount;
    
    // Actualizar UI - Desactivar todos
    document.querySelectorAll('.risk-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-cyan-600');
        btn.classList.add('bg-gray-800');
    });
    
    // Activar el clicado
    event.target.classList.remove('bg-gray-800');
    event.target.classList.add('active', 'bg-cyan-600');
    
    // Limpiar input personalizado
    document.getElementById('customRisk').value = '';
    
    console.log(`⚠️ Riesgo seleccionado: $${amount}`);
}

function selectCustomRisk() {
    const customValue = parseFloat(document.getElementById('customRisk').value);
    
    if (!customValue || customValue <= 0) {
        showNotification('Introduce un valor válido', 'warning');
        return;
    }
    
    propfirmConfig.risk = customValue;
    document.getElementById('selectedRisk').value = customValue;
    
    // Desactivar botones predefinidos
    document.querySelectorAll('.risk-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-cyan-600');
        btn.classList.add('bg-gray-800');
    });
    
    console.log(`⚠️ Riesgo personalizado: $${customValue}`);
    showNotification(`Riesgo configurado: $${customValue}`, 'success');
}

function applyThresholds() {
    propfirmConfig.threshold1 = parseFloat(document.getElementById('threshold1').value);
    propfirmConfig.threshold2 = parseFloat(document.getElementById('threshold2').value);
    propfirmConfig.ddDaily = parseFloat(document.getElementById('ddDaily').value);
    propfirmConfig.ddMax = parseFloat(document.getElementById('ddMax').value);
    
    console.log('✅ Umbrales aplicados:', propfirmConfig);
    showNotification('Umbrales aplicados correctamente', 'success');
}

// ============================================================================
// GESTIÓN DE EAs
// ============================================================================
function addToPropfirm(magicNumber) {
    // Verificar si ya está en la lista
    if (propfirmEAs.find(ea => ea.magic_number === magicNumber)) {
        showNotification('Este EA ya está en la lista de Propfirms', 'warning');
        return;
    }
    
    // Obtener datos del EA
    fetch(`/api/ea/detailed-stats/${magicNumber}`)
        .then(response => response.json())
        .then(async stats => {
            // Obtener info adicional
            const response = await fetch(`/api/ea/info/${magicNumber}`);
            const info = await response.json();
            
            const ea = {
                magic_number: magicNumber,
                name: info.caracteristicas || `EA ${magicNumber}`,
                rr_ratio: stats.rr_ratio || 0
            };
            
            propfirmEAs.push(ea);
            localStorage.setItem('propfirmEAs', JSON.stringify(propfirmEAs));
            renderPropfirmEAsList();
            
            showNotification(`EA ${magicNumber} añadido a Análisis Propfirms`, 'success');
        })
        .catch(error => {
            console.error('Error añadiendo EA:', error);
            showNotification('Error añadiendo EA', 'error');
        });
}

function removeFromPropfirm(magicNumber) {
    propfirmEAs = propfirmEAs.filter(ea => ea.magic_number !== magicNumber);
    localStorage.setItem('propfirmEAs', JSON.stringify(propfirmEAs));
    renderPropfirmEAsList();
    
    showNotification(`EA ${magicNumber} eliminado`, 'info');
}

function clearPropfirmList() {
    if (propfirmEAs.length === 0) {
        showNotification('La lista ya está vacía', 'info');
        return;
    }
    
    if (confirm('¿Estás seguro de que quieres limpiar toda la lista?')) {
        propfirmEAs = [];
        localStorage.setItem('propfirmEAs', JSON.stringify(propfirmEAs));
        renderPropfirmEAsList();
        
        // Ocultar resultados
        document.getElementById('propfirmResults').classList.add('hidden');
        
        showNotification('Lista limpiada', 'success');
    }
}

function renderPropfirmEAsList() {
    const tbody = document.getElementById('propfirmEAsTableBody');
    
    if (!tbody) return;
    
    if (propfirmEAs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="4" class="text-center p-8 text-gray-500">
                    <i class="fas fa-inbox text-4xl mb-2"></i>
                    <p>No hay EAs seleccionados</p>
                    <p class="text-sm mt-2">Ve a Características Técnicas y añade EAs</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = propfirmEAs.map(ea => `
        <tr class="border-b border-gray-800 hover:bg-gray-800">
            <td class="text-left p-2 text-cyan-400 font-semibold">${ea.name}</td>
            <td class="text-center p-2 text-white">${ea.magic_number}</td>
            <td class="text-center p-2 text-yellow-400">${ea.rr_ratio.toFixed(2)}</td>
            <td class="text-center p-2">
                <button onclick="removeFromPropfirm(${ea.magic_number})" 
                        class="bg-red-600 hover:bg-red-700 px-3 py-1 rounded text-sm"
                        title="Eliminar">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
}

// ============================================================================
// PROCESAMIENTO DE ESTRATEGIAS
// ============================================================================
async function processStrategies() {
    if (propfirmEAs.length === 0) {
        showNotification('No hay EAs seleccionados', 'warning');
        return;
    }
    
    console.log('🚀 Procesando estrategias...');
    console.log('Configuración:', propfirmConfig);
    console.log('EAs a procesar:', propfirmEAs.length);
    
    // Aplicar umbrales antes de procesar
    applyThresholds();
    
    try {
        const magicNumbers = propfirmEAs.map(ea => ea.magic_number).join(',');
        
        const response = await fetch('/api/propfirm/simulate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                magic_numbers: propfirmEAs.map(ea => ea.magic_number),
                config: propfirmConfig
            })
        });
        
        const results = await response.json();
        
        if (results.error) {
            showNotification(results.error, 'error');
            return;
        }
        
        displayPropfirmResults(results);
        
    } catch (error) {
        console.error('Error procesando estrategias:', error);
        showNotification('Error procesando estrategias', 'error');
    }
}

function displayPropfirmResults(results) {
    console.log('📊 Resultados recibidos:', results);
    
    // ✅ GUARDAR EN HISTORIAL
    const simulation = {
        timestamp: new Date().toISOString(),
        date: new Date().toLocaleString('es-ES'),
        config: {...propfirmConfig},
        results: results
    };
    
    propfirmHistory.unshift(simulation); // Añadir al inicio
    
    // Mantener solo las últimas 20 simulaciones
    if (propfirmHistory.length > 20) {
        propfirmHistory = propfirmHistory.slice(0, 20);
    }
    
    localStorage.setItem('propfirmHistory', JSON.stringify(propfirmHistory));
    renderHistorySelector();
    
    // Mostrar sección de resultados
    document.getElementById('propfirmResults').classList.remove('hidden');
    
    // Actualizar resumen
    document.getElementById('totalStrategies').textContent = results.summary.total_strategies;
    document.getElementById('completedChallenges').textContent = results.summary.completed_challenges;
    document.getElementById('avgTime').textContent = results.summary.avg_time.toFixed(1);
    document.getElementById('bestStrategy').textContent = results.summary.best_strategy;
    
    // Renderizar tabla de resultados
    const tbody = document.getElementById('propfirmResultsTableBody');
    
    tbody.innerHTML = results.strategies.map(strategy => {
        const successRate = strategy.success_rate.toFixed(1);
        const successColor = successRate >= 60 ? 'text-green-400' : 
                            successRate >= 40 ? 'text-yellow-400' : 'text-red-400';
        
        return `
            <tr class="border-b border-gray-800 hover:bg-gray-800">
                <td class="text-left p-2 text-cyan-400 font-semibold">${strategy.name}</td>
                <td class="text-center p-2 text-green-400 font-bold">${strategy.completed}</td>
                <td class="text-center p-2 text-white">${strategy.avg_time.toFixed(1)}</td>
                <td class="text-center p-2 text-yellow-400">${strategy.best_time}</td>
                <td class="text-center p-2 ${successColor} font-bold">${successRate}%</td>
                <td class="text-center p-2 text-white">${strategy.total_months}</td>
                <td class="text-center p-2 text-red-400">${strategy.susp_dd_max}</td>
                <td class="text-center p-2 text-orange-400">${strategy.susp_dd_daily}</td>
                <td class="text-center p-2">
                    <button onclick="showStrategyDetails(${strategy.magic_number})" 
                            class="bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded text-xs"
                            title="Ver detalles">
                        Ver detalles
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    
    showNotification('✅ Estrategias procesadas y guardadas', 'success');
}

async function showStrategyDetails(magicNumber) {
    console.log(`📊 Ver detalles de EA ${magicNumber}`);
    
    const modal = document.getElementById('propfirmStrategyModal');
    const title = document.getElementById('propfirmStrategyTitle');
    const tbody = document.getElementById('propfirmStrategyTradesBody');
    
    if (!modal || !title || !tbody) {
        console.error('❌ Modal no encontrado');
        return;
    }
    
    // Obtener nombre del EA
    const ea = propfirmEAs.find(e => e.magic_number === magicNumber);
    const eaName = ea ? ea.name : `EA ${magicNumber}`;
    
    title.textContent = `Trades Escalados - ${eaName}`;
    
    // Mostrar modal
    modal.classList.remove('hidden');
    
    tbody.innerHTML = `
        <tr>
            <td colspan="8" class="text-center p-8 text-gray-500">
                <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
                <p>Cargando trades escalados...</p>
            </td>
        </tr>
    `;
    
    try {
        // Llamar al backend con la configuración actual
        const response = await fetch('/api/propfirm/strategy-trades', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                magic_number: magicNumber,
                config: propfirmConfig
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center p-8 text-red-500">
                        Error: ${data.error}
                    </td>
                </tr>
            `;
            return;
        }
        
        // Actualizar info de configuración
        document.getElementById('modalCapital').textContent = `$${propfirmConfig.capital.toLocaleString()}`;
        document.getElementById('modalRisk').textContent = `$${propfirmConfig.risk}`;
        document.getElementById('modalScaling').textContent = `${data.scaling_factor.toFixed(2)}x`;
        document.getElementById('modalTotalTrades').textContent = data.trades.length;
        
        // Renderizar trades
        tbody.innerHTML = data.trades.map((trade, idx) => {
            const pnlColor = trade.scaled_pnl >= 0 ? 'text-green-400' : 'text-red-400';
            const balanceColor = trade.balance >= propfirmConfig.capital ? 'text-green-400' : 'text-red-400';
            
            let statusBadge = '';
            if (trade.status === 'active') {
                statusBadge = '<span class="text-xs bg-blue-600 px-2 py-1 rounded">Activo</span>';
            } else if (trade.status === 'phase1') {
                statusBadge = '<span class="text-xs bg-yellow-600 px-2 py-1 rounded">Fase 1 ✓</span>';
            } else if (trade.status === 'completed') {
                statusBadge = '<span class="text-xs bg-green-600 px-2 py-1 rounded">Completado 🎉</span>';
            } else if (trade.status === 'susp_dd_max') {
                statusBadge = '<span class="text-xs bg-red-600 px-2 py-1 rounded">Susp. DD Máx</span>';
            } else if (trade.status === 'susp_dd_daily') {
                statusBadge = '<span class="text-xs bg-orange-600 px-2 py-1 rounded">Susp. DD Diario</span>';
            }
            
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800">
                    <td class="text-left p-2 text-gray-400">${idx + 1}</td>
                    <td class="text-left p-2 text-gray-300">${trade.close_time}</td>
                    <td class="text-left p-2 text-cyan-400">${trade.symbol}</td>
                    <td class="text-left p-2 ${trade.type === 'Buy' ? 'text-green-400' : 'text-red-400'}">${trade.type}</td>
                    <td class="text-right p-2 text-gray-400">$${trade.original_pnl.toFixed(2)}</td>
                    <td class="text-right p-2 font-bold ${pnlColor}">$${trade.scaled_pnl.toFixed(2)}</td>
                    <td class="text-right p-2 font-bold ${balanceColor}">$${trade.balance.toFixed(2)}</td>
                    <td class="text-center p-2">${statusBadge}</td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error cargando trades:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center p-8 text-red-500">
                    Error al cargar trades
                </td>
            </tr>
        `;
    }
}

function closePropfirmStrategyModal() {
    const modal = document.getElementById('propfirmStrategyModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function renderHistorySelector() {
    const container = document.getElementById('historyContainer');
    if (!container) return;
    
    if (propfirmHistory.length === 0) {
        container.innerHTML = '<p class="text-xs text-gray-500">No hay simulaciones guardadas</p>';
        return;
    }
    
    container.innerHTML = `
        <select onchange="loadSimulation(this.value)" 
                class="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-xs w-full">
            <option value="">📊 Ver simulaciones guardadas (${propfirmHistory.length})</option>
            ${propfirmHistory.map((sim, idx) => `
                <option value="${idx}">
                    ${sim.date} - ${sim.results.summary.total_strategies} EAs - ${sim.results.summary.completed_challenges} completados
                </option>
            `).join('')}
        </select>
        <button onclick="clearHistory()" 
                class="mt-2 bg-gray-600 hover:bg-gray-700 px-3 py-1 rounded text-xs font-semibold w-full"
                title="Limpiar todo el historial">
            <i class="fas fa-trash text-xs"></i> Limpiar Historial
        </button>
    `;
}

function loadSimulation(index) {
    if (index === '') return;
    
    const simulation = propfirmHistory[parseInt(index)];
    if (!simulation) return;
    
    console.log('📂 Cargando simulación:', simulation.date);
    
    // Restaurar configuración
    propfirmConfig = {...simulation.config};
    
    // Actualizar UI de configuración
    document.getElementById('selectedCapital').value = propfirmConfig.capital;
    document.getElementById('selectedRisk').value = propfirmConfig.risk;
    document.getElementById('threshold1').value = propfirmConfig.threshold1;
    document.getElementById('threshold2').value = propfirmConfig.threshold2;
    document.getElementById('ddDaily').value = propfirmConfig.ddDaily;
    document.getElementById('ddMax').value = propfirmConfig.ddMax;
    
    // Mostrar resultados
    displayPropfirmResults(simulation.results);
    
    showNotification(`Simulación cargada: ${simulation.date}`, 'info');
}

function loadLastSimulation() {
    if (propfirmHistory.length > 0) {
        const lastSim = propfirmHistory[0];
        displayPropfirmResults(lastSim.results);
        console.log('📂 Última simulación cargada automáticamente');
    }
}

function clearHistory() {
    if (!confirm('¿Estás seguro de que quieres eliminar todo el historial de simulaciones?')) {
        return;
    }
    
    propfirmHistory = [];
    localStorage.removeItem('propfirmHistory');
    renderHistorySelector();
    
    // Ocultar resultados
    document.getElementById('propfirmResults').classList.add('hidden');
    
    showNotification('Historial eliminado', 'success');
}

// ============================================================================
// EXPORT
// ============================================================================
window.initPropfirms = initPropfirms;
window.selectCapital = selectCapital;
window.selectRisk = selectRisk;
window.applyThresholds = applyThresholds;
window.addToPropfirm = addToPropfirm;
window.removeFromPropfirm = removeFromPropfirm;
window.clearPropfirmList = clearPropfirmList;
window.processStrategies = processStrategies;
window.showStrategyDetails = showStrategyDetails;
window.selectCustomRisk = selectCustomRisk;
window.loadSimulation = loadSimulation;
window.clearHistory = clearHistory;