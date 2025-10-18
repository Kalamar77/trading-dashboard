from flask import Blueprint, request, jsonify
import pandas as pd
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
import os

cuenta_real_bp = Blueprint('cuenta_real', __name__)

UPLOAD_FOLDER_REAL = 'uploads_cuenta_real'
ALLOWED_EXTENSIONS = {'csv'}

if not os.path.exists(UPLOAD_FOLDER_REAL):
    os.makedirs(UPLOAD_FOLDER_REAL)

# ============================================================================
# INICIALIZACIÓN DE BD
# ============================================================================
def init_cuenta_real_db():
    """Inicializa tablas para cuenta real"""
    conn = sqlite3.connect('trading_data.db')
    c = conn.cursor()
    
    # Tabla de cuentas/sources
    c.execute('''CREATE TABLE IF NOT EXISTS cuenta_real_sources
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_name TEXT UNIQUE,
                  filename TEXT,
                  upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
                  total_trades INTEGER,
                  net_profit REAL,
                  first_trade_date TEXT,
                  last_trade_date TEXT)''')
    
    # Tabla de trades
    c.execute('''CREATE TABLE IF NOT EXISTS cuenta_real_trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  account_name TEXT,
                  ticket INTEGER,
                  symbol TEXT,
                  lots REAL,
                  type TEXT,
                  open_price REAL,
                  close_price REAL,
                  open_time TEXT,
                  close_time TEXT,
                  open_date TEXT,
                  close_date TEXT,
                  profit REAL,
                  swap REAL,
                  commission REAL,
                  net_profit REAL,
                  tp REAL,
                  sl REAL,
                  pips REAL,
                  result TEXT,
                  trade_duration TEXT,
                  magic_number INTEGER,
                  order_comment TEXT,
                  account TEXT,
                  FOREIGN KEY (account_name) REFERENCES cuenta_real_sources(account_name))''')
    
    # NUEVA TABLA: Gestión de portfolios
    c.execute('''CREATE TABLE IF NOT EXISTS cuenta_real_portfolio
                 (magic_number INTEGER PRIMARY KEY,
                  riesgo REAL DEFAULT 0,
                  fecha_futura TEXT,
                  comentario TEXT,
                  updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    print("✅ Tablas de Cuenta Real inicializadas")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ============================================================================
# SUBIR CSV
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/upload', methods=['POST'])
def upload_cuenta_real_csv():
    """Sube CSV de cuenta real"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No hay archivo', 'success': False}), 400
        
        file = request.files['file']
        account_name = request.form.get('account_name', 'Cuenta Real')
        
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo', 'success': False}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Solo archivos CSV', 'success': False}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER_REAL, f"{account_name}_{filename}")
        file.save(filepath)
        
        # Leer CSV con separador punto y coma
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        
        # Limpiar nombres de columnas
        df.columns = df.columns.str.strip()
        
        print(f"📊 Columnas encontradas: {df.columns.tolist()}")
        
        # Verificar que existe la columna de fecha
        if 'Close date' not in df.columns:
            return jsonify({'error': 'CSV no tiene columna "Close date"', 'success': False}), 400
        
        # Convertir fechas
        df['Close date'] = pd.to_datetime(df['Close date'], format='%d/%m/%Y', errors='coerce')
        df = df.dropna(subset=['Close date'])
        
        # Convertir numéricos
        numeric_cols = ['Lots', 'Open price', 'Close price', 'Profit', 'Swap', 'Commission', 'Net profit', 'T/P', 'S/L', 'Pips']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        total_trades = len(df)
        net_profit = df['Net profit'].sum()
        first_date = df['Close date'].min().strftime('%Y-%m-%d')
        last_date = df['Close date'].max().strftime('%Y-%m-%d')
        
        # Guardar en BD
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Eliminar datos anteriores de esta cuenta
        c.execute('DELETE FROM cuenta_real_trades WHERE account_name = ?', (account_name,))
        c.execute('DELETE FROM cuenta_real_sources WHERE account_name = ?', (account_name,))
        
        # Insertar cuenta
        c.execute('''INSERT INTO cuenta_real_sources 
                     (account_name, filename, upload_date, total_trades, net_profit, first_trade_date, last_trade_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (account_name, filename, datetime.now().isoformat(), total_trades, net_profit, first_date, last_date))
        
        # Insertar trades
        for _, row in df.iterrows():
            c.execute('''INSERT INTO cuenta_real_trades 
                         (account_name, ticket, symbol, lots, type, open_price, close_price,
                          open_time, close_time, open_date, close_date, profit, swap, commission,
                          net_profit, tp, sl, pips, result, trade_duration, magic_number, order_comment, account)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (account_name,
                      row.get('Ticket', 0),
                      row.get('Symbol', ''),
                      row.get('Lots', 0),
                      row.get('Buy/sell', ''),  # ← Cambiado a 'Buy/sell'
                      row.get('Open price', 0),
                      row.get('Close price', 0),
                      row.get('Open time', ''),
                      row.get('Close time', ''),
                      row.get('Open date', ''),
                      row['Close date'].strftime('%Y-%m-%d'),
                      row.get('Profit', 0),
                      row.get('Swap', 0),
                      row.get('Commission', 0),
                      row.get('Net profit', 0),
                      row.get('T/P', 0),
                      row.get('S/L', 0),
                      row.get('Pips', 0),
                      row.get('Result', ''),
                      row.get('Trade duration (hours)', ''),  # ← Cambiado
                      row.get('Magic number', 0),
                      row.get('Order comment', ''),
                      row.get('Account', '')))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ {total_trades} trades cargados',
            'account_name': account_name,
            'total_trades': total_trades,
            'net_profit': round(net_profit, 2)
        })
        
    except Exception as e:
        print(f"ERROR en upload_cuenta_real_csv: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500
# ============================================================================
# LISTAR CUENTAS
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/sources', methods=['GET'])
def get_cuenta_real_sources():
    """Lista todas las cuentas cargadas"""
    try:
        conn = sqlite3.connect('trading_data.db')
        df = pd.read_sql_query('SELECT * FROM cuenta_real_sources ORDER BY upload_date DESC', conn)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        return jsonify(df.to_dict('records'))
        
    except Exception as e:
        print(f"ERROR en get_cuenta_real_sources: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ESTADÍSTICAS (CON FILTROS)
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/stats', methods=['GET'])
def get_cuenta_real_stats():
    """Calcula estadísticas de cuenta real con filtros"""
    try:
        account = request.args.get('account', 'all')
        year = request.args.get('year', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        query = 'SELECT close_date, net_profit FROM cuenta_real_trades WHERE 1=1'
        params = []
        
        if account != 'all':
            query += ' AND account_name = ?'
            params.append(account)
        
        if year != 'all':
            query += " AND close_date LIKE ?"
            params.append(f'{year}%')
        
        query += ' ORDER BY close_date'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify({
                'net_profit': 0, 'total_trades': 0, 'win_rate': 0,
                'profit_factor': 0, 'expectancy': 0, 'sharpe_ratio': 0,
                'max_drawdown': 0, 'ret_dd': 0, 'sqn': 0, 'r2_equity': 0,
                'cagr': 0, 'rr_ratio': 0, 'avg_recovery_days': 0,
                'consistency_green_months': 0
            })
        
        df['close_date'] = pd.to_datetime(df['close_date'])
        df = df.sort_values('close_date')
        
        # Calcular todos los KPIs (igual que dashboard principal)
        total_trades = len(df)
        net_profit = df['net_profit'].sum()
        
        winning_trades = len(df[df['net_profit'] > 0])
        losing_trades = len(df[df['net_profit'] < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = df[df['net_profit'] > 0]['net_profit'].sum()
        gross_loss = abs(df[df['net_profit'] < 0]['net_profit'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        avg_win = df[df['net_profit'] > 0]['net_profit'].mean() if winning_trades > 0 else 0
        avg_loss = abs(df[df['net_profit'] < 0]['net_profit'].mean()) if losing_trades > 0 else 0
        expectancy = ((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss))
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # Equity y Drawdown
        df['cumulative'] = df['net_profit'].cumsum()
        df['running_max'] = df['cumulative'].cummax()
        df['drawdown'] = df['cumulative'] - df['running_max']
        max_drawdown = df['drawdown'].min()
        max_drawdown_abs = abs(max_drawdown)
        ret_dd = (net_profit / max_drawdown_abs) if max_drawdown_abs > 0 else 0

        # Max DD Porcentual
        capital_inicial = 100000  # Capital real de la cuenta
        max_dd_percent = (max_drawdown_abs / capital_inicial * 100) if capital_inicial > 0 else 0
        
        # SQN
        avg_pnl = df['net_profit'].mean()
        std_pnl = df['net_profit'].std(ddof=1)
        sqn = (avg_pnl / std_pnl * (total_trades ** 0.5)) if std_pnl > 0 else 0
        
        # R²
        if len(df) > 2:
            x = range(len(df))
            y = df['cumulative'].values
            y_mean = y.mean()
            ss_tot = ((y - y_mean) ** 2).sum()
            x_mean = sum(x) / len(x)
            numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
            denominator = sum((xi - x_mean) ** 2 for xi in x)
            
            if denominator > 0:
                slope = numerator / denominator
                intercept = y_mean - slope * x_mean
                y_pred = [slope * xi + intercept for xi in x]
                ss_res = sum((yi - y_pred_i) ** 2 for yi, y_pred_i in zip(y, y_pred))
                r2_equity = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            else:
                r2_equity = 0
        else:
            r2_equity = 0
        
        # CAGR
        first_date = df['close_date'].min()
        last_date = df['close_date'].max()
        days_diff = (last_date - first_date).days

        if days_diff > 0:
            capital_req = max(5000, max_drawdown_abs * 2)
            equity_final = capital_req + net_profit
            if capital_req > 0 and equity_final > 0:
                cagr = float(round(((equity_final / capital_req) ** (365.25 / days_diff) - 1) * 100, 2))
            else:
                cagr = 0.0
        else:
            cagr = 0.0
        
        # Sharpe
        df['date'] = df['close_date'].dt.date
        daily_profit = df.groupby('date')['net_profit'].sum()
        equity_curve = daily_profit.cumsum()
        daily_returns = equity_curve.pct_change().dropna()
        
        if len(daily_returns) > 1:
            mean_return = daily_returns.mean()
            std_return = daily_returns.std(ddof=1)
            sharpe_ratio = (mean_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Recovery
        recovery_times = []
        in_dd = False
        dd_start = None
        
        for idx, row in df.iterrows():
            if row['drawdown'] < 0 and not in_dd:
                in_dd = True
                dd_start = row['close_date']
            elif row['drawdown'] == 0 and in_dd:
                in_dd = False
                if dd_start:
                    recovery_days = (row['close_date'] - dd_start).days
                    if recovery_days >= 0:
                        recovery_times.append(recovery_days)
        
        avg_recovery = sum(recovery_times) / len(recovery_times) if recovery_times else 0
        
        # Consistencia
        df['year_month'] = df['close_date'].dt.strftime('%Y-%m')
        monthly_profit = df.groupby('year_month')['net_profit'].sum()
        green_months = (monthly_profit > 0).sum()
        total_months = len(monthly_profit)
        consistency = (green_months / total_months * 100) if total_months > 0 else 0
        
        return jsonify({
        'net_profit': round(net_profit, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'expectancy': round(expectancy, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'max_drawdown': round(max_drawdown, 2),
        'max_dd_percent': round(max_dd_percent, 2),  # ← AÑADIR ESTA LÍNEA
        'ret_dd': round(ret_dd, 2),
        'sqn': round(sqn, 2),
        'r2_equity': round(r2_equity, 4),
        'cagr': float(round(cagr, 2)),
        'rr_ratio': round(rr_ratio, 2),
        'avg_recovery_days': round(avg_recovery, 1),
        'consistency_green_months': round(consistency, 1)
    })
        
    except Exception as e:
        print(f"ERROR en get_cuenta_real_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# DATOS MENSUALES
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/monthly', methods=['GET'])
def get_cuenta_real_monthly():
    """Datos mensuales para gráfico"""
    try:
        account = request.args.get('account', 'all')
        year = request.args.get('year', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        query = 'SELECT close_date, net_profit FROM cuenta_real_trades WHERE 1=1'
        params = []
        
        if account != 'all':
            query += ' AND account_name = ?'
            params.append(account)
        
        if year != 'all':
            query += " AND close_date LIKE ?"
            params.append(f'{year}%')
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        df['close_date'] = pd.to_datetime(df['close_date'])
        df['month'] = df['close_date'].dt.strftime('%Y-%m')
        
        monthly = df.groupby('month')['net_profit'].sum().reset_index()
        monthly.columns = ['month', 'profit']
        
        return jsonify(monthly.to_dict('records'))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# EQUITY/DRAWDOWN DIARIO
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/equity-dd', methods=['GET'])
def get_cuenta_real_equity_dd():
    """Datos de equity y drawdown diario"""
    try:
        account = request.args.get('account', 'all')
        year = request.args.get('year', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        query = 'SELECT close_date, net_profit FROM cuenta_real_trades WHERE 1=1'
        params = []
        
        if account != 'all':
            query += ' AND account_name = ?'
            params.append(account)
        
        if year != 'all':
            query += " AND close_date LIKE ?"
            params.append(f'{year}%')
        
        query += ' ORDER BY close_date'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify({'labels': [], 'equity': [], 'drawdown': []})
        
        df['close_date'] = pd.to_datetime(df['close_date'])
        df['date'] = df['close_date'].dt.date
        
        daily = df.groupby('date')['net_profit'].sum().reset_index()
        daily['equity'] = daily['net_profit'].cumsum()
        daily['running_max'] = daily['equity'].cummax()
        daily['drawdown'] = daily['equity'] - daily['running_max']
        
        labels = [d.strftime('%Y-%m-%d') for d in daily['date']]
        
        return jsonify({
            'labels': labels,
            'equity': daily['equity'].round(2).tolist(),
            'drawdown': daily['drawdown'].round(2).tolist()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ÚLTIMOS TRADES
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/recent-trades', methods=['GET'])
def get_cuenta_real_recent_trades():
    """Últimos 50 trades"""
    try:
        account = request.args.get('account', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        query = '''SELECT ticket, symbol, type, lots, close_date, net_profit, result
                   FROM cuenta_real_trades WHERE 1=1'''
        params = []
        
        if account != 'all':
            query += ' AND account_name = ?'
            params.append(account)
        
        query += ' ORDER BY close_date DESC LIMIT 50'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        return jsonify(df.to_dict('records'))
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ANÁLISIS MENSUAL POR EA
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/ea-monthly', methods=['GET'])
def get_cuenta_real_ea_monthly():
    """Análisis mensual por EA para cuenta real"""
    try:
        account = request.args.get('account', 'all')
        year = request.args.get('year', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        query = '''SELECT magic_number, close_date, net_profit 
                   FROM cuenta_real_trades WHERE 1=1'''
        params = []
        
        if account != 'all':
            query += ' AND account_name = ?'
            params.append(account)
        
        if year != 'all':
            query += " AND close_date LIKE ?"
            params.append(f'{year}%')
        
        query += ' ORDER BY close_date'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        df['close_date'] = pd.to_datetime(df['close_date'])
        df['month'] = df['close_date'].dt.month
        df['month_name'] = df['close_date'].dt.strftime('%b').str.upper()
        
        # Mapeo de meses en español
        month_map = {
            'JAN': 'ENE', 'FEB': 'FEB', 'MAR': 'MAR', 'APR': 'ABR',
            'MAY': 'MAY', 'JUN': 'JUN', 'JUL': 'JUL', 'AUG': 'AGO',
            'SEP': 'SEP', 'OCT': 'OCT', 'NOV': 'NOV', 'DEC': 'DIC'
        }
        df['month_name'] = df['month_name'].map(month_map)
        
        # Agrupar por EA
        eas = df['magic_number'].unique()
        
        result = []
        
        for ea in eas:
            ea_data = df[df['magic_number'] == ea].copy()
            
            # Calcular RET/DD para el EA
            ea_data['cumulative'] = ea_data['net_profit'].cumsum()
            ea_data['running_max'] = ea_data['cumulative'].cummax()
            ea_data['drawdown'] = ea_data['cumulative'] - ea_data['running_max']
            max_dd = abs(ea_data['drawdown'].min())
            total_profit = ea_data['net_profit'].sum()
            ret_dd = (total_profit / max_dd) if max_dd > 0 else 0
            
            # Calcular max consecutive losses
            consecutive_losses = 0
            max_consecutive_loss = 0
            for profit in ea_data['net_profit']:
                if profit < 0:
                    consecutive_losses += 1
                    max_consecutive_loss = max(max_consecutive_loss, consecutive_losses)
                else:
                    consecutive_losses = 0
            
            ea_row = {
                'magic_number': int(ea),
                'ret_dd': round(ret_dd, 2),
                'max_consecutive_loss': max_consecutive_loss
            }
            
            # Datos por mes
            monthly = ea_data.groupby('month_name').agg({
                'net_profit': ['sum', 'count']
            }).reset_index()
            monthly.columns = ['month', 'profit', 'trades']
            
            for _, month_row in monthly.iterrows():
                month = month_row['month']
                month_data = ea_data[ea_data['month_name'] == month]
                
                winning = len(month_data[month_data['net_profit'] > 0])
                total = len(month_data)
                win_rate = (winning / total * 100) if total > 0 else 0
                
                ea_row[month] = {
                    'profit': round(month_row['profit'], 2),
                    'trades': int(month_row['trades']),
                    'winning': round(win_rate, 1)
                }
            
            result.append(ea_row)
        
        return jsonify(result)
        
    except Exception as e:
        print(f"ERROR en get_cuenta_real_ea_monthly: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500    
    
# ============================================================================
# DETALLE DE TRADES POR EA Y MES
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/trades-detail', methods=['GET'])
def get_cuenta_real_trades_detail():
    """Obtiene trades detallados por EA y mes"""
    try:
        magic_number = request.args.get('magic_number')
        month = request.args.get('month')
        year = request.args.get('year', 'all')
        account = request.args.get('account', 'all')
        
        if not magic_number or not month:
            return jsonify({'error': 'Faltan parámetros'}), 400
        
        # Mapeo de meses
        month_map = {
            'ENE': '01', 'FEB': '02', 'MAR': '03', 'ABR': '04',
            'MAY': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08',
            'SEP': '09', 'OCT': '10', 'NOV': '11', 'DIC': '12'
        }
        
        month_num = month_map.get(month)
        if not month_num:
            return jsonify({'error': 'Mes inválido'}), 400
        
        conn = sqlite3.connect('trading_data.db')
        
        query = '''SELECT ticket, symbol, type, lots, open_price, close_price, 
                          close_date, net_profit, order_comment
                   FROM cuenta_real_trades 
                   WHERE magic_number = ?'''
        params = [int(magic_number)]
        
        if account != 'all':
            query += ' AND account_name = ?'
            params.append(account)
        
        if year != 'all':
            query += " AND close_date LIKE ?"
            params.append(f'{year}-{month_num}%')
        else:
            query += " AND close_date LIKE ?"
            params.append(f'%-{month_num}-%')
        
        query += ' ORDER BY close_date'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        # Convertir a formato esperado por el frontend
        trades = []
        for _, row in df.iterrows():
            trades.append({
                'ticket': int(row['ticket']),
                'symbol': row['symbol'],
                'type': row['type'],
                'lots': float(row['lots']),
                'open_price': float(row['open_price']),
                'close_price': float(row['close_price']),
                'close_time': row['close_date'],
                'profit': float(row['net_profit']),
                'comment': row['order_comment']
            })
        
        return jsonify(trades)
        
    except Exception as e:
        print(f"ERROR en get_cuenta_real_trades_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500    
    
# ============================================================================
# GESTIÓN DE PORTFOLIO
# ============================================================================
@cuenta_real_bp.route('/api/cuenta-real/portfolio-list', methods=['GET'])
def get_cuenta_real_portfolio_list():
    """Lista todos los EAs con su información de portfolio"""
    try:
        account = request.args.get('account', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        # Obtener Magic Numbers únicos con información básica
        query = '''SELECT DISTINCT 
                          t.magic_number,
                          GROUP_CONCAT(DISTINCT t.symbol) as symbols,
                          COUNT(*) as total_trades
                   FROM cuenta_real_trades t
                   WHERE 1=1'''
        params = []
        
        if account != 'all':
            query += ' AND t.account_name = ?'
            params.append(account)
        
        query += ' GROUP BY t.magic_number ORDER BY t.magic_number'
        
        df_eas = pd.read_sql_query(query, conn, params=params)
        
        if df_eas.empty:
            conn.close()
            return jsonify([])
        
        # Obtener información de portfolio
        portfolio_query = '''SELECT magic_number, riesgo, fecha_futura, comentario
                            FROM cuenta_real_portfolio'''
        df_portfolio = pd.read_sql_query(portfolio_query, conn)
        
        conn.close()
        
        # Combinar información
        result = []
        for _, row in df_eas.iterrows():
            magic = int(row['magic_number'])
            
            # Crear nombre descriptivo desde los símbolos
            symbols = row['symbols'].split(',') if pd.notna(row['symbols']) else []
            if len(symbols) == 1:
                ea_name = f"EA {symbols[0]}"
            elif len(symbols) > 1:
                ea_name = f"EA Multi ({len(symbols)} pares)"
            else:
                ea_name = f"EA {magic}"
            
            # Buscar portfolio info
            portfolio_info = df_portfolio[df_portfolio['magic_number'] == magic]
            
            if not portfolio_info.empty:
                result.append({
                    'magic_number': magic,
                    'ea_name': ea_name,
                    'riesgo': float(portfolio_info.iloc[0]['riesgo']) if pd.notna(portfolio_info.iloc[0]['riesgo']) else 0,
                    'fecha_futura': portfolio_info.iloc[0]['fecha_futura'] if pd.notna(portfolio_info.iloc[0]['fecha_futura']) else '',
                    'comentario': portfolio_info.iloc[0]['comentario'] if pd.notna(portfolio_info.iloc[0]['comentario']) else ''
                })
            else:
                result.append({
                    'magic_number': magic,
                    'ea_name': ea_name,
                    'riesgo': 0,
                    'fecha_futura': '',
                    'comentario': ''
                })
        
        return jsonify(result)
        
    except Exception as e:
        print(f"ERROR en get_cuenta_real_portfolio_list: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@cuenta_real_bp.route('/api/cuenta-real/portfolio-update', methods=['POST'])
def update_cuenta_real_portfolio():
    """Actualiza información de portfolio de un EA"""
    try:
        data = request.json
        magic_number = data.get('magic_number')
        riesgo = data.get('riesgo', 0)
        fecha_futura = data.get('fecha_futura', '')
        comentario = data.get('comentario', '')
        
        if not magic_number:
            return jsonify({'error': 'Magic number requerido', 'success': False}), 400
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Insertar o actualizar
        c.execute('''INSERT INTO cuenta_real_portfolio 
                     (magic_number, riesgo, fecha_futura, comentario, updated_at)
                     VALUES (?, ?, ?, ?, ?)
                     ON CONFLICT(magic_number) 
                     DO UPDATE SET 
                        riesgo=excluded.riesgo,
                        fecha_futura=excluded.fecha_futura,
                        comentario=excluded.comentario,
                        updated_at=excluded.updated_at''',
                 (int(magic_number), float(riesgo), fecha_futura, comentario, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Portfolio actualizado para EA {magic_number}'
        })
        
    except Exception as e:
        print(f"ERROR en update_cuenta_real_portfolio: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500    