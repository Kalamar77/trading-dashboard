// ============================================================================
// VARIABLES GLOBALES
// ============================================================================
let monthlyChart = null;
let drawdownChart = null;
let selectedEA = null;

// Variables para ordenamiento de tabla
let currentSortColumn = null;
let currentSortDirection = 'asc';
let eaTableData = [];

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Inicializando dashboard...');
    
    await loadFilters();
    await loadDashboardData();
    await initCuentaReal();  // ← AÑADIR ESTA LÍNEA
    
    console.log('✅ Dashboard inicializado');
});

// ============================================================================
// CARGAR FILTROS
// ============================================================================
async function loadFilters() {
    try {
        console.log('🔄 Cargando filtros...');
        
        // 1. Cargar SOURCES con nombres amigables
        try {
            const sourcesResponse = await fetch('/api/sources');
            const sources = await sourcesResponse.json();
            
            console.log('✅ Sources recibidos de la API:', sources);
            
            // 🔧 MAPEO DE NOMBRES - Añade aquí nuevas cuentas
            const sourceNames = {
                'atr2': 'Darwinex',
                'atr3': 'Darwinex2',
                'axi_dax': 'Axi',
                'axi_nq': 'Axi 2'
                // Para añadir más cuentas, solo añade líneas aquí:
                // 'codigo_tecnico': 'Nombre Amigable',
            };
            
            const sourceSelect = document.getElementById('filterSource');
            if (sourceSelect) {
                const options = sources.map(s => {
                    const displayName = sourceNames[s] || s;
                    console.log(`  Mapeando: ${s} → ${displayName}`);
                    return `<option value="${s}">${displayName}</option>`;
                }).join('');
                
                sourceSelect.innerHTML = '<option value="all">Cuenta: Todas</option>' + options;
                
                console.log(`✅ ${sources.length} cuentas cargadas en el selector`);
            } else {
                console.error('❌ No se encontró el elemento filterSource');
            }
        } catch (error) {
            console.error('❌ Error cargando sources:', error);
        }
        
        // 2. Cargar SYMBOLS
        try {
            const symbolsResponse = await fetch('/api/symbols');
            const symbols = await symbolsResponse.json();
            console.log('✅ Symbols cargados:', symbols.length);
            
            const symbolSelect = document.getElementById('filterSymbol');
            if (symbolSelect) {
                symbolSelect.innerHTML = '<option value="all">Divisa: Todas</option>' + 
                    symbols.map(s => `<option value="${s}">${s}</option>`).join('');
            }
        } catch (error) {
            console.error('❌ Error cargando symbols:', error);
        }
        
        // 3. Cargar TIMEFRAMES
        try {
            const timeframesResponse = await fetch('/api/timeframes');
            const timeframes = await timeframesResponse.json();
            console.log('✅ Timeframes cargados:', timeframes.length);
            
            const timeframeSelect = document.getElementById('filterTimeframe');
            if (timeframeSelect) {
                timeframeSelect.innerHTML = '<option value="all">Temp: Todas</option>' + 
                    timeframes.map(t => `<option value="${t}">${t}</option>`).join('');
            }
        } catch (error) {
            console.error('❌ Error cargando timeframes:', error);
        }
        
        // 4. Cargar MAGIC NUMBERS
        try {
            const magicResponse = await fetch('/api/magic-numbers');
            const magicNumbers = await magicResponse.json();
            console.log('✅ Magic Numbers cargados:', magicNumbers.length);
            
            const magicSelectMain = document.getElementById('filterMagicNumberMain');
            if (magicSelectMain) {
                magicSelectMain.innerHTML = '<option value="all">Magic: Todos</option>' + 
                    magicNumbers.map(m => `<option value="${m}">${m}</option>`).join('');
            }
        } catch (error) {
            console.error('❌ Error cargando magic numbers:', error);
        }
        
        console.log('✅ Todos los filtros cargados');
        
    } catch (error) {
        console.error('❌ Error general cargando filtros:', error);
    }
}

// ============================================================================
// CARGA DE DATOS DEL DASHBOARD
// ============================================================================
async function loadDashboardData() {
    try {
        const source = document.getElementById('filterSource')?.value || 'all';
        const year = document.getElementById('filterYear')?.value || '2025';
        const type = document.getElementById('filterType')?.value || 'all';
        const symbol = document.getElementById('filterSymbol')?.value || 'all';
        const timeframe = document.getElementById('filterTimeframe')?.value || 'all';
        const magicNumber = document.getElementById('filterMagicNumberMain')?.value || 'all';
        
        const params = `source=${source}&year=${year}&type=${type}&symbol=${symbol}&timeframe=${timeframe}&magic_number=${magicNumber}`;
        
        const statsResponse = await fetch(`/api/stats?${params}`);
        const stats = await statsResponse.json();
        updateStats(stats);
        
        const monthlyResponse = await fetch(`/api/monthly-filtered?${params}`);
        const monthlyData = await monthlyResponse.json();
        updateMonthlyChart(monthlyData);
        
        const drawdownResponse = await fetch(`/api/drawdown-equity-daily?${params}`);
        const drawdownData = await drawdownResponse.json();
        updateDrawdownChart(drawdownData);
        
        const eaMonthlyResponse = await fetch(`/api/ea-monthly-performance?${params}`);
        const eaMonthlyData = await eaMonthlyResponse.json();
        updateEAMonthlyTable(eaMonthlyData);
        
        const lastUpdateResponse = await fetch('/api/last-update');
        const lastUpdate = await lastUpdateResponse.json();
        updateLastUpdate(lastUpdate);
        
    } catch (error) {
        console.error('Error cargando datos del dashboard:', error);
    }
}

async function applyFilters() {
    console.log('🔄 Aplicando filtros...');
    await loadDashboardData();
    await updateMaxDDYear(); // ← AÑADIR ESTA LÍNEA
}

// ============================================================================
// MAX DD POR AÑO
// ============================================================================
async function updateMaxDDYear() {
    const yearSelector = document.getElementById('yearSelectorMaxDD');
    const maxDDYearElement = document.getElementById('maxDDYear');
    const card = document.getElementById('maxDDYearCard');
    
    if (!yearSelector || !maxDDYearElement) {
        console.error('❌ No se encontraron elementos de Max DD Year');
        return;
    }
    
    const year = yearSelector.value;
    
    // ✅ OBTENER TODOS LOS FILTROS DEL DASHBOARD
    const source = document.getElementById('filterSource')?.value || 'all';
    const symbol = document.getElementById('filterSymbol')?.value || 'all';
    const timeframe = document.getElementById('filterTimeframe')?.value || 'all';
    const magicNumber = document.getElementById('filterMagicNumberMain')?.value || 'all';
    const type = document.getElementById('filterType')?.value || 'all';
    
    const params = `year=${year}&source=${source}&symbol=${symbol}&timeframe=${timeframe}&magic_number=${magicNumber}&type=${type}`;
    
    console.log('📊 Actualizando Max DD Year con filtros:', params);
    
    // Mostrar loading
    maxDDYearElement.textContent = '...';
    
    try {
        const response = await fetch(`/api/max-dd-year?${params}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        console.log('   Max DD:', data.max_dd, '% | Año:', data.year);
        
        // Mostrar valor como PORCENTAJE
        maxDDYearElement.textContent = `${data.max_dd.toFixed(2)}%`;
        
        // Aplicar colores según umbrales PORCENTUALES (menos DD es mejor)
        if (card) {
            card.classList.remove('kpi-green', 'kpi-yellow', 'kpi-red');
            
            if (data.max_dd <= 10) {
                card.classList.add('kpi-green');  // Verde: <= 10%
            } else if (data.max_dd <= 20) {
                card.classList.add('kpi-yellow'); // Amarillo: 10-20%
            } else {
                card.classList.add('kpi-red');    // Rojo: > 20%
            }
        }
        
        console.log('✅ Max DD Year actualizado');
        
    } catch (error) {
        console.error('❌ Error obteniendo Max DD Year:', error);
        maxDDYearElement.textContent = '-';
    }
}

// ============================================================================
// ACTUALIZAR ESTADÍSTICAS
// ============================================================================
function updateStats(stats) {
    // Función helper para valores seguros
    const safe = (value, decimals = 2) => {
        return (value !== undefined && value !== null && !isNaN(value)) ? Number(value).toFixed(decimals) : '0.' + '0'.repeat(decimals);
    };
    
    document.getElementById('netProfit').textContent = `$${safe(stats.net_profit, 2)}`;
    document.getElementById('totalTrades').textContent = stats.total_trades || 0;
    document.getElementById('totalEAsCount').textContent = stats.total_eas || 0;
    document.getElementById('winRate').textContent = `${safe(stats.win_rate, 1)}%`;
    document.getElementById('profitFactor').textContent = safe(stats.profit_factor, 2);
    document.getElementById('expectancy').textContent = safe(stats.expectancy, 2);
    document.getElementById('sharpe').textContent = safe(stats.sharpe_ratio, 2);
    document.getElementById('maxDD').textContent = `$${safe(stats.max_drawdown, 2)}`;
    
    document.getElementById('retdd').textContent = safe(stats.ret_dd, 2);
    document.getElementById('sqn').textContent = safe(stats.sqn, 2);
    document.getElementById('r2').textContent = safe(stats.r2_equity, 4);
    document.getElementById('cagr').textContent = `${safe(stats.cagr, 2)}%`;
    
    document.getElementById('rrRatio').textContent = safe(stats.rr_ratio, 2);
    
    document.getElementById('avgRecoveryMain').textContent = safe(stats.avg_recovery_days, 1);
    document.getElementById('consistencyMain').textContent = `${safe(stats.consistency_green_months, 1)}%`;
    
    // KPIs con colores - validar valores antes
    applyKPIColors('retddCard', stats.ret_dd || 0, 2.0, 3.0);
    applyKPIColors('sqnCard', stats.sqn || 0, 1.6, 2.5);
    applyKPIColors('r2Card', stats.r2_equity || 0, 0.70, 0.85);
    applyKPIColors('cagrCard', stats.cagr || 0, 5, 15);
    applyKPIColors('profitFactorCard', stats.profit_factor || 0, 1.20, 1.40);
    applyKPIColors('expectancyCard', stats.expectancy || 0, 0.10, 0.25);
    applyKPIColors('sharpeCard', stats.sharpe_ratio || 0, 1.00, 1.50);
    applyKPIColors('rrCard', stats.rr_ratio || 0, 1.5, 2.0);
}

function applyKPIColors(cardId, value, yellowThreshold, greenThreshold) {
    const card = document.getElementById(cardId);
    if (!card) {
        console.warn(`⚠️ Card no encontrada: ${cardId}`);
        return;
    }
    
    // Limpiar clases anteriores
    card.classList.remove('kpi-green', 'kpi-yellow', 'kpi-red');
    
    // Aplicar nueva clase según umbral
    if (value >= greenThreshold) {
        card.classList.add('kpi-green');
        console.log(`✅ ${cardId}: ${value} >= ${greenThreshold} → VERDE`);
    } else if (value >= yellowThreshold) {
        card.classList.add('kpi-yellow');
        console.log(`⚠️ ${cardId}: ${value} >= ${yellowThreshold} → AMARILLO`);
    } else {
        card.classList.add('kpi-red');
        console.log(`❌ ${cardId}: ${value} < ${yellowThreshold} → ROJO`);
    }
}

// ============================================================================
// GRÁFICO MENSUAL
// ============================================================================
function updateMonthlyChart(data) {
    const ctx = document.getElementById('monthlyChart');
    if (!ctx) return;
    
    if (monthlyChart) {
        monthlyChart.destroy();
    }
    
    const labels = data.map(d => d.month);
    const profits = data.map(d => d.profit);
    
    monthlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Profit Mensual',
                data: profits,
                backgroundColor: profits.map(p => p >= 0 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)'),
                borderColor: profits.map(p => p >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)'),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    callbacks: {
                        label: function(context) {
                            return `Profit: $${context.parsed.y.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#9ca3af' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9ca3af' }
                }
            }
        }
    });
}

// ============================================================================
// GRÁFICO DRAWDOWN
// ============================================================================
function updateDrawdownChart(data) {
    const ctx = document.getElementById('drawdownChart');
    if (!ctx) return;
    
    if (drawdownChart) {
        drawdownChart.destroy();
    }
    
    const labels = data.map(d => d.date);
    const equities = data.map(d => d.equity);
    const drawdowns = data.map(d => d.drawdown);
    
    drawdownChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Equity',
                    data: equities,
                    borderColor: 'rgb(16, 185, 129)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: false,
                    tension: 0.4,
                    borderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: 'Drawdown',
                    data: drawdowns,
                    borderColor: 'rgb(239, 68, 68)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
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
                    labels: { color: '#9ca3af' }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
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
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Equity ($)',
                        color: '#10b981'
                    },
                    grid: { color: 'rgba(16, 185, 129, 0.1)' },
                    ticks: { color: '#10b981' }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Drawdown ($)',
                        color: '#ef4444'
                    },
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#ef4444' }
                },
                x: {
                    grid: { display: false },
                    ticks: { 
                        color: '#9ca3af',
                        maxRotation: 45,
                        minRotation: 45
                    }
                }
            }
        }
    });
}

// ============================================================================
// TABLA DE EAs - CON ORDENAMIENTO
// ============================================================================
function updateEAMonthlyTable(data) {
    const tbody = document.getElementById('eaMonthlyTableBody');
    if (!tbody) return;
    
    eaTableData = data;
    
    if (data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="18" class="text-center p-8 text-gray-500">
                    <i class="fas fa-inbox text-4xl mb-2"></i>
                    <p>No hay datos disponibles con los filtros seleccionados</p>
                </td>
            </tr>
        `;
        return;
    }
    
    renderEATable(data);
}

function renderEATable(data) {
    const tbody = document.getElementById('eaMonthlyTableBody');
    const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
    
    tbody.innerHTML = data.map(ea => {
        let totalProfit = 0;
        let totalTrades = 0;
        let totalWinning = 0;
        
        let monthCells = months.map(month => {
            if (ea[month]) {
                totalProfit += ea[month].profit;
                totalTrades += ea[month].trades;
                if (ea[month].winning !== undefined) {
                    totalWinning += ea[month].winning;
                }
                const color = ea[month].profit >= 0 ? 'text-emerald-400' : 'text-red-400';
                
                return `
                    <td class="text-right p-2 ${color} cursor-pointer hover:bg-gray-700 transition-colors" 
                        onclick="showTradesDetail(${ea.magic_number}, '${month}')"
                        title="Click: ver ${ea[month].trades} trades de ${month}">
                        <div class="font-semibold">$${ea[month].profit.toFixed(2)}</div>
                        <div class="text-xs text-gray-400">(${ea[month].trades})</div>
                    </td>
                `;
            }
            return `<td class="text-right p-2 text-gray-600">-</td>`;
        }).join('');
        
        const monthsWithData = months.filter(m => ea[m]).length;
        const avgWinRate = monthsWithData > 0 ? (totalWinning / monthsWithData).toFixed(1) : '-';
        const retDD = ea.ret_dd !== undefined ? ea.ret_dd.toFixed(2) : '-';
        const maxConsecLoss = ea.max_consecutive_loss !== undefined ? ea.max_consecutive_loss : '-';
        const totalColor = totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400';
        const isSelected = selectedEA && selectedEA == ea.magic_number ? 'ea-row-selected' : '';
        
        return `
            <tr class="border-b border-gray-800 hover:bg-gray-800 transition-colors ${isSelected}">
                <td class="text-left p-2 font-semibold text-yellow-400 sticky left-0 bg-gray-900 cursor-pointer hover:bg-yellow-900"
                    onclick="filterByEA(${ea.magic_number})" 
                    title="Click: filtrar por EA ${ea.magic_number}">
                    ${ea.magic_number}
                    ${isSelected ? '<i class="fas fa-filter ml-2 text-xs"></i>' : ''}
                </td>
                ${monthCells}
                <td class="text-right p-2 font-bold ${totalColor}">$${totalProfit.toFixed(2)}</td>
                <td class="text-right p-2 text-gray-400">${totalTrades}</td>
                <td class="text-right p-2 text-blue-400">${avgWinRate}%</td>
                <td class="text-right p-2 text-purple-400">${retDD}</td>
                <td class="text-right p-2 text-red-400">${maxConsecLoss}</td>
            </tr>
        `;
    }).join('');
}

function sortEATable(column) {
    console.log('Ordenando por:', column);
    
    if (currentSortColumn === column) {
        currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortColumn = column;
        currentSortDirection = 'desc';
    }
    
    const sortedData = [...eaTableData].sort((a, b) => {
        let valueA, valueB;
        
        if (column === 'magic_number') {
            valueA = a.magic_number;
            valueB = b.magic_number;
        } else if (column === 'total') {
            const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
            valueA = months.reduce((sum, m) => sum + (a[m] ? a[m].profit : 0), 0);
            valueB = months.reduce((sum, m) => sum + (b[m] ? b[m].profit : 0), 0);
        } else if (column === 'trades') {
            const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
            valueA = months.reduce((sum, m) => sum + (a[m] ? a[m].trades : 0), 0);
            valueB = months.reduce((sum, m) => sum + (b[m] ? b[m].trades : 0), 0);
        } else if (column === 'winning') {
            const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
            const monthsWithDataA = months.filter(m => a[m]).length;
            const totalWinningA = months.reduce((sum, m) => sum + (a[m] ? a[m].winning : 0), 0);
            valueA = monthsWithDataA > 0 ? totalWinningA / monthsWithDataA : 0;
            
            const monthsWithDataB = months.filter(m => b[m]).length;
            const totalWinningB = months.reduce((sum, m) => sum + (b[m] ? b[m].winning : 0), 0);
            valueB = monthsWithDataB > 0 ? totalWinningB / monthsWithDataB : 0;
        } else if (column === 'ret_dd') {
            valueA = a.ret_dd || 0;
            valueB = b.ret_dd || 0;
        } else if (column === 'max_consecutive_loss') {
            valueA = a.max_consecutive_loss || 0;
            valueB = b.max_consecutive_loss || 0;
        } else {
            valueA = a[column] ? a[column].profit : -999999;
            valueB = b[column] ? b[column].profit : -999999;
        }
        
        if (currentSortDirection === 'asc') {
            return valueA > valueB ? 1 : -1;
        } else {
            return valueA < valueB ? 1 : -1;
        }
    });
    
    updateSortIndicators(column);
    renderEATable(sortedData);
}

function updateSortIndicators(column) {
    document.querySelectorAll('.sort-indicator').forEach(el => el.remove());
    
    const header = document.querySelector(`[data-sort="${column}"]`);
    if (header) {
        const indicator = document.createElement('i');
        indicator.className = `fas fa-${currentSortDirection === 'asc' ? 'arrow-up' : 'arrow-down'} sort-indicator ml-1 text-yellow-400`;
        header.appendChild(indicator);
    }
}

// ============================================================================
// FILTRAR POR EA
// ============================================================================
function filterByEA(magicNumber) {
    console.log('Filtrando por EA:', magicNumber);
    
    if (selectedEA === magicNumber) {
        selectedEA = null;
        document.getElementById('filterMagicNumberMain').value = 'all';
    } else {
        selectedEA = magicNumber;
        document.getElementById('filterMagicNumberMain').value = magicNumber;
    }
    
    applyFilters();
}

// ============================================================================
// MODAL DETALLE DE TRADES
// ============================================================================
async function showTradesDetail(magicNumber, month) {
    const modal = document.getElementById('tradesDetailModal');
    const title = document.getElementById('tradesDetailTitle');
    const tbody = document.getElementById('tradesDetailTableBody');
    
    title.textContent = `Trades del EA ${magicNumber} - ${month}`;
    
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
        const year = document.getElementById('filterYear')?.value || 'all';
        const response = await fetch(`/api/trades-detail?magic_number=${magicNumber}&month=${month}&year=${year}`);
        const trades = await response.json();
        
        if (trades.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center p-8 text-gray-500">
                        No hay trades para este período
                    </td>
                </tr>
            `;
            return;
        }
        
        const totalProfit = trades.reduce((sum, t) => sum + t.profit, 0);
        const winningTrades = trades.filter(t => t.profit > 0).length;
        const winRate = (winningTrades / trades.length * 100).toFixed(1);
        
        document.getElementById('modalTotalTrades').textContent = trades.length;
        document.getElementById('modalTotalProfit').textContent = `$${totalProfit.toFixed(2)}`;
        document.getElementById('modalWinRate').textContent = `${winRate}%`;
        
        tbody.innerHTML = trades.map(trade => {
            const profitColor = trade.profit >= 0 ? 'text-emerald-400' : 'text-red-400';
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800">
                    <td class="text-left p-2 text-gray-300">${trade.close_time}</td>
                    <td class="text-left p-2 text-white">${trade.symbol}</td>
                    <td class="text-left p-2 text-blue-400">${trade.type}</td>
                    <td class="text-right p-2 text-gray-300">${trade.lots.toFixed(2)}</td>
                    <td class="text-right p-2 text-gray-300">${trade.open_price.toFixed(5)}</td>
                    <td class="text-right p-2 text-gray-300">${trade.close_price.toFixed(5)}</td>
                    <td class="text-right p-2 font-bold ${profitColor}">$${trade.profit.toFixed(2)}</td>
                    <td class="text-left p-2 text-gray-400 text-xs">${trade.comment}</td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error cargando detalle de trades:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center p-8 text-red-500">
                    Error al cargar los trades
                </td>
            </tr>
        `;
    }
}

function closeTradesDetailPopup() {
    document.getElementById('tradesDetailModal').classList.add('hidden');
}

// ============================================================================
// ÚLTIMA ACTUALIZACIÓN
// ============================================================================
function updateLastUpdate(updates) {
    const lastUpdateEl = document.getElementById('lastUpdate');
    if (updates && updates.length > 0) {
        const latest = updates[0];
        const date = new Date(latest.last_update);
        lastUpdateEl.textContent = date.toLocaleString('es-ES');
    } else {
        lastUpdateEl.textContent = 'Sin actualizaciones';
    }
}

// ============================================================================
// ACTUALIZAR DATOS
// ============================================================================
async function updateData(event) {
    let button = null;
    let originalHTML = null;
    
    // Si hay un evento (se llamó desde un botón)
    if (event && event.target) {
        button = event.target.closest('button');
        if (button) {
            originalHTML = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin text-xs"></i> Actualizando...';
            button.disabled = true;
        }
    }
    
    try {
        console.log('🔄 Actualizando datos...');
        
        const response = await fetch('/api/update-data');
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ Datos actualizados');
        }
        
        await loadDashboardData();
        
    } catch (error) {
        console.error('❌ Error actualizando datos:', error);
        if (button) {
            alert('❌ Error al actualizar datos');
        }
    } finally {
        // Restaurar botón si existe
        if (button && originalHTML) {
            button.innerHTML = originalHTML;
            button.disabled = false;
        }
    }
}
// ============================================================================
// NAVEGACIÓN ENTRE TABS
// ============================================================================
function showTab(tabName) {
    document.querySelectorAll('[id$="-tab"]').forEach(tab => tab.classList.add('hidden'));
    document.getElementById(`${tabName}-tab`).classList.remove('hidden');
    
    document.querySelectorAll('.sidebar-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.classList.add('text-gray-400', 'hover:bg-gray-800');
    });
    
    event.target.closest('.sidebar-btn').classList.add('active');
    event.target.closest('.sidebar-btn').classList.remove('text-gray-400', 'hover:bg-gray-800');
    
    // Inicializar pestañas específicas
    if (tabName === 'caracteristicas') {
        initCaracteristicasEA();
    } else if (tabName === 'portfolio') {
        InitPortfolio();
    } else if (tabName === 'propfirms') {  // ← AÑADIR ESTO
        initPropfirms();
    }
}

// ============================================================================
// VERIFICACIÓN DE EAs
// ============================================================================
async function showVerifyEAsModal() {
    const modal = document.getElementById('verifyEAsModal');
    const tbody = document.getElementById('verifyEAsTableBody');
    
    tbody.innerHTML = `
        <tr>
            <td colspan="13" class="text-center p-8 text-gray-500">
                <i class="fas fa-spinner fa-spin text-2xl mb-2"></i>
                <p>Cargando verificación...</p>
            </td>
        </tr>
    `;
    
    modal.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/verify-eas');
        const data = await response.json();
        
        document.getElementById('verifyTotalEAs').textContent = data.total_eas;
        document.getElementById('verifyTotalTrades').textContent = data.total_trades_all;
        
        if (data.eas.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="13" class="text-center p-8 text-gray-500">
                        No hay EAs para verificar
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = data.eas.map(ea => {
            const profitColor = ea.total_profit >= 0 ? 'text-emerald-400' : 'text-red-400';
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800">
                    <td class="text-left p-2 font-semibold text-yellow-400">${ea.magic_number}</td>
                    <td class="text-right p-2 text-white">${ea.total_trades}</td>
                    <td class="text-left p-2 text-cyan-400">${ea.currency_pair || '-'}</td>
                    <td class="text-left p-2 text-blue-400">${ea.timeframe || '-'}</td>
                    <td class="text-left p-2 text-purple-400">${ea.direction || '-'}</td>
                    <td class="text-left p-2 text-gray-300 text-xs">${ea.strategy || '-'}</td>
                    <td class="text-right p-2 font-bold ${profitColor}">$${ea.total_profit.toFixed(2)}</td>
                    <td class="text-right p-2 text-green-400">${ea.win_rate.toFixed(1)}%</td>
                    <td class="text-left p-2 text-gray-400 text-xs">${ea.symbols.join(', ')}</td>
                    <td class="text-left p-2 text-gray-400 text-xs">${ea.sources.join(', ')}</td>
                    <td class="text-left p-2 text-gray-400 text-xs">${ea.first_trade}</td>
                    <td class="text-left p-2 text-gray-400 text-xs">${ea.last_trade}</td>
                    <td class="text-center p-2">
                        <button onclick="deleteEA(${ea.magic_number})" 
                                class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs"
                                title="Eliminar EA">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error verificando EAs:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="13" class="text-center p-8 text-red-500">
                    Error al cargar datos
                </td>
            </tr>
        `;
    }
}

function closeVerifyEAsModal() {
    document.getElementById('verifyEAsModal').classList.add('hidden');
}

// ============================================================================
// ELIMINAR EA
// ============================================================================
async function deleteEA(magicNumber) {
    const confirmation = confirm(
        `⚠️ ELIMINAR EA ${magicNumber}\n\n` +
        `Esto eliminará TODOS los trades de este EA.\n` +
        `Esta acción NO se puede deshacer.\n\n` +
        `¿Continuar?`
    );
    
    if (!confirmation) return;
    
    try {
        const response = await fetch('/api/delete-ea', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ magic_number: magicNumber })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            closeVerifyEAsModal();
            await loadDashboardData();
        } else {
            alert('❌ Error: ' + (result.error || 'Error desconocido'));
        }
        
    } catch (error) {
        console.error('Error eliminando EA:', error);
        alert('❌ Error de conexión: ' + error.message);
    }
}

// ============================================================================
// AÑADIR MAPEO INDIVIDUAL
// ============================================================================
async function showAddMappingModal() {
    const fromMagic = prompt('Magic Number ORIGEN (el que viene del CSV):');
    
    if (!fromMagic) return;
    
    const toMagic = prompt('Magic Number DESTINO (al que convertir):');
    
    if (!toMagic) return;
    
    try {
        const fromNum = parseInt(fromMagic);
        const toNum = parseInt(toMagic);
        
        if (isNaN(fromNum) || isNaN(toNum)) {
            alert('❌ Los magic numbers deben ser números');
            return;
        }
        
        const updateExisting = confirm(
            `Mapeo: ${fromNum} → ${toNum}\n\n` +
            `¿Actualizar también los trades existentes con el magic ${fromNum}?\n\n` +
            `SI = Actualizar ahora\n` +
            `NO = Solo para futuros trades`
        );
        
        const response = await fetch('/api/add-mapping', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_magic: fromNum,
                to_magic: toNum,
                update_existing: updateExisting
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            let message = result.message + '\n\n';
            
            if (result.existing_trades > 0) {
                if (result.trades_updated > 0) {
                    message += `✅ ${result.trades_updated} trades actualizados`;
                } else {
                    message += `💡 ${result.existing_trades} trades existentes NO modificados`;
                }
            }
            
            alert(message);
            await loadDashboardData();
        } else {
            alert('❌ Error: ' + (result.error || 'Error desconocido'));
        }
        
    } catch (error) {
        console.error('Error añadiendo mapeo:', error);
        alert('❌ Error: ' + error.message);
    }
}

// ============================================================================
// VER MAPEOS ACTIVOS
// ============================================================================
async function showActiveMappingsDetailed() {
    try {
        const response = await fetch('/api/active-mappings');
        const mappings = await response.json();
        
        if (mappings.length === 0) {
            alert('❌ No hay mapeos activos');
            return;
        }
        
        let message = `✅ MAPEOS ACTIVOS: ${mappings.length}\n\n`;
        
        mappings.forEach(m => {
            message += `${m.from} → ${m.to}\n`;
        });
        
        message += `\n💡 Para gestionar mapeos:\n`;
        message += `   • Añadir: Click en "Añadir Mapeo"\n`;
        message += `   • Eliminar: Edita el código o usa manage_eas.py`;
        
        alert(message);
        
    } catch (error) {
        console.error('Error:', error);
        alert('Error al cargar mapeos');
    }
}

// ============================================================================
// MODAL DE UNIFICACIÓN
// ============================================================================
function showUnifyModal() {
    const modal = document.getElementById('unifyModal');
    modal.classList.remove('hidden');
    
    const tbody = document.getElementById('unifyMappingsBody');
    tbody.innerHTML = '';
    
    addUnifyRow();
}

function closeUnifyModal() {
    document.getElementById('unifyModal').classList.add('hidden');
}

function addUnifyRow() {
    const tbody = document.getElementById('unifyMappingsBody');
    const rowId = `unify-row-${Date.now()}`;
    
    const row = document.createElement('tr');
    row.id = rowId;
    row.className = 'border-b border-gray-700';
    row.innerHTML = `
        <td class="p-2">
            <input type="number" class="from-magic bg-gray-800 border border-gray-700 rounded px-2 py-1 w-full text-white" placeholder="123456">
        </td>
        <td class="p-2 text-center text-yellow-400 font-bold">→</td>
        <td class="p-2">
            <input type="number" class="to-magic bg-gray-800 border border-gray-700 rounded px-2 py-1 w-full text-white" placeholder="654321">
        </td>
        <td class="p-2 text-center">
            <button onclick="removeUnifyRow('${rowId}')" class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs">
                <i class="fas fa-times"></i>
            </button>
        </td>
    `;
    
    tbody.appendChild(row);
}

function removeUnifyRow(rowId) {
    const row = document.getElementById(rowId);
    if (row) {
        row.remove();
    }
}

function loadPresetMappings() {
    const tbody = document.getElementById('unifyMappingsBody');
    tbody.innerHTML = '';
    
    const presetMappings = [
        { from: 21020, to: 210201 },
        { from: 11111, to: 41193 },
        { from: 54332, to: 5433 },
        { from: 4119, to: 41193 },
        { from: 2120, to: 21201 },
        { from: 43336, to: 4333 },
        { from: 21204, to: 212041 },
        { from: 2123, to: 21231 },
        { from: 5434, to: 54341 },
        { from: 31204, to: 312041 },
        { from: 24455, to: 24451 },
        { from: 24456, to: 24461 },
        { from: 24457, to: 24471 },
        { from: 31205, to: 312051 },
        { from: 541, to: 5411 },
        { from: 31206, to: 312061 },
        { from: 21205, to: 212051 },
        { from: 21207, to: 212071 },
        { from: 6574, to: 65741 }
    ];
    
    presetMappings.forEach(mapping => {
        const rowId = `unify-row-${Date.now()}-${Math.random()}`;
        const row = document.createElement('tr');
        row.id = rowId;
        row.className = 'border-b border-gray-700';
        row.innerHTML = `
            <td class="p-2">
                <input type="number" class="from-magic bg-gray-800 border border-gray-700 rounded px-2 py-1 w-full text-white" value="${mapping.from}">
            </td>
            <td class="p-2 text-center text-yellow-400 font-bold">→</td>
            <td class="p-2">
                <input type="number" class="to-magic bg-gray-800 border border-gray-700 rounded px-2 py-1 w-full text-white" value="${mapping.to}">
            </td>
            <td class="p-2 text-center">
                <button onclick="removeUnifyRow('${rowId}')" class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs">
                    <i class="fas fa-times"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function executeUnification() {
    const rows = document.querySelectorAll('#unifyMappingsBody tr');
    
    const mappings = [];
    rows.forEach(row => {
        const fromInput = row.querySelector('.from-magic');
        const toInput = row.querySelector('.to-magic');
        
        if (fromInput && toInput && fromInput.value && toInput.value) {
            mappings.push({
                from: parseInt(fromInput.value),
                to: parseInt(toInput.value)
            });
        }
    });
    
    if (mappings.length === 0) {
        alert('❌ No hay mapeos para ejecutar');
        return;
    }
    
    const confirmation = confirm(
        `⚠️ EJECUTAR UNIFICACIÓN\n\n` +
        `Se van a unificar ${mappings.length} magic numbers.\n` +
        `Esta acción modificará los trades existentes.\n\n` +
        `¿Continuar?`
    );
    
    if (!confirmation) return;
    
    try {
        const response = await fetch('/api/unify-magic-numbers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mappings: mappings })
        });
        
        const result = await response.json();
        
        if (result.success) {
            let message = `✅ UNIFICACIÓN COMPLETADA\n\n`;
            message += `Total mapeos: ${result.total_mappings}\n`;
            message += `Trades actualizados: ${result.total_trades_updated}\n\n`;
            message += result.message;
            
            alert(message);
            closeUnifyModal();
            await loadDashboardData();
        } else {
            alert('❌ Error: ' + (result.error || 'Error desconocido'));
        }
        
    } catch (error) {
        console.error('Error ejecutando unificación:', error);
        alert('❌ Error de conexión: ' + error.message);
    }
}

// ============================================================================
// RESET TRADES
// ============================================================================
async function resetAllTrades() {
    const confirmation = confirm(
        `⚠️ ATENCIÓN - ELIMINAR TODOS LOS TRADES\n\n` +
        `Esto eliminará TODOS los trades de la base de datos.\n` +
        `Los mapeos de unificación se mantendrán.\n\n` +
        `Después deberás hacer click en "Actualizar Datos".\n\n` +
        `¿Estás SEGURO de que quieres continuar?`
    );
    
    if (!confirmation) return;
    
    const doubleCheck = prompt('Escribe "ELIMINAR" para confirmar (en mayúsculas):');
    
    if (doubleCheck !== 'ELIMINAR') {
        alert('❌ Operación cancelada');
        return;
    }
    
    try {
        const response = await fetch('/api/reset-trades', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(
                `✅ RESET COMPLETADO\n\n` +
                `Trades eliminados: ${result.trades_deleted}\n` +
                `Mapeos conservados: ${result.mappings_preserved}\n\n` +
                `Ahora haz click en "Actualizar Datos" para reimportar.`
            );
            
            await loadDashboardData();
        } else {
            alert('❌ Error: ' + (result.error || 'Error desconocido'));
        }
        
    } catch (error) {
        console.error('Error en reset:', error);
        alert('❌ Error de conexión: ' + error.message);
    }
}

// Cuando se carga la página o después de updateData()
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Inicializando Dashboard...');
    
    await loadFilters();
    await loadDashboardData(); // ← Cambiar esto, no llamar updateData()
    await updateMaxDDYear(); // ← Cargar Max DD Year inicial
    
    console.log('✅ Dashboard inicializado');
});