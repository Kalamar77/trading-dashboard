// ============================================================================
// GESTIÓN DE PORTAFOLIOS
// ============================================================================

let portfolioEAs = []; // Array de EAs en el portafolio

// ============================================================================
// AÑADIR EA AL PORTAFOLIO
// ============================================================================
function addToPortfolio(magicNumber, activo, caracteristicas) {
    console.log(`➕ Añadiendo EA ${magicNumber} al portafolio`);
    
    // Verificar si ya está en el portafolio
    if (portfolioEAs.find(ea => ea.magic_number === magicNumber)) {
        showNotification('⚠️ Este EA ya está en el portafolio', 'warning');
        return;
    }
    
    // Añadir al array
    portfolioEAs.push({
        magic_number: magicNumber,
        activo: activo,
        caracteristicas: caracteristicas
    });
    
    // Guardar en localStorage
    localStorage.setItem('portfolioEAs', JSON.stringify(portfolioEAs));
    
    showNotification(`✅ ${activo} (${caracteristicas}) añadido al portafolio`, 'success');
    
    console.log('📊 Portafolio actual:', portfolioEAs);
    
    // Actualizar vista si estamos en la pestaña de portfolio
    const portfolioTab = document.getElementById('portfolio-tab');
    if (portfolioTab && !portfolioTab.classList.contains('hidden')) {
        renderPortfolioEAsList();
        loadPortfolioData();
    }
}

// ============================================================================
// RENDERIZAR TABLA DE EAs EN PORTAFOLIO
// ============================================================================
async function renderPortfolioEAsList() {
    const tbody = document.getElementById('portfolioEAsTableBody');
    
    if (!tbody) return;
    
    if (portfolioEAs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center p-8 text-gray-500">
                    <i class="fas fa-inbox text-4xl mb-2"></i>
                    <p>No hay EAs en el portafolio</p>
                    <p class="text-sm mt-2">Ve a Características Técnicas y añade EAs usando el botón verde</p>
                </td>
            </tr>
        `;
        return;
    }
    
    // Cargar detalles completos de cada EA desde la BD
    try {
        const magicNumbers = portfolioEAs.map(ea => ea.magic_number).join(',');
        const response = await fetch(`/api/portfolio/ea-details?magic_numbers=${magicNumbers}`);
        const easDetails = await response.json();
        
        tbody.innerHTML = easDetails.map(ea => {
            // Color según dirección
            let direccionColor = 'text-gray-400';
            if (ea.direccion.includes('Buy') && !ea.direccion.includes('Sell')) {
                direccionColor = 'text-green-400';
            } else if (ea.direccion.includes('Sell') && !ea.direccion.includes('Buy')) {
                direccionColor = 'text-red-400';
            } else if (ea.direccion.includes('Buy/Sell')) {
                direccionColor = 'text-yellow-400';
            }
            
            return `
                <tr class="border-b border-gray-800 hover:bg-gray-800 transition-colors">
                    <td class="text-left p-2 text-cyan-400 font-semibold">${ea.activo || '-'}</td>
                    <td class="text-left p-2 font-semibold ${direccionColor}">${ea.direccion || '-'}</td>
                    <td class="text-center p-2 text-blue-400">${ea.timeframe || '-'}</td>
                    <td class="text-left p-2 text-gray-300">${ea.caracteristicas || '-'}</td>
                    <td class="text-center p-2 text-purple-400">${ea.walk_forward || '-'}</td>
                    <td class="text-center p-2 text-yellow-400">${ea.fecha_futura || '-'}</td>
                    <td class="text-center p-2 text-emerald-400 font-semibold">${ea.magic_number}</td>
                    <td class="text-center p-2">
                        <button onclick="removeFromPortfolio(${ea.magic_number})" 
                                class="bg-red-600 hover:bg-red-700 px-2 py-1 rounded text-xs"
                                title="Eliminar del portfolio">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error cargando detalles de EAs:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center p-4 text-red-500">
                    Error cargando detalles de los EAs
                </td>
            </tr>
        `;
    }
}
// ============================================================================
// ELIMINAR EA DEL PORTAFOLIO
// ============================================================================
function removeFromPortfolio(magicNumber) {
    portfolioEAs = portfolioEAs.filter(ea => ea.magic_number !== magicNumber);
    localStorage.setItem('portfolioEAs', JSON.stringify(portfolioEAs));
    
    showNotification('🗑️ EA eliminado del portafolio', 'info');
    
    renderPortfolioEAsList();
    loadPortfolioData();
}

// ============================================================================
// LIMPIAR TODO EL PORTAFOLIO
// ============================================================================
function clearPortfolio() {
    if (!confirm('¿Estás seguro de que quieres eliminar todos los EAs del portafolio?')) {
        return;
    }
    
    portfolioEAs = [];
    localStorage.setItem('portfolioEAs', JSON.stringify(portfolioEAs));
    
    showNotification('🗑️ Portafolio limpiado', 'info');
    
    renderPortfolioEAsList();
    loadPortfolioData();
}

// ============================================================================
// CARGAR DATOS DEL PORTAFOLIO
// ============================================================================
async function loadPortfolioData() {
    console.log('📊 Cargando datos del portafolio...');
    
    if (portfolioEAs.length === 0) {
        resetPortfolioUI();
        return;
    }
    
    try {
        const magicNumbers = portfolioEAs.map(ea => ea.magic_number).join(',');
        
        // Cargar stats
        const statsResponse = await fetch(`/api/portfolio/stats?magic_numbers=${magicNumbers}`);
        const stats = await statsResponse.json();
        updatePortfolioStats(stats);
        
        // Cargar gráfico mensual
        const monthlyResponse = await fetch(`/api/portfolio/monthly?magic_numbers=${magicNumbers}`);
        const monthlyData = await monthlyResponse.json();
        updatePortfolioMonthlyChart(monthlyData);
        
        // Cargar gráfico de drawdown
        const drawdownResponse = await fetch(`/api/portfolio/drawdown?magic_numbers=${magicNumbers}`);
        const drawdownData = await drawdownResponse.json();
        updatePortfolioDrawdownChart(drawdownData);
        
        // Cargar análisis mensual por EA
        const eaMonthlyResponse = await fetch(`/api/portfolio/ea-monthly?magic_numbers=${magicNumbers}`);
        const eaMonthlyData = await eaMonthlyResponse.json();
        updatePortfolioEAMonthlyTable(eaMonthlyData);
        
        await updatePortfolioMaxDDYear();
        console.log('✅ Datos del portafolio cargados');
        
    } catch (error) {
        console.error('❌ Error cargando datos del portafolio:', error);
        showNotification('Error cargando datos del portafolio', 'error');
    }
}

// ============================================================================
// ACTUALIZAR STATS DEL PORTAFOLIO
// ============================================================================
function updatePortfolioStats(stats) {
    document.getElementById('portfolioNetProfit').textContent = `$${stats.net_profit.toFixed(2)}`;
    document.getElementById('portfolioRetdd').textContent = stats.ret_dd.toFixed(2);
    document.getElementById('portfolioSqn').textContent = stats.sqn.toFixed(2);
    document.getElementById('portfolioR2').textContent = stats.r2_equity.toFixed(4);
    document.getElementById('portfolioCagr').textContent = `${stats.cagr.toFixed(2)}%`;
    document.getElementById('portfolioProfitFactor').textContent = stats.profit_factor.toFixed(2);
    document.getElementById('portfolioExpectancy').textContent = stats.expectancy.toFixed(2);
    document.getElementById('portfolioSharpe').textContent = stats.sharpe_ratio.toFixed(2);
    document.getElementById('portfolioRr').textContent = stats.rr_ratio.toFixed(2);
    document.getElementById('portfolioTotalTrades').textContent = stats.total_trades;
    document.getElementById('portfolioWinRate').textContent = `${stats.win_rate.toFixed(1)}%`;
    
    // Aplicar colores
    applyKPIColors('portfolioRetddCard', stats.ret_dd, 2.0, 3.0);
    applyKPIColors('portfolioSqnCard', stats.sqn, 1.6, 2.5);
    applyKPIColors('portfolioR2Card', stats.r2_equity, 0.70, 0.85);
    applyKPIColors('portfolioCagrCard', stats.cagr, 5, 15);
    applyKPIColors('portfolioProfitFactorCard', stats.profit_factor, 1.20, 1.40);
    applyKPIColors('portfolioExpectancyCard', stats.expectancy, 0.10, 0.25);
    applyKPIColors('portfolioSharpeCard', stats.sharpe_ratio, 1.00, 1.50);
    applyKPIColors('portfolioRrCard', stats.rr_ratio, 1.5, 2.0);
}

// ============================================================================
// RESETEAR UI
// ============================================================================
function resetPortfolioUI() {
    document.getElementById('portfolioNetProfit').textContent = '$0.00';
    document.getElementById('portfolioRetdd').textContent = '0.00';
    document.getElementById('portfolioSqn').textContent = '0.00';
    document.getElementById('portfolioR2').textContent = '0.0000';
    document.getElementById('portfolioCagr').textContent = '0.00%';
    document.getElementById('portfolioProfitFactor').textContent = '0.00';
    document.getElementById('portfolioExpectancy').textContent = '0.00';
    document.getElementById('portfolioSharpe').textContent = '0.00';
    document.getElementById('portfolioRr').textContent = '0.00';
    document.getElementById('portfolioTotalTrades').textContent = '0';
    document.getElementById('portfolioWinRate').textContent = '0.0%';
    
    // Limpiar gráficos
    if (window.portfolioMonthlyChartInstance) {
        window.portfolioMonthlyChartInstance.destroy();
    }
    if (window.portfolioDrawdownChartInstance) {
        window.portfolioDrawdownChartInstance.destroy();
    }
}

// ============================================================================
// GRÁFICO DE RENTABILIDAD MENSUAL
// ============================================================================
function updatePortfolioMonthlyChart(data) {
    const canvas = document.getElementById('portfolioMonthlyChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Destruir gráfico existente
    if (window.portfolioMonthlyChartInstance) {
        window.portfolioMonthlyChartInstance.destroy();
    }
    
    if (!data || data.length === 0) {
        return;
    }
    
    const labels = data.map(d => d.month);
    const profits = data.map(d => d.profit);
    
    const colors = profits.map(p => p >= 0 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)');
    
    window.portfolioMonthlyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Profit/Loss Mensual',
                data: profits,
                backgroundColor: colors,
                borderColor: colors.map(c => c.replace('0.8', '1')),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => `$${context.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(75, 85, 99, 0.2)' },
                    ticks: {
                        color: '#9CA3AF',
                        callback: (value) => `$${value.toFixed(0)}`
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9CA3AF' }
                }
            }
        }
    });
}

// ============================================================================
// GRÁFICO DE EQUITY Y DRAWDOWN
// ============================================================================
function updatePortfolioDrawdownChart(data) {
    const canvas = document.getElementById('portfolioDrawdownChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Destruir gráfico existente
    if (window.portfolioDrawdownChartInstance) {
        window.portfolioDrawdownChartInstance.destroy();
    }
    
    if (!data || data.length === 0) {
        return;
    }
    
    const labels = data.map(d => d.date);
    const equity = data.map(d => d.equity);
    const drawdown = data.map(d => d.drawdown);
    
    window.portfolioDrawdownChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Equity',
                    data: equity,
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    yAxisID: 'y'
                },
                {
                    label: 'Drawdown',
                    data: drawdown,
                    borderColor: 'rgba(239, 68, 68, 1)',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
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
                    labels: { color: '#9CA3AF' }
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`
                    }
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    grid: { color: 'rgba(75, 85, 99, 0.2)' },
                    ticks: {
                        color: '#10B981',
                        callback: (value) => `$${value.toFixed(0)}`
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    grid: { drawOnChartArea: false },
                    ticks: {
                        color: '#EF4444',
                        callback: (value) => `$${value.toFixed(0)}`
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#9CA3AF',
                        maxTicksLimit: 10
                    }
                }
            }
        }
    });
}

// ============================================================================
// TABLA MENSUAL POR EA - CON CELDAS CLICABLES
// ============================================================================
function updatePortfolioEAMonthlyTable(data) {
    const tbody = document.getElementById('portfolioMonthlyTableBody');
    
    if (!tbody) return;
    
    if (!data || data.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="14" class="text-center p-8 text-gray-500">
                    Añade EAs al portafolio para ver el análisis
                </td>
            </tr>
        `;
        return;
    }
    
    const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
    
    tbody.innerHTML = data.map(ea => {
        let total = 0;
        
        let row = `
            <tr class="border-b border-gray-800 hover:bg-gray-800">
                <td class="text-left p-2 text-cyan-400 font-semibold sticky left-0 bg-gray-900">${ea.name}</td>
        `;
        
        months.forEach(month => {
            const profit = ea[month] || 0;
            const trades = ea[`${month}_trades`] || 0;
            total += profit;
            const color = profit >= 0 ? 'text-emerald-400' : 'text-red-400';
            
            // Hacer celda clicable si hay profit
            if (profit !== 0) {
                row += `
                    <td class="text-right p-2 ${color} cursor-pointer hover:bg-gray-700 transition-colors" 
                        onclick="showPortfolioTradesDetail(${ea.magic_number}, '${month}')"
                        title="Click para ver trades">
                        $${profit.toFixed(2)}<br>
                        <span class="text-xs text-gray-400">(${trades})</span>
                    </td>
                `;
            } else {
                row += `<td class="text-right p-2 text-gray-600">-</td>`;
            }
        });
        
        const totalColor = total >= 0 ? 'text-emerald-400' : 'text-red-400';
        row += `<td class="text-right p-2 font-bold ${totalColor}">$${total.toFixed(2)}</td>`;
        row += `</tr>`;
        
        return row;
    }).join('');
}

// ============================================================================
// MOSTRAR TRADES DE UN MES ESPECÍFICO
// ============================================================================
async function showPortfolioTradesDetail(magicNumber, month) {
    const modal = document.getElementById('tradesDetailModal');
    const title = document.getElementById('tradesDetailTitle');
    const tbody = document.getElementById('tradesDetailTableBody');
    
    if (!modal || !title || !tbody) {
        console.error('❌ Modal de trades no encontrado');
        return;
    }
    
    // Obtener año actual (puedes mejorarlo para detectar el año del trade)
    const currentYear = new Date().getFullYear();
    
    title.textContent = `Trades - EA ${magicNumber} - ${month} ${currentYear}`;
    
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
        const response = await fetch(`/api/portfolio/trades-detail/${magicNumber}/${month}?year=${currentYear}`);
        
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
        
        // Actualizar resumen
        document.getElementById('modalTotalTrades').textContent = data.summary.total;
        document.getElementById('modalTotalProfit').textContent = `$${data.summary.profit.toFixed(2)}`;
        document.getElementById('modalWinRate').textContent = `${data.summary.win_rate.toFixed(1)}%`;
        
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
// NOTIFICACIONES
// ============================================================================
function showNotification(message, type = 'info') {
    console.log(`${type.toUpperCase()}: ${message}`);
    // TODO: Implementar notificaciones visuales
    alert(message);
}

// ============================================================================
// MAX DD YEAR
// ============================================================================
async function updatePortfolioMaxDDYear() {
    const yearSelector = document.getElementById('portfolioYearSelector');
    const maxDDElement = document.getElementById('portfolioMaxDDYear');
    const card = document.getElementById('portfolioMaxDDYearCard');
    
    if (!yearSelector || !maxDDElement || portfolioEAs.length === 0) return;
    
    const year = yearSelector.value;
    const magicNumbers = portfolioEAs.map(ea => ea.magic_number).join(',');
    
    console.log(`📊 Actualizando Portfolio Max DD Year: ${year}`);
    
    maxDDElement.textContent = '...';
    
    try {
        const response = await fetch(`/api/portfolio/max-dd-year?magic_numbers=${magicNumbers}&year=${year}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        maxDDElement.textContent = `${data.max_dd.toFixed(2)}%`;
        
        // Aplicar colores
        if (card) {
            card.classList.remove('kpi-green', 'kpi-yellow', 'kpi-red');
            
            if (data.max_dd <= 10) {
                card.classList.add('kpi-green');
            } else if (data.max_dd <= 20) {
                card.classList.add('kpi-yellow');
            } else {
                card.classList.add('kpi-red');
            }
        }
        
        console.log(`✅ Max DD Year: ${data.max_dd.toFixed(2)}%`);
        
    } catch (error) {
        console.error('❌ Error obteniendo Max DD Year:', error);
        maxDDElement.textContent = '-';
    }
}

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
function InitPortfolio() {
    console.log('✅ Portfolio inicializado');
    
    // Cargar EAs desde localStorage
    const saved = localStorage.getItem('portfolioEAs');
    if (saved) {
        portfolioEAs = JSON.parse(saved);
        console.log(`📦 ${portfolioEAs.length} EAs cargados del localStorage`);
    }
    
    renderPortfolioEAsList();
    loadPortfolioData();
}