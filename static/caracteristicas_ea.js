// ============================================================================
// CARACTERÍSTICAS TÉCNICAS EA - JAVASCRIPT
// ============================================================================

let eaCharacteristicsList = [];
let selectedEAforStats = null;
let currentEAforMonthly = null;
let eaDrawdownChartInstance = null; // ← AÑADIR ESTA LÍNEA

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
async function initCaracteristicasEA() {
    console.log('🚀 Inicializando Características EA...');
    await loadEAsList();
    await loadEASelector();
    console.log('✅ Características EA inicializadas');
}

// ============================================================================
// CARGA DE EAs
// ============================================================================
async function loadEAsList() {
    try {
        const response = await fetch('/api/ea/list');
        const data = await response.json();
        
        eaCharacteristicsList = data;
        renderEAsList(data);
        
        // ✅ RECARGAR SELECTOR TAMBIÉN
        await loadEASelectorInternal(data);
        
    } catch (error) {
        console.error('Error cargando EAs:', error);
    }
}

function renderEAsList(data) {
    const tbody = document.getElementById('easListTableBody');
    
    if (!tbody) return;

    // AÑADIR ESTOS LOGS
    console.log('📊 Datos recibidos:', data);
    if (data.length > 0) {
        console.log('Primer EA:', data[0]);
        console.log('  - walk_forward:', data[0].walk_forward);
        console.log('  - fecha_futura:', data[0].fecha_futura);
    }

    
    if (data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center p-8 text-gray-500">
                    <i class="fas fa-inbox text-4xl mb-2"></i>
                    <p>No hay EAs cargados. Sube tu primer CSV arriba.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = data.map(ea => {
        console.log(`EA ${ea.magic_number}:`, {
            walk_forward: ea.walk_forward,
            fecha_futura: ea.fecha_futura
        });
        
        // Usar nuevos campos con fallback a los antiguos
        const activo = ea.activo || ea.symbol || '-';
        const direccion = ea.direccion || ea.trade_type || '-';
        const timeframe = ea.timeframe || '-';
        const caracteristicas = ea.caracteristicas || ea.strategy || '-';
        const walkForward = ea.walk_forward || ea.range_config || '-';
        const fechaFutura = ea.fecha_futura || '-';
        
        // Color según dirección
        let direccionColor = 'text-gray-400';
        if (direccion.includes('Buy') && !direccion.includes('Sell')) {
            direccionColor = 'text-green-400';
        } else if (direccion.includes('Sell') && !direccion.includes('Buy')) {
            direccionColor = 'text-red-400';
        } else if (direccion.includes('Buy/Sell')) {
            direccionColor = 'text-yellow-400';
        }
        
        return `
            <tr class="border-b border-gray-800 hover:bg-gray-800 transition-colors">
                <td class="text-left p-2 text-cyan-400 font-semibold">${activo}</td>
                <td class="text-left p-2 font-semibold ${direccionColor}">${direccion}</td>
                <td class="text-center p-2 text-blue-400">${timeframe}</td>
                <td class="text-left p-2 text-gray-300">${caracteristicas}</td>
                <td class="text-center p-2 text-purple-400">${walkForward}</td>
                <td class="text-center p-2 text-yellow-400">${fechaFutura}</td>
                <td class="text-center p-2 text-emerald-400 font-semibold">${ea.magic_number}</td>
                <td class="text-right p-2 text-gray-400">${ea.total_backtests || 0}</td>
                <td class="text-center p-2">
                    <button onclick="viewBacktestResults(${ea.magic_number}, '${caracteristicas}')" 
                            class="bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded text-xs mr-1"
                            title="Ver resultados">
                        <i class="fas fa-chart-line"></i>
                    </button>
                    <button onclick="addToPortfolio(${ea.magic_number}, '${activo}', '${caracteristicas}')" 
                            class="bg-green-600 hover:bg-green-700 px-2 py-1 rounded text-xs mr-1"
                            title="Añadir a Portfolio">
                        <i class="fas fa-briefcase"></i>
                    </button>
                    <button onclick="addToPropfirm(${ea.magic_number})" 
                            class="bg-yellow-600 hover:bg-yellow-700 px-2 py-1 rounded text-xs mr-1"
                            title="Añadir a Análisis Propfirms">
                        <i class="fas fa-trophy"></i>
                    </button>
                    <button onclick="deleteEACharacteristics(${ea.magic_number})" 
                            class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs"
                            title="Eliminar">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}
// ============================================================================
// ANÁLISIS MENSUAL
// ============================================================================


async function loadEAMonthlyAnalysis(magicNumber) {
    console.log('📅 Cargando análisis mensual para EA:', magicNumber);
    
    currentEAforMonthly = magicNumber;
    
    // Verificar que estemos en la pestaña correcta
    const caracteristicasTab = document.getElementById('caracteristicas-tab');
    if (!caracteristicasTab || caracteristicasTab.classList.contains('hidden')) {
        console.log('   ⚠️ No estamos en la pestaña de características, saltando...');
        return;
    }
    
    const container = document.getElementById('eaMonthlyAnalysisContainer');
    const table = container ? container.querySelector('table') : null;
    
    if (!table) {
        console.error('❌ No se encontró la tabla');
        return;
    }
    
    // Mostrar contenedor
    if (container) {
        container.classList.remove('hidden');
        console.log('   ✅ Contenedor visible');
    }
    
    // Buscar tbody
    let tbody = table.querySelector('tbody');
    
    if (!tbody) {
        console.log('   ⚠️ No hay tbody, creándolo...');
        tbody = document.createElement('tbody');
        tbody.id = 'eaMonthlyTableBodyCharacteristics';
        table.appendChild(tbody);
    }
    
    console.log('   📍 Usando tbody:', tbody);
    
    // Mostrar loading
    tbody.innerHTML = `
        <tr>
            <td colspan="18" class="text-center p-8 text-gray-500">
                <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
                <p>Cargando análisis mensual...</p>
            </td>
        </tr>
    `;
    
    try {
        console.log(`   🌐 Llamando a: /api/ea/monthly-analysis/${magicNumber}`);
        const response = await fetch(`/api/ea/monthly-analysis/${magicNumber}`);
        
        console.log(`   📡 Response status: ${response.status}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('   📦 Datos recibidos:', data);
        
        if (data.error) {
            console.error('   ❌ Error en datos:', data.error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="18" class="text-center p-8 text-red-500">
                        <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                        <p>${data.error}</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        if (data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="18" class="text-center p-8 text-gray-500">
                        <i class="fas fa-inbox text-4xl mb-2"></i>
                        <p>No hay datos disponibles</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        console.log('   🎨 Limpiando tbody...');
        tbody.innerHTML = '';
        
        console.log('   🖼️ Renderizando múltiples años...');
        renderEAMonthlyTableAllYears(tbody, data);
        
        console.log('   ✅ Renderizado completo. Filas en tbody:', tbody.children.length);
        
    } catch (error) {
        console.error('❌ Error cargando análisis mensual:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="18" class="text-center p-8 text-red-500">
                    <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                    <p>Error: ${error.message}</p>
                </td>
            </tr>
        `;
    }
}

function renderEAMonthlyTableAllYears(tbody, data) {
    console.log('🖼️ renderEAMonthlyTableAllYears - Años:', data.length);
    
    const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
    
    let allRowsHTML = '';
    
    // Procesar cada año
    data.forEach(yearData => {
        let totalProfit = 0;
        let totalTrades = 0;
        let totalWinning = 0;
        let monthsWithData = 0;
        
        let rowHTML = `
            <tr class="border-b border-gray-800">
                <td class="text-left p-2 font-semibold text-yellow-400 sticky left-0 bg-gray-900">${yearData.year}</td>
        `;
        
        // Procesar meses
        months.forEach(month => {
            if (yearData[month]) {
                totalProfit += yearData[month].profit;
                totalTrades += yearData[month].trades;
                
                if (yearData[month].winning !== undefined) {
                    totalWinning += yearData[month].winning;
                    monthsWithData++;
                }
                
                const color = yearData[month].profit >= 0 ? 'text-emerald-400' : 'text-red-400';
                
                rowHTML += `
                    <td class="text-right p-2 ${color} cursor-pointer hover:bg-gray-800 transition-colors" 
                        onclick="showEATradesDetail(${yearData.magic_number}, '${month}', ${yearData.year}, ${yearData[month].profit}, ${yearData[month].trades})"
                        title="Click para ver trades">
                        <div class="font-semibold">$${yearData[month].profit.toFixed(2)}</div>
                        <div class="text-xs text-gray-400">(${yearData[month].trades})</div>
                    </td>
                `;
            } else {
                rowHTML += `<td class="text-right p-2 text-gray-600">-</td>`;
            }
        });
        
        const avgWinRate = monthsWithData > 0 ? (totalWinning / monthsWithData).toFixed(1) : '0.0';
        const retDD = yearData.ret_dd !== undefined ? yearData.ret_dd.toFixed(2) : '0.00';
        const maxConsecLoss = yearData.max_consecutive_loss !== undefined ? yearData.max_consecutive_loss : 0;
        const totalColor = totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400';
        
        // Añadir totales
        rowHTML += `
                <td class="text-right p-2 font-bold ${totalColor}">$${totalProfit.toFixed(2)}</td>
                <td class="text-right p-2 text-gray-400">${totalTrades}</td>
                <td class="text-right p-2 text-blue-400">${avgWinRate}%</td>
                <td class="text-right p-2 text-purple-400">${retDD}</td>
                <td class="text-right p-2 text-red-400">${maxConsecLoss}</td>
            </tr>
        `;
        
        allRowsHTML += rowHTML;
        
        console.log(`   ${yearData.year}: $${totalProfit.toFixed(2)}, ${totalTrades} trades`);
    });
    
    tbody.innerHTML = allRowsHTML;
    
    console.log('   ✅ Todas las filas renderizadas. Total filas:', tbody.children.length);
}

function renderEAMonthlyTable(tbody, ea) {
    console.log('🖼️ renderEAMonthlyTable iniciado para EA:', ea.magic_number);
    
    const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
    
    let totalProfit = 0;
    let totalTrades = 0;
    let totalWinning = 0;
    let monthsWithData = 0;
    
    // Construir HTML directamente
    let rowHTML = `
        <tr class="border-b border-gray-800">
            <td class="text-left p-2 font-semibold text-yellow-400 sticky left-0 bg-gray-900">${ea.magic_number}</td>
    `;
    
    // Procesar meses
    months.forEach(month => {
        if (ea[month]) {
            totalProfit += ea[month].profit;
            totalTrades += ea[month].trades;
            
            if (ea[month].winning !== undefined) {
                totalWinning += ea[month].winning;
                monthsWithData++;
            }
            
            const color = ea[month].profit >= 0 ? 'text-emerald-400' : 'text-red-400';
            
            // ✅ HACER LA CELDA CLICABLE
            rowHTML += `
                <td class="text-right p-2 ${color} cursor-pointer hover:bg-gray-800 transition-colors" 
                    onclick="showEATradesDetail(${ea.magic_number}, '${month}', ${ea[month].profit}, ${ea[month].trades})"
                    title="Click para ver trades">
                    <div class="font-semibold">$${ea[month].profit.toFixed(2)}</div>
                    <div class="text-xs text-gray-400">(${ea[month].trades})</div>
                </td>
            `;
            
            console.log(`      ${month}: $${ea[month].profit.toFixed(2)} (${ea[month].trades} trades)`);
        } else {
            rowHTML += `<td class="text-right p-2 text-gray-600">-</td>`;
        }
    });
    
    const avgWinRate = monthsWithData > 0 ? (totalWinning / monthsWithData).toFixed(1) : '0.0';
    const retDD = ea.ret_dd !== undefined ? ea.ret_dd.toFixed(2) : '0.00';
    const maxConsecLoss = ea.max_consecutive_loss !== undefined ? ea.max_consecutive_loss : 0;
    const totalColor = totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400';
    
    console.log(`   💰 Totales: $${totalProfit.toFixed(2)}, ${totalTrades} trades, ${avgWinRate}% win`);
    
    // Añadir totales
    rowHTML += `
            <td class="text-right p-2 font-bold ${totalColor}">$${totalProfit.toFixed(2)}</td>
            <td class="text-right p-2 text-gray-400">${totalTrades}</td>
            <td class="text-right p-2 text-blue-400">${avgWinRate}%</td>
            <td class="text-right p-2 text-purple-400">${retDD}</td>
            <td class="text-right p-2 text-red-400">${maxConsecLoss}</td>
        </tr>
    `;
    
    console.log('   📝 HTML de fila construido');
    
    // Asignar directamente
    tbody.innerHTML = rowHTML;
    
    console.log('   ✅ innerHTML asignado. Hijos:', tbody.children.length);
}

// ============================================================================
// DETALLE DE TRADES POR MES (EA ESPECÍFICO)
// ============================================================================
async function showEATradesDetail(magicNumber, month, year, profit, trades) {
    const modal = document.getElementById('tradesDetailModal');
    const title = document.getElementById('tradesDetailTitle');
    const tbody = document.getElementById('tradesDetailTableBody');
    
    title.textContent = `Trades - EA ${magicNumber} - ${month} ${year}`;
    
    tbody.innerHTML = `
        <tr>
            <td colspan="8" class="text-center p-8 text-gray-500">
                <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
                <p>Cargando trades...</p>
            </td>
        </tr>
    `;
    
    modal.classList.remove('hidden');
    
    try {
        const response = await fetch(`/api/ea/trades-detail/${magicNumber}/${month}?year=${year}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center p-8 text-red-500">
                        ${data.error}
                    </td>
                </tr>
            `;
            return;
        }
        
        if (data.trades.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center p-8 text-gray-500">
                        No hay trades para este mes
                    </td>
                </tr>
            `;
            return;
        }
        
        // Renderizar trades
        tbody.innerHTML = data.trades.map(trade => {
            const profitColor = trade.profit >= 0 ? 'text-emerald-400' : 'text-red-400';
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800">
                    <td class="text-left p-2 text-gray-300">${trade.close_time}</td>
                    <td class="text-left p-2 text-cyan-400">${trade.symbol}</td>
                    <td class="text-left p-2 ${trade.type === 'Buy' ? 'text-green-400' : 'text-red-400'}">${trade.type}</td>
                    <td class="text-right p-2 text-gray-300">${trade.volume.toFixed(2)}</td>
                    <td class="text-right p-2 text-gray-300">${trade.open_price.toFixed(5)}</td>
                    <td class="text-right p-2 text-gray-300">${trade.close_price.toFixed(5)}</td>
                    <td class="text-right p-2 font-bold ${profitColor}">$${trade.profit.toFixed(2)}</td>
                    <td class="text-left p-2 text-gray-400 text-xs">${trade.comment}</td>
                </tr>
            `;
        }).join('');
        
        // Actualizar resumen en el modal
        document.getElementById('modalTotalTrades').textContent = data.summary.total;
        document.getElementById('modalTotalProfit').textContent = `$${data.summary.profit.toFixed(2)}`;
        document.getElementById('modalWinRate').textContent = `${data.summary.win_rate.toFixed(1)}%`;
        
        // Color del profit total
        const profitElement = document.getElementById('modalTotalProfit');
        if (data.summary.profit >= 0) {
            profitElement.className = 'text-lg font-bold text-emerald-400';
        } else {
            profitElement.className = 'text-lg font-bold text-red-400';
        }
        
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
// ============================================================================
// GRÁFICO DE DRAWDOWN DEL EA
// ============================================================================
async function loadEADrawdownChart(magicNumber) {
    console.log('📈 Cargando gráfico drawdown para EA:', magicNumber);
    
    const container = document.getElementById('eaDrawdownContainer');
    const canvas = document.getElementById('eaDrawdownChart');
    
    if (!container || !canvas) {
        console.error('❌ No se encontró el contenedor del gráfico');
        return;
    }
    
    // Mostrar contenedor
    container.classList.remove('hidden');
    
    try {
        const response = await fetch(`/api/ea/drawdown-chart/${magicNumber}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            console.error('❌ Error en datos:', data.error);
            return;
        }
        
        console.log('✅ Datos del gráfico recibidos');
        renderEADrawdownChart(data);
        
    } catch (error) {
        console.error('❌ Error cargando gráfico drawdown:', error);
    }
}

function renderEADrawdownChart(data) {
    const canvas = document.getElementById('eaDrawdownChart');
    
    if (!canvas) {
        console.error('❌ Canvas no encontrado');
        return;
    }
    
    // Destruir gráfico anterior si existe
    if (eaDrawdownChartInstance) {
        eaDrawdownChartInstance.destroy();
    }
    
    const ctx = canvas.getContext('2d');
    
    eaDrawdownChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Equity',
                    data: data.equity,
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'Drawdown',
                    data: data.drawdown,
                    borderColor: 'rgba(239, 68, 68, 1)',
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: 'rgba(255, 255, 255, 0.8)',
                        font: { size: 11 },
                        usePointStyle: true,
                        padding: 15
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 10,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += '$' + context.parsed.y.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: 'rgba(255, 255, 255, 0.6)',
                        font: { size: 10 },
                        maxRotation: 45,
                        minRotation: 0,
                        maxTicksLimit: 15
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Equity ($)',
                        color: 'rgba(16, 185, 129, 1)',
                        font: { size: 11, weight: 'bold' }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawBorder: false
                    },
                    ticks: {
                        color: 'rgba(16, 185, 129, 0.8)',
                        font: { size: 10 },
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Drawdown ($)',
                        color: 'rgba(239, 68, 68, 1)',
                        font: { size: 11, weight: 'bold' }
                    },
                    grid: {
                        drawOnChartArea: false
                    },
                    ticks: {
                        color: 'rgba(239, 68, 68, 0.8)',
                        font: { size: 10 },
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    }
                }
            }
        }
    });
    
    console.log('✅ Gráfico drawdown renderizado');
}

// ============================================================================
// GESTIÓN DE COMENTARIO Y FECHA FUTURA
// ============================================================================
async function onEAStatsChange() {
    const select = document.getElementById('eaStatsSelector');
    const magicNumber = select ? select.value : '';
    
    console.log('🔄 Cambio de EA:', magicNumber);
    
    // Obtener referencias a los campos
    const commentInput = document.getElementById('eaCommentInput');
    const dateInput = document.getElementById('eaFutureDateInput');
    const saveButton = document.getElementById('saveEAInfoButton');
    
    if (!magicNumber || magicNumber === '') {
        hideEAStats();
        
        // Deshabilitar y limpiar campos
        if (commentInput) {
            commentInput.value = '';
            commentInput.disabled = true;
        }
        if (dateInput) {
            dateInput.value = '';
            dateInput.disabled = true;
        }
        if (saveButton) {
            saveButton.disabled = true;
        }
        
        return;
    }
    
    selectedEAforStats = magicNumber;
    
    // ✅ HABILITAR CAMPOS INMEDIATAMENTE
    console.log('   🔓 Habilitando campos de entrada...');
    
    if (commentInput) {
        commentInput.disabled = false;
        commentInput.removeAttribute('disabled');
        console.log('   ✅ Comentario habilitado:', !commentInput.disabled);
    } else {
        console.error('   ❌ No se encontró eaCommentInput');
    }
    
    if (dateInput) {
        dateInput.disabled = false;
        dateInput.removeAttribute('disabled');
        console.log('   ✅ Fecha habilitada:', !dateInput.disabled);
    } else {
        console.error('   ❌ No se encontró eaFutureDateInput');
    }
    
    if (saveButton) {
        saveButton.disabled = false;
        saveButton.removeAttribute('disabled');
        console.log('   ✅ Botón guardar habilitado:', !saveButton.disabled);
    } else {
        console.error('   ❌ No se encontró saveEAInfoButton');
    }
    
    // Pequeño delay para asegurar que los campos estén listos
    await new Promise(resolve => setTimeout(resolve, 50));
    
    // Cargar información del EA
    await loadEAInfo(magicNumber);
    
    // Cargar estadísticas
    await loadEAStats(magicNumber);
}

async function loadEAInfo(magicNumber) {
    console.log('📋 Cargando información del EA:', magicNumber);
    
    try {
        const response = await fetch(`/api/ea/info/${magicNumber}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('   📦 Datos recibidos:', data);
        
        const commentInput = document.getElementById('eaCommentInput');
        const dateInput = document.getElementById('eaFutureDateInput');
        
        if (commentInput) {
            commentInput.value = data.notes || '';
            console.log('   📝 Comentario cargado, caracteres:', commentInput.value.length);
        }
        
        if (dateInput) {
            dateInput.value = data.future_date || '';
            console.log('   📅 Fecha cargada:', dateInput.value || 'vacía');
        }
        
        console.log('✅ Info del EA cargada correctamente');
        
    } catch (error) {
        console.error('❌ Error cargando info del EA:', error);
    }
}

async function saveEAInfo() {
    const magicNumber = selectedEAforStats;
    
    if (!magicNumber) {
        alert('❌ Selecciona un EA primero');
        return;
    }
    
    const commentInput = document.getElementById('eaCommentInput');
    const dateInput = document.getElementById('eaFutureDateInput');
    const saveButton = document.getElementById('saveEAInfoButton');
    
    if (!commentInput || !dateInput || !saveButton) {
        console.error('❌ No se encontraron los elementos del formulario');
        alert('❌ Error: No se encontraron los campos del formulario');
        return;
    }
    
    const notes = commentInput.value.trim();
    const futureDate = dateInput.value;
    
    console.log('💾 Guardando información:', { 
        magicNumber, 
        notesLength: notes.length,
        futureDate: futureDate || 'vacía'
    });
    
    const originalText = saveButton.innerHTML;
    saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
    saveButton.disabled = true;
    
    try {
        const response = await fetch('/api/ea/update-info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                magic_number: parseInt(magicNumber),
                notes: notes,
                future_date: futureDate
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ Información guardada correctamente');
            
            // Mostrar mensaje de éxito temporal
            saveButton.innerHTML = '<i class="fas fa-check"></i> ¡Guardado!';
            saveButton.classList.remove('bg-purple-600', 'hover:bg-purple-700');
            saveButton.classList.add('bg-green-600');
            
            // Recargar lista de EAs para actualizar la tabla
            await loadEAsList();
            
            setTimeout(() => {
                saveButton.innerHTML = originalText;
                saveButton.classList.remove('bg-green-600');
                saveButton.classList.add('bg-purple-600', 'hover:bg-purple-700');
                saveButton.disabled = false;
            }, 2000);
        } else {
            console.error('❌ Error al guardar:', result.error);
            alert('❌ Error al guardar: ' + (result.error || 'Error desconocido'));
            saveButton.innerHTML = originalText;
            saveButton.disabled = false;
        }
        
    } catch (error) {
        console.error('❌ Error guardando información:', error);
        alert('❌ Error de conexión: ' + error.message);
        saveButton.innerHTML = originalText;
        saveButton.disabled = false;
    }
}

// ============================================================================
// SUBIDA DE ARCHIVOS
// ============================================================================
function triggerFileUpload() {
    document.getElementById('eaFileInput').click();
}

async function handleFileUpload(event) {
    const files = event.target.files;
    
    if (!files || files.length === 0) {
        return;
    }
    
    const uploadButton = document.getElementById('uploadEAButton');
    const originalText = uploadButton.innerHTML;
    
    uploadButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
    uploadButton.disabled = true;
    
    try {
        const formData = new FormData();
        
        for (let i = 0; i < files.length; i++) {
            formData.append('files[]', files[i]);
        }
        
        const response = await fetch('/api/ea/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            let message = `✅ ${result.message}\n\n`;
            
            result.results.forEach(r => {
                if (r.success) {
                    message += `✓ ${r.filename}\n  Magic: ${r.magic_number} | Trades: ${r.trades}\n`;
                } else {
                    message += `✗ ${r.filename}\n  Error: ${r.error}\n`;
                }
            });
            
            alert(message);
            
            // ✅ RECARGAR LISTA Y SELECTOR
            await loadEAsList();
            
        } else {
            alert('❌ Error: ' + (result.error || 'Error desconocido'));
        }
        
    } catch (error) {
        console.error('Error subiendo archivos:', error);
        alert('❌ Error de conexión: ' + error.message);
    } finally {
        uploadButton.innerHTML = originalText;
        uploadButton.disabled = false;
        event.target.value = '';
    }
}

// ============================================================================
// VER RESULTADOS DE BACKTESTING
// ============================================================================
async function viewBacktestResults(magicNumber, strategy) {
    const modal = document.getElementById('backtestResultsModal');
    const title = document.getElementById('backtestResultsTitle');
    const tbody = document.getElementById('backtestResultsTableBody');
    
    title.textContent = `Resultados Backtesting - EA ${magicNumber} (${strategy})`;
    
    tbody.innerHTML = `
        <tr>
            <td colspan="7" class="text-center p-8 text-gray-500">
                <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
                <p>Cargando resultados...</p>
            </td>
        </tr>
    `;
    
    modal.classList.remove('hidden');
    
    try {
        const response = await fetch(`/api/ea/backtest-results/${magicNumber}`);
        const results = await response.json();
        
        if (results.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center p-8 text-gray-500">
                        No hay resultados de backtesting
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = results.map(r => {
            const profitColor = r.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400';
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800">
                    <td class="text-center p-2 text-gray-300">${r.test_number}</td>
                    <td class="text-right p-2 font-bold ${profitColor}">$${r.net_profit.toFixed(2)}</td>
                    <td class="text-right p-2 text-white">${r.total_trades}</td>
                    <td class="text-right p-2 text-green-400">${r.win_rate.toFixed(1)}%</td>
                    <td class="text-right p-2 text-blue-400">${r.profit_factor.toFixed(2)}</td>
                    <td class="text-right p-2 text-red-400">$${Math.abs(r.max_drawdown).toFixed(2)}</td>
                    <td class="text-right p-2 text-purple-400">${r.sharpe_ratio.toFixed(2)}</td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error cargando resultados:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center p-8 text-red-500">
                    Error al cargar resultados
                </td>
            </tr>
        `;
    }
}

function closeBacktestResultsModal() {
    document.getElementById('backtestResultsModal').classList.add('hidden');
}

// ============================================================================
// NOTAS
// ============================================================================
function showNotesModal(magicNumber, currentNotes) {
    const modal = document.getElementById('notesModal');
    const textarea = document.getElementById('notesTextarea');
    const saveButton = document.getElementById('saveNotesButton');
    
    textarea.value = currentNotes || '';
    
    saveButton.onclick = async () => {
        await saveNotes(magicNumber, textarea.value);
    };
    
    modal.classList.remove('hidden');
}

function closeNotesModal() {
    document.getElementById('notesModal').classList.add('hidden');
}

async function saveNotes(magicNumber, notes) {
    try {
        const response = await fetch('/api/ea/update-notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ magic_number: magicNumber, notes: notes })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('✅ Notas guardadas');
            closeNotesModal();
            await loadEAsList();
        } else {
            alert('❌ Error: ' + result.error);
        }
        
    } catch (error) {
        console.error('Error guardando notas:', error);
        alert('❌ Error: ' + error.message);
    }
}

// ============================================================================
// ELIMINAR EA
// ============================================================================
async function deleteEACharacteristics(magicNumber) {
    const confirmation = confirm(
        `⚠️ ELIMINAR EA ${magicNumber}\n\n` +
        `Esto eliminará el archivo CSV y todos sus resultados de backtesting.\n` +
        `Esta acción NO se puede deshacer.\n\n` +
        `¿Continuar?`
    );
    
    if (!confirmation) return;
    
    try {
        const response = await fetch(`/api/ea/delete/${magicNumber}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            
            // Si el EA eliminado estaba seleccionado, limpiar
            if (selectedEAforStats == magicNumber) {
                selectedEAforStats = null;
                hideEAStats();
                const select = document.getElementById('eaStatsSelector');
                if (select) select.value = '';
            }
            
            // ✅ RECARGAR LISTA Y SELECTOR
            await loadEAsList();
            
        } else {
            alert('❌ Error: ' + result.error);
        }
        
    } catch (error) {
        console.error('Error eliminando EA:', error);
        alert('❌ Error: ' + error.message);
    }
}

// ============================================================================
// SELECTOR DE EA Y VISUALIZACIÓN DE KPIs
// ============================================================================
async function loadEASelector() {
    try {
        const response = await fetch('/api/ea/list');
        const data = await response.json();
        await loadEASelectorInternal(data);
    } catch (error) {
        console.error('Error cargando selector de EAs:', error);
    }
}

function loadEASelectorInternal(data) {
    const select = document.getElementById('eaStatsSelector');
    
    if (!select) {
        console.warn('⚠️ Selector eaStatsSelector no encontrado');
        return;
    }
    
    console.log('📋 Cargando selector con', data.length, 'EAs');
    
    if (data.length === 0) {
        select.innerHTML = '<option value="">No hay EAs disponibles</option>';
        select.disabled = true;
        hideEAStats();
        return;
    }
    
    select.innerHTML = '<option value="">Selecciona un EA...</option>' +
        data.map(ea => 
            `<option value="${ea.magic_number}">${ea.magic_number} - ${ea.symbol} ${ea.timeframe} ${ea.strategy}</option>`
        ).join('');
    
    select.disabled = false;
    
    console.log('✅ Selector cargado con', data.length, 'opciones');
}


async function loadEAStats(magicNumber) {
    const statsContainer = document.getElementById('eaStatsContainer');
    const monthlyContainer = document.getElementById('eaMonthlyAnalysisContainer');
    const drawdownContainer = document.getElementById('eaDrawdownContainer');
    
    if (!statsContainer) {
        console.error('❌ No se encontró eaStatsContainer');
        return;
    }
    
    console.log('📊 Cargando stats para EA:', magicNumber);
    
    // Mostrar loading en stats
    statsContainer.classList.remove('hidden');
    statsContainer.innerHTML = `
        <div class="stat-card rounded-lg p-8">
            <div class="text-center">
                <i class="fas fa-spinner fa-spin text-4xl text-yellow-400 mb-4"></i>
                <p class="text-gray-400">Calculando KPIs del EA ${magicNumber}...</p>
            </div>
        </div>
    `;
    
    // Mostrar contenedor de gráfico drawdown
    if (drawdownContainer) {
        drawdownContainer.classList.remove('hidden');
    }
    
    // Mostrar contenedor de análisis mensual
    if (monthlyContainer) {
        monthlyContainer.classList.remove('hidden');
    }
    
    try {
        const response = await fetch(`/api/ea/detailed-stats/${magicNumber}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const stats = await response.json();
        
        if (stats.error) {
            statsContainer.innerHTML = `
                <div class="stat-card rounded-lg p-8">
                    <div class="text-center">
                        <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
                        <p class="text-red-400">${stats.error}</p>
                    </div>
                </div>
            `;
            return;
        }
        
        console.log('✅ Stats cargadas:', stats);
        renderEAStats(stats);
        
        // Cargar gráfico de drawdown
        await loadEADrawdownChart(magicNumber);
        
        // Cargar análisis mensual
        await loadEAMonthlyAnalysis(magicNumber);
        
    } catch (error) {
        console.error('❌ Error cargando stats del EA:', error);
        statsContainer.innerHTML = `
            <div class="stat-card rounded-lg p-8">
                <div class="text-center">
                    <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
                    <p class="text-red-400">Error al cargar estadísticas: ${error.message}</p>
                </div>
            </div>
        `;
    }
}

function hideEAStats() {
    const statsContainer = document.getElementById('eaStatsContainer');
    if (statsContainer) {
        statsContainer.classList.add('hidden');
        statsContainer.innerHTML = '';
    }
    
    // Ocultar y destruir gráfico de drawdown
    const drawdownContainer = document.getElementById('eaDrawdownContainer');
    if (drawdownContainer) {
        drawdownContainer.classList.add('hidden');
    }
    
    if (eaDrawdownChartInstance) {
        eaDrawdownChartInstance.destroy();
        eaDrawdownChartInstance = null;
    }
    
    const monthlyContainer = document.getElementById('eaMonthlyAnalysisContainer');
    if (monthlyContainer) {
        monthlyContainer.classList.add('hidden');
    }
    
    // Resetear año
    const yearFilter = document.getElementById('eaMonthlyYearFilter');
    if (yearFilter) {
        yearFilter.value = '2025';
    }
    
    currentEAforMonthly = null;
    
    // Limpiar tbody también
    const tbody = document.getElementById('eaMonthlyTableBodyCharacteristics');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="18" class="text-center p-8 text-gray-500">
                    <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
                    <p>Selecciona un EA...</p>
                </td>
            </tr>
        `;
    }
    
    console.log('👁️ Stats ocultadas');
}
function renderEAStats(stats) {
    const statsContainer = document.getElementById('eaStatsContainer');
    
    if (!statsContainer) return;
    
    statsContainer.classList.remove('hidden');
    
    statsContainer.innerHTML = `
        <div class="space-y-4">
            <!-- INFO PERÍODO -->
            <div class="stat-card rounded-lg p-4">
                <h4 class="text-sm font-semibold text-gray-400 mb-2">INFORMACIÓN DEL PERÍODO</h4>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div>
                        <p class="text-gray-500">Primer Trade</p>
                        <p class="text-white font-semibold">${stats.first_trade_date}</p>
                    </div>
                    <div>
                        <p class="text-gray-500">Último Trade</p>
                        <p class="text-white font-semibold">${stats.last_trade_date}</p>
                    </div>
                    <div>
                        <p class="text-gray-500">Total Días</p>
                        <p class="text-cyan-400 font-semibold">${stats.total_days}</p>
                    </div>
                    <div>
                        <p class="text-gray-500">Total Meses</p>
                        <p class="text-cyan-400 font-semibold">${stats.total_months}</p>
                    </div>
                </div>
            </div>
            
            <!-- KPIs PRINCIPALES -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div class="stat-card rounded-lg p-4">
                    <p class="text-xs text-gray-400 uppercase tracking-wider mb-1">Net Profit</p>
                    <p class="text-3xl font-bold ${stats.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}">$${stats.net_profit.toFixed(2)}</p>
                </div>
                <div id="eaRetDD" class="stat-card rounded-lg p-4">
                    <p class="text-xs text-white uppercase tracking-wider mb-1 font-semibold">RET/DD</p>
                    <p class="text-3xl font-bold text-white">${stats.ret_dd.toFixed(2)}</p>
                </div>
                <div id="eaSQN" class="stat-card rounded-lg p-4">
                    <p class="text-xs text-white uppercase tracking-wider mb-1 font-semibold">SQN</p>
                    <p class="text-3xl font-bold text-white">${stats.sqn.toFixed(2)}</p>
                </div>
                <div id="eaR2" class="stat-card rounded-lg p-4">
                    <p class="text-xs text-white uppercase tracking-wider mb-1 font-semibold">R² Equity</p>
                    <p class="text-3xl font-bold text-white">${stats.r2_equity.toFixed(4)}</p>
                </div>
            </div>

            <!-- KPIs SECUNDARIOS -->
            <div class="grid grid-cols-2 md:grid-cols-7 gap-3">
                <div id="eaCAGR" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">CAGR</p>
                    <p class="text-xl font-bold text-white">${stats.cagr.toFixed(2)}%</p>
                </div>
                <div id="eaProfitFactor" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">Profit Factor</p>
                    <p class="text-xl font-bold text-white">${stats.profit_factor.toFixed(2)}</p>
                </div>
                <div id="eaExpectancy" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">Expectancy</p>
                    <p class="text-xl font-bold text-white">${stats.expectancy.toFixed(2)}</p>
                </div>
                <div id="eaSharpe" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">Sharpe Ratio</p>
                    <p class="text-xl font-bold text-white">${stats.sharpe_ratio.toFixed(2)}</p>
                </div>
                <div id="eaRR" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">RR Ratio</p>
                    <p class="text-xl font-bold text-white">${stats.rr_ratio.toFixed(2)}</p>
                </div>
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1"># Trades</p>
                    <p class="text-xl font-bold">${stats.total_trades}</p>
                </div>
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1">Win Rate</p>
                    <p class="text-xl font-bold">${stats.win_rate.toFixed(1)}%</p>
                </div>
            </div>

            <!-- KPIs ADICIONALES -->
            <div class="grid grid-cols-2 md:grid-cols-6 gap-3">
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1">Max DD Total</p>
                    <p class="text-lg font-bold text-red-400">$${Math.abs(stats.max_drawdown).toFixed(2)}</p>
                </div>
                <div class="stat-card rounded-lg p-4">
                    <div class="flex justify-between items-center mb-2">
                        <p class="text-gray-400 text-xs uppercase">Max DD Year</p>
                        <select id="eaYearSelector" onchange="updateEAMaxDDYearForSelected()" 
                                class="bg-gray-800 border border-gray-700 text-white rounded px-1 py-0.5 text-xs">
                            <option value="${new Date().getFullYear()}">${new Date().getFullYear()}</option>
                            <option value="${new Date().getFullYear() - 1}">${new Date().getFullYear() - 1}</option>
                            <option value="${new Date().getFullYear() - 2}">${new Date().getFullYear() - 2}</option>
                            <option value="${new Date().getFullYear() - 3}">${new Date().getFullYear() - 3}</option>
                            <option value="${new Date().getFullYear() - 4}">${new Date().getFullYear() - 4}</option>
                            <option value="${new Date().getFullYear() - 5}">${new Date().getFullYear() - 5}</option>
                            <option value="all">Todos</option>
                        </select>
                    </div>
                    <p id="eaMaxDDYearValue" class="text-2xl font-bold text-red-400">${stats.max_dd_year.toFixed(2)}%</p>
                </div>
                <div id="eaAvgRecovery" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">AVG Recovery</p>
                    <p class="text-lg font-bold text-white">${stats.avg_recovery_days.toFixed(1)} días</p>
                </div>
                <div id="eaConsistency" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">Consistencia</p>
                    <p class="text-lg font-bold text-white">${stats.consistency_green_months.toFixed(1)}%</p>
                </div>
                <div id="eaStagnation" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">Stagnation</p>
                    <p class="text-lg font-bold text-white">${stats.stagnation_days} días</p>
                </div>
                <div id="eaAvgTrades" class="stat-card rounded-lg p-3">
                    <p class="text-xs text-white uppercase mb-1 font-semibold">AVG Trades/Mes</p>
                    <p class="text-lg font-bold text-white">${stats.avg_trades_per_month.toFixed(1)}</p>
                </div>
            </div>

            <!-- PROFIT/LOSS DETAILS -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1">Gross Profit</p>
                    <p class="text-lg font-bold text-emerald-400">$${stats.gross_profit.toFixed(2)}</p>
                </div>
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1">Gross Loss</p>
                    <p class="text-lg font-bold text-red-400">$${stats.gross_loss.toFixed(2)}</p>
                </div>
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1">Winning Trades</p>
                    <p class="text-lg font-bold text-emerald-400">${stats.winning_trades}</p>
                </div>
                <div class="stat-card rounded-lg p-3">
                    <p class="text-xs text-gray-500 uppercase mb-1">Losing Trades</p>
                    <p class="text-lg font-bold text-red-400">${stats.losing_trades}</p>
                </div>
            </div>
        </div>
    `;
    
    // Aplicar colores a los KPIs según umbrales
    applyEAKPIColors('eaRetDD', stats.ret_dd, 2.0, 3.0);
    applyEAKPIColors('eaSQN', stats.sqn, 1.6, 2.5);
    applyEAKPIColors('eaR2', stats.r2_equity, 0.70, 0.85);
    applyEAKPIColors('eaCAGR', stats.cagr, 5, 15);
    applyEAKPIColors('eaProfitFactor', stats.profit_factor, 1.20, 1.40);
    applyEAKPIColors('eaExpectancy', stats.expectancy, 0.10, 0.25);
    applyEAKPIColors('eaSharpe', stats.sharpe_ratio, 1.00, 1.50);
    applyEAKPIColors('eaRR', stats.rr_ratio, 1.5, 2.0);
    applyEAKPIColors('eaAvgRecovery', stats.avg_recovery_days, 30, 15, true); // true = invertido (menos es mejor)
    applyEAKPIColors('eaConsistency', stats.consistency_green_months, 60, 80);
    applyEAKPIColors('eaStagnation', stats.stagnation_days, 90, 30, true); // invertido (menos es mejor)
    applyEAKPIColors('eaAvgTrades', stats.avg_trades_per_month, 20, 40);
}

function applyEAKPIColors(cardId, value, yellowThreshold, greenThreshold, inverted = false) {
    const card = document.getElementById(cardId);
    if (!card) return;
    
    card.classList.remove('kpi-green', 'kpi-yellow', 'kpi-red');
    
    if (inverted) {
        // Para métricas donde MENOR es MEJOR (recovery days, stagnation)
        if (value <= greenThreshold) {
            card.classList.add('kpi-green');
        } else if (value <= yellowThreshold) {
            card.classList.add('kpi-yellow');
        } else {
            card.classList.add('kpi-red');
        }
    } else {
        // Para métricas donde MAYOR es MEJOR
        if (value >= greenThreshold) {
            card.classList.add('kpi-green');
        } else if (value >= yellowThreshold) {
            card.classList.add('kpi-yellow');
        } else {
            card.classList.add('kpi-red');
        }
    }
}

// ============================================================================
// ACTUALIZAR MAX DD YEAR DEL EA SELECCIONADO
// ============================================================================
async function updateEAMaxDDYearForSelected() {
    const selector = document.getElementById('eaStatsSelector');
    const yearSelector = document.getElementById('eaYearSelector');
    const maxDDElement = document.getElementById('eaMaxDDYearValue');
    
    if (!selector || !yearSelector || !maxDDElement) return;
    
    const magicNumber = selector.value;
    const year = yearSelector.value;
    
    if (!magicNumber) return;
    
    console.log(`📊 Actualizando Max DD Year para EA ${magicNumber}, año ${year}`);
    
    maxDDElement.textContent = '...';
    
    try {
        const response = await fetch(`/api/ea/max-dd-year-selected?magic_number=${magicNumber}&year=${year}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        maxDDElement.textContent = `${data.max_dd.toFixed(2)}%`;
        
        console.log(`✅ Max DD Year actualizado: ${data.max_dd.toFixed(2)}%`);
        
    } catch (error) {
        console.error('❌ Error actualizando Max DD Year:', error);
        maxDDElement.textContent = '-';
    }
}