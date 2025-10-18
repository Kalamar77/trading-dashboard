// ============================================================================
// CUENTA REAL - JAVASCRIPT
// ============================================================================

let cuentaRealMonthlyChart = null;
let cuentaRealDrawdownChart = null;

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
async function initCuentaReal() {
    console.log('🚀 Inicializando Cuenta Real...');
    
    await loadCuentaRealSources();
    await loadCuentaRealData();
    
    console.log('✅ Cuenta Real inicializada');
}

// ============================================================================
// CARGAR SOURCES (CUENTAS)
// ============================================================================
async function loadCuentaRealSources() {
    try {
        const response = await fetch('/api/cuenta-real/sources');
        const sources = await response.json();
        
        const select = document.getElementById('filterCuentaRealAccount');
        
        if (!select) return;
        
        if (sources.length === 0) {
            select.innerHTML = '<option value="all">Sin cuentas cargadas</option>';
            select.disabled = true;
            return;
        }
        
        select.disabled = false;
        select.innerHTML = '<option value="all">Todas las cuentas</option>' +
            sources.map(s => `<option value="${s.account_name}">${s.account_name} (${s.total_trades} trades)</option>`).join('');
        
    } catch (error) {
        console.error('Error cargando sources:', error);
    }
}

// ============================================================================
// CARGAR DATOS
// ============================================================================
async function loadCuentaRealData() {
    try {
        const account = document.getElementById('filterCuentaRealAccount')?.value || 'all';
        const year = document.getElementById('filterCuentaRealYear')?.value || 'all';
        
        const params = `account=${account}&year=${year}`;
        
        // Estadísticas
        const statsResponse = await fetch(`/api/cuenta-real/stats?${params}`);
        const stats = await statsResponse.json();
        updateCuentaRealStats(stats);
        
        // Gráfico mensual
        const monthlyResponse = await fetch(`/api/cuenta-real/monthly?${params}`);
        const monthlyData = await monthlyResponse.json();
        updateCuentaRealMonthlyChart(monthlyData);
        
        // Gráfico equity/DD
        const equityResponse = await fetch(`/api/cuenta-real/equity-dd?${params}`);
        const equityData = await equityResponse.json();
        updateCuentaRealDrawdownChart(equityData);
        
        // Tabla EA mensual
        const eaMonthlyResponse = await fetch(`/api/cuenta-real/ea-monthly?${params}`);
        const eaMonthlyData = await eaMonthlyResponse.json();
        updateCuentaRealEAMonthlyTable(eaMonthlyData);
        
        // Portfolio
        await loadCuentaRealPortfolio();  // ← AÑADIR ESTA LÍNEA
        
    } catch (error) {
        console.error('Error cargando datos cuenta real:', error);
    }
}

function applyCuentaRealFilters() {
    console.log('🔄 Aplicando filtros cuenta real...');
    loadCuentaRealData();
}

// ============================================================================
// ACTUALIZAR ESTADÍSTICAS
// ============================================================================
function updateCuentaRealStats(stats) {
    document.getElementById('cuentaRealNetProfit').textContent = `$${stats.net_profit.toFixed(2)}`;
    document.getElementById('cuentaRealTotalTrades').textContent = stats.total_trades;
    document.getElementById('cuentaRealWinRate').textContent = `${stats.win_rate.toFixed(1)}%`;
    document.getElementById('cuentaRealProfitFactor').textContent = stats.profit_factor.toFixed(2);
    document.getElementById('cuentaRealExpectancy').textContent = stats.expectancy.toFixed(2);
    document.getElementById('cuentaRealSharpe').textContent = stats.sharpe_ratio.toFixed(2);
    document.getElementById('cuentaRealMaxDD').textContent = `${stats.max_dd_percent.toFixed(2)}%`;
    
    document.getElementById('cuentaRealRetDD').textContent = stats.ret_dd.toFixed(2);
    document.getElementById('cuentaRealSQN').textContent = stats.sqn.toFixed(2);
    document.getElementById('cuentaRealR2').textContent = stats.r2_equity.toFixed(4);
    document.getElementById('cuentaRealCAGR').textContent = `${stats.cagr.toFixed(2)}%`;
    document.getElementById('cuentaRealRR').textContent = stats.rr_ratio.toFixed(2);
    
    document.getElementById('cuentaRealAvgRecovery').textContent = stats.avg_recovery_days.toFixed(1);
    document.getElementById('cuentaRealConsistency').textContent = `${stats.consistency_green_months.toFixed(1)}%`;
    
    // Aplicar colores a KPIs
    applyKPIColors('cuentaRealRetDDCard', stats.ret_dd, 2.0, 3.0);
    applyKPIColors('cuentaRealSQNCard', stats.sqn, 1.6, 2.5);
    applyKPIColors('cuentaRealR2Card', stats.r2_equity, 0.70, 0.85);
    applyKPIColors('cuentaRealCAGRCard', stats.cagr, 5, 15);
    applyKPIColors('cuentaRealProfitFactorCard', stats.profit_factor, 1.20, 1.40);
    applyKPIColors('cuentaRealExpectancyCard', stats.expectancy, 0.10, 0.25);
    applyKPIColors('cuentaRealSharpeCard', stats.sharpe_ratio, 1.00, 1.50);
    applyKPIColors('cuentaRealRRCard', stats.rr_ratio, 1.5, 2.0);
    applyKPIColors('cuentaRealAvgRecoveryCard', stats.avg_recovery_days, 30, 15, true);
    applyKPIColors('cuentaRealConsistencyCard', stats.consistency_green_months, 60, 80);
}

// ============================================================================
// GRÁFICO MENSUAL
// ============================================================================
function updateCuentaRealMonthlyChart(data) {
    const ctx = document.getElementById('cuentaRealMonthlyChart');
    if (!ctx) return;
    
    if (cuentaRealMonthlyChart) {
        cuentaRealMonthlyChart.destroy();
    }
    
    const labels = data.map(d => d.month);
    const profits = data.map(d => d.profit);
    
    cuentaRealMonthlyChart = new Chart(ctx, {
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
function updateCuentaRealDrawdownChart(data) {
    const ctx = document.getElementById('cuentaRealDrawdownChart');
    if (!ctx) return;
    
    if (cuentaRealDrawdownChart) {
        cuentaRealDrawdownChart.destroy();
    }
    
    cuentaRealDrawdownChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Equity',
                    data: data.equity,
                    borderColor: 'rgb(16, 185, 129)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: false,
                    tension: 0.4,
                    borderWidth: 2,
                    yAxisID: 'y'
                },
                {
                    label: 'Drawdown',
                    data: data.drawdown,
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
                    labels: { color: '#9ca3af' }
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
// TABLA DE TRADES
// ============================================================================
function updateCuentaRealTradesTable(trades) {
    const tbody = document.getElementById('cuentaRealTradesTableBody');
    
    if (!tbody) return;
    
    if (trades.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center p-8 text-gray-500">
                    No hay trades
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = trades.map(trade => {
        const profitColor = trade.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400';
        const resultColor = trade.result === 'Win' ? 'text-green-400' : 'text-red-400';
        
        return `
            <tr class="border-b border-gray-800 hover:bg-gray-800">
                <td class="text-left p-2 text-gray-300">${trade.close_date}</td>
                <td class="text-left p-2 text-cyan-400">${trade.symbol}</td>
                <td class="text-left p-2 ${trade.type === 'Buy' ? 'text-green-400' : 'text-red-400'}">${trade.type}</td>
                <td class="text-right p-2 text-gray-300">${trade.lots.toFixed(2)}</td>
                <td class="text-right p-2 font-bold ${profitColor}">$${trade.net_profit.toFixed(2)}</td>
                <td class="text-center p-2 ${resultColor}">${trade.result}</td>
                <td class="text-center p-2 text-gray-300">${trade.ticket}</td>
            </tr>
        `;
    }).join('');
}

// ============================================================================
// SUBIR CSV
// ============================================================================
function triggerCuentaRealUpload() {
    document.getElementById('cuentaRealFileInput').click();
}

async function handleCuentaRealUpload(event) {
    const file = event.target.files[0];
    
    if (!file) return;
    
    const accountName = prompt('Nombre de la cuenta:', 'Cuenta Real');
    
    if (!accountName) return;
    
    const button = document.getElementById('uploadCuentaRealButton');
    const originalText = button.innerHTML;
    
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Subiendo...';
    button.disabled = true;
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('account_name', accountName);
        
        const response = await fetch('/api/cuenta-real/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`✅ ${result.message}\n\nCuenta: ${result.account_name}\nTrades: ${result.total_trades}\nProfit: $${result.net_profit.toFixed(2)}`);
            
            await loadCuentaRealSources();
            await loadCuentaRealData();
        } else {
            alert('❌ Error: ' + result.error);
        }
        
    } catch (error) {
        console.error('Error subiendo CSV:', error);
        alert('❌ Error: ' + error.message);
    } finally {
        button.innerHTML = originalText;
        button.disabled = false;
        event.target.value = '';
    }
}

// ============================================================================
// TABLA EA MENSUAL
// ============================================================================
function updateCuentaRealEAMonthlyTable(data) {
    const tbody = document.getElementById('cuentaRealEAMonthlyTableBody');
    
    if (!tbody) return;
    
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
    
    const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
    
    tbody.innerHTML = data.map(ea => {
        let totalProfit = 0;
        let totalTrades = 0;
        let totalWinning = 0;
        let monthsWithData = 0;
        
        let monthCells = months.map(month => {
            if (ea[month]) {
                totalProfit += ea[month].profit;
                totalTrades += ea[month].trades;
                totalWinning += ea[month].winning;
                monthsWithData++;
                
                const color = ea[month].profit >= 0 ? 'text-emerald-400' : 'text-red-400';
                
                return `
                    <td class="text-right p-2 ${color} cursor-pointer hover:bg-gray-800 transition-colors" 
                        onclick="showCuentaRealTradesDetail(${ea.magic_number}, '${month}')"
                        title="Click para ver ${ea[month].trades} trades de ${month}">
                        <div class="font-semibold">$${ea[month].profit.toFixed(2)}</div>
                        <div class="text-xs text-gray-400">(${ea[month].trades})</div>
                    </td>
                `;
            }
            return `<td class="text-right p-2 text-gray-600">-</td>`;
        }).join('');
        
        const avgWinRate = monthsWithData > 0 ? (totalWinning / monthsWithData).toFixed(1) : '0.0';
        const retDD = ea.ret_dd !== undefined ? ea.ret_dd.toFixed(2) : '-';
        const maxConsecLoss = ea.max_consecutive_loss !== undefined ? ea.max_consecutive_loss : '-';
        const totalColor = totalProfit >= 0 ? 'text-emerald-400' : 'text-red-400';
        
        return `
            <tr class="border-b border-gray-800 hover:bg-gray-800 transition-colors">
                <td class="text-left p-2 font-semibold text-yellow-400 sticky left-0 bg-gray-900">
                    ${ea.magic_number}
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

// ============================================================================
// MODAL DETALLE DE TRADES
// ============================================================================
async function showCuentaRealTradesDetail(magicNumber, month) {
    const modal = document.getElementById('tradesDetailModal');
    const title = document.getElementById('tradesDetailTitle');
    const tbody = document.getElementById('tradesDetailTableBody');
    
    const year = document.getElementById('filterCuentaRealYear')?.value || 'all';
    const account = document.getElementById('filterCuentaRealAccount')?.value || 'all';
    
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
        const params = `magic_number=${magicNumber}&month=${month}&year=${year}&account=${account}`;
        const response = await fetch(`/api/cuenta-real/trades-detail?${params}`);
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
                    <td class="text-left p-2 text-gray-400 text-xs">${trade.comment || '-'}</td>
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

// ============================================================================
// GESTIÓN DE PORTFOLIO
// ============================================================================
async function loadCuentaRealPortfolio() {
    try {
        const account = document.getElementById('filterCuentaRealAccount')?.value || 'all';
        
        const response = await fetch(`/api/cuenta-real/portfolio-list?account=${account}`);
        const eas = await response.json();
        
        updateCuentaRealPortfolioTable(eas);
        
    } catch (error) {
        console.error('Error cargando portfolio:', error);
    }
}

function updateCuentaRealPortfolioTable(eas) {
    const tbody = document.getElementById('cuentaRealPortfolioTableBody');
    
    if (!tbody) return;
    
    // AÑADIR ESTA VALIDACIÓN
    if (!Array.isArray(eas)) {
    console.error('Error: eas no es un array', eas);
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="text-center p-8 text-red-500">
                <i class="fas fa-exclamation-triangle text-4xl mb-2"></i>
                <p>Error cargando portfolio: ${eas.error || 'Error desconocido'}</p>
            </td>
        </tr>
    `;
    return;
}

if (eas.length === 0) {
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="text-center p-8 text-gray-500">
                <i class="fas fa-inbox text-4xl mb-2"></i>
                <p>No hay EAs en la cuenta seleccionada</p>
            </td>
        </tr>
    `;
    return;
}
    
    tbody.innerHTML = eas.map(ea => `
    <tr class="border-b border-gray-800 hover:bg-gray-800">
        <td class="text-left p-2 text-cyan-400 font-semibold">${ea.ea_name || 'EA ' + ea.magic_number}</td>
        <td class="text-center p-2 text-yellow-400 font-semibold">${ea.magic_number}</td>
        <td class="text-right p-2">
            <input type="number" 
                   class="bg-gray-800 border border-gray-700 rounded px-2 py-1 w-24 text-white text-right"
                   value="${ea.riesgo || 0}"
                   onchange="saveCuentaRealPortfolioField(${ea.magic_number}, 'riesgo', this.value)"
                   placeholder="0">
        </td>
        <td class="text-center p-2">
            <input type="date" 
                   class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white"
                   value="${ea.fecha_futura || ''}"
                   onchange="saveCuentaRealPortfolioField(${ea.magic_number}, 'fecha_futura', this.value)">
        </td>
        <td class="text-left p-2">
            <input type="text" 
                   class="bg-gray-800 border border-gray-700 rounded px-2 py-1 w-full text-white"
                   value="${ea.comentario || ''}"
                   onchange="saveCuentaRealPortfolioField(${ea.magic_number}, 'comentario', this.value)"
                   placeholder="Añadir comentario...">
        </td>
        <td class="text-center p-2">
            <button onclick="saveCuentaRealPortfolioRow(${ea.magic_number})" 
                    class="bg-green-600 hover:bg-green-700 px-3 py-1 rounded text-xs"
                    title="Guardar">
                <i class="fas fa-save"></i>
            </button>
        </td>
    </tr>
`).join('');
}
async function saveCuentaRealPortfolioField(magicNumber, field, value) {
    // Auto-guardado al cambiar un campo
    const row = event.target.closest('tr');
    const riesgo = row.querySelector('input[type="number"]').value;
    const fecha = row.querySelector('input[type="date"]').value;
    const comentario = row.querySelector('input[type="text"]').value;
    
    try {
        const response = await fetch('/api/cuenta-real/portfolio-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                magic_number: magicNumber,
                riesgo: parseFloat(riesgo) || 0,
                fecha_futura: fecha,
                comentario: comentario
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Actualizar total
            await loadCuentaRealPortfolio();
        }
        
    } catch (error) {
        console.error('Error guardando portfolio:', error);
    }
}

async function saveCuentaRealPortfolioRow(magicNumber) {
    const row = event.target.closest('tr');
    const riesgo = row.querySelector('input[type="number"]').value;
    const fecha = row.querySelector('input[type="date"]').value;
    const comentario = row.querySelector('input[type="text"]').value;
    
    try {
        const response = await fetch('/api/cuenta-real/portfolio-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                magic_number: magicNumber,
                riesgo: parseFloat(riesgo) || 0,
                fecha_futura: fecha,
                comentario: comentario
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert('✅ Portfolio guardado correctamente');
            await loadCuentaRealPortfolio();
        } else {
            alert('❌ Error: ' + result.error);
        }
        
    } catch (error) {
        console.error('Error guardando portfolio:', error);
        alert('❌ Error de conexión');
    }
}