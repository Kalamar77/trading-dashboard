import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, jsonify, request
import pandas as pd
import sqlite3
from datetime import datetime
import requests
from io import StringIO
import hashlib
import warnings
from cuenta_real import cuenta_real_bp, init_cuenta_real_db

warnings.filterwarnings('ignore', category=DeprecationWarning)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
UPLOAD_FOLDER = 'uploads_ea'

CSV_URLS = {
    'atr2': 'https://www.fxblue.com/users/-demo_darwinex-/csv',
    'atr3': 'https://www.fxblue.com/users/-demo_darwinex2-/csv',
    'axi_nq': 'https://www.fxblue.com/users/axi_nq/csv',
    'axi_dax': 'https://www.fxblue.com/users/axi_dax/csv'
}

# ============================================================================
# INICIALIZACIÓN DE BASE DE DATOS
# ============================================================================

def init_db():
    conn = sqlite3.connect('trading_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  trade_hash TEXT UNIQUE,
                  source TEXT,
                  open_time TEXT,
                  close_time TEXT,
                  symbol TEXT,
                  type TEXT,
                  lots REAL,
                  open_price REAL,
                  close_price REAL,
                  sl REAL,
                  tp REAL,
                  profit REAL,
                  magic_number INTEGER,
                  comment TEXT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS updates_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source TEXT,
                  last_update TEXT,
                  records_added INTEGER,
                  status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ea_configurations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ea_name TEXT,
                  magic_number INTEGER,
                  best_range TEXT,
                  parameters TEXT,
                  comments TEXT,
                  localization TEXT,
                  fecha_futura TEXT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS magic_number_mappings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  from_magic INTEGER UNIQUE,
                  to_magic INTEGER,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def generate_trade_hash(row):
    trade_string = f"{row.get('open_time', '')}{row.get('close_time', '')}{row.get('symbol', '')}{row.get('type', '')}{row.get('lots', '')}{row.get('open_price', '')}{row.get('profit', '')}"
    return hashlib.md5(trade_string.encode()).hexdigest()

def extract_direction_from_comment(comment):
    if not comment or pd.isna(comment):
        return None
    
    comment_upper = str(comment).upper()
    
    if '_BS_' in comment_upper or '_BS' in comment_upper[-4:]:
        return 'BS'
    elif '_B_' in comment_upper or '_B' in comment_upper[-3:]:
        return 'B'
    elif '_S_' in comment_upper or '_S' in comment_upper[-3:]:
        return 'S'
    
    return None

def extract_timeframe_from_comment(comment):
    if not comment or pd.isna(comment):
        return None
    
    comment_upper = str(comment).upper()
    
    # ORDEN IMPORTANTE: Más largo primero para evitar que H1 detecte H12
    timeframe_patterns = [
        ('H12', '12H'), ('12H', '12H'),
        ('H1', '1H'), ('1H', '1H'),
        ('H2', '2H'), ('2H', '2H'),
        ('H4', '4H'), ('4H', '4H'),
        ('H6', '6H'), ('6H', '6H'),
        ('H8', '8H'), ('8H', '8H'),
        ('M30', '30m'), ('30M', '30m'),
        ('M15', '15m'), ('15M', '15m'),
        ('M5', '5m'), ('5M', '5m'),
        ('M1', '1m'), ('1M', '1m'),
        ('D1', '1D'), ('1D', '1D'),
        ('W1', 'W1'),
        ('MN', 'MN'),
    ]
    
    # Buscar con separadores para evitar falsos positivos (H1 dentro de H12)
    for pattern, standard in timeframe_patterns:
        # Buscar el patrón rodeado de separadores (_) o al inicio/final
        if f'_{pattern}_' in comment_upper or \
           comment_upper.startswith(pattern + '_') or \
           comment_upper.endswith('_' + pattern) or \
           comment_upper == pattern:
            return standard
    
    return None

def parse_comment_full(comment):
    if not comment or pd.isna(comment) or comment == '':
        return {
            'currency_pair': None,
            'timeframe': None,
            'strategy': None,
            'range': None,
            'comment_magic': None,
            'direction': None
        }
    
    comment_str = str(comment)
    parts = comment_str.split('_')
    
    result = {
        'currency_pair': None,
        'timeframe': None,
        'strategy': None,
        'range': None,
        'comment_magic': None,
        'direction': None
    }
    
    if len(parts) >= 2:
        result['currency_pair'] = parts[0] if parts[0] else None
        result['timeframe'] = extract_timeframe_from_comment(parts[1])
        
        if len(parts) >= 3:
            strategy_parts = []
            range_found = False
            
            for i in range(2, len(parts)):
                part = parts[i]
                
                if '%' in part and not range_found:
                    result['range'] = part
                    range_found = True
                elif i == len(parts) - 1:
                    import re
                    clean_magic = re.sub(r'[^\d]', '', part)
                    if clean_magic:
                        result['comment_magic'] = clean_magic
                elif not range_found:
                    strategy_parts.append(part)
            
            if strategy_parts:
                result['strategy'] = '_'.join(strategy_parts)
    
    result['direction'] = extract_direction_from_comment(comment_str)
    
    return result

def apply_filters_to_dataframe(df, source=None, year=None, trade_type=None, symbol=None, timeframe=None, magic_number=None):
    if df.empty:
        return df
    
    if source and source != 'all':
        df = df[df['source'] == source]
    
    # FILTRO POR TIPO: Buy, Sell o Buy/Sell según comentario
    if trade_type and trade_type != 'all':
        df['direction'] = df['comment'].apply(extract_direction_from_comment)
        
        if trade_type == 'Buy':
            df = df[(df['type'] == 'Buy') & (df['direction'].isin(['B', None]))]
            
        elif trade_type == 'Sell':
            df = df[(df['type'] == 'Sell') & (df['direction'] == 'S')]
            
        elif trade_type == 'Buy/Sell':
            df = df[df['direction'] == 'BS']
        
        df = df.drop(columns=['direction'])
    
    if symbol and symbol != 'all':
        df = df[df['symbol'] == symbol]
    
    if magic_number and magic_number != 'all':
        df = df[df['magic_number'] == int(magic_number)]
    
    if 'close_time' in df.columns:
        df['close_time'] = pd.to_datetime(df['close_time'], errors='coerce')
        df = df.dropna(subset=['close_time'])
    
    # ✅ USAR LA COLUMNA TIMEFRAME DIRECTAMENTE
    if timeframe and timeframe != 'all' and 'timeframe' in df.columns:
        df = df[df['timeframe'] == timeframe]
    
    if year and year != 'all' and 'close_time' in df.columns:
        df = df[df['close_time'].dt.year == int(year)]
    
    return df

def fetch_and_store_csv(source_name, url):
    try:
        print(f"Descargando {source_name} desde {url}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        df = pd.read_csv(StringIO(response.text), skiprows=1, on_bad_lines='skip')
        
        if df.empty:
            print(f"  ⚠️ {source_name}: CSV vacío")
            return {'success': False, 'error': 'CSV vacío', 'records_added': 0}
        
        print(f"  ✓ {source_name}: {len(df)} registros encontrados")
        
        column_mapping = {
            'Open time': 'open_time', 'Close time': 'close_time', 'Symbol': 'symbol',
            'Buy/sell': 'type', 'Lots': 'lots', 'Open price': 'open_price',
            'Close price': 'close_price', 'S/L': 'sl', 'T/P': 'tp',
            'Net profit': 'profit', 'Magic number': 'magic_number', 'Order comment': 'comment'
        }
        
        df = df.rename(columns=column_mapping)
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('SELECT from_magic, to_magic FROM magic_number_mappings')
        mappings = {row[0]: row[1] for row in c.fetchall()}
        
        if mappings:
            print(f"  📋 Mapeos activos: {len(mappings)} conversiones configuradas")
        
        records_added = 0
        mapped_count = 0
        
        for idx, row in df.iterrows():
            try:
                trade_hash = generate_trade_hash(row)
                c.execute('SELECT id FROM trades WHERE trade_hash = ?', (trade_hash,))
                if c.fetchone() is None:
                    original_magic = int(row.get('magic_number', 0) or 0)
                    mapped_magic = mappings.get(original_magic, original_magic)
                    
                    if original_magic != mapped_magic:
                        mapped_count += 1
                        if mapped_count <= 5:
                            print(f"  🔄 Mapeando: {original_magic} → {mapped_magic}")
                    
                    # EXTRAER TIMEFRAME DEL COMENTARIO
                    comment = str(row.get('comment', ''))
                    timeframe = extract_timeframe_from_comment(comment)
                    
                    # Si no se detectó, usar valor por defecto
                    if not timeframe:
                        timeframe = 'Unknown'
                    
                    c.execute('''INSERT INTO trades 
                                (trade_hash, source, open_time, close_time, symbol, type, 
                                lots, open_price, close_price, sl, tp, profit, magic_number, comment, timeframe)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (trade_hash, source_name, 
                            str(row.get('open_time', '')), str(row.get('close_time', '')),
                            str(row.get('symbol', '')), str(row.get('type', '')),
                            float(row.get('lots', 0) or 0), float(row.get('open_price', 0) or 0), 
                            float(row.get('close_price', 0) or 0), float(row.get('sl', 0) or 0), 
                            float(row.get('tp', 0) or 0), float(row.get('profit', 0) or 0),
                            mapped_magic,
                            comment,
                            timeframe))  # ← AÑADIDO TIMEFRAME
                    records_added += 1
            except Exception:
                continue
        
        if mapped_count > 5:
            print(f"  🔄 ...y {mapped_count - 5} conversiones más")
        
        timestamp = datetime.now().isoformat()
        c.execute('''INSERT INTO updates_log (source, last_update, records_added, status)
                    VALUES (?, ?, ?, ?)''', (source_name, timestamp, records_added, 'success'))
        conn.commit()
        conn.close()
        
        print(f"  ✓ {source_name}: {records_added} registros nuevos añadidos ({mapped_count} mapeados automáticamente)")
        return {'success': True, 'records_added': records_added, 'mapped': mapped_count}
    except Exception as e:
        print(f"  ✗ Error en {source_name}: {str(e)}")
        return {'success': False, 'error': str(e)}

# ============================================================================
# CÁLCULO DE ESTADÍSTICAS
# ============================================================================

def calculate_statistics(source=None, year=None, trade_type=None, symbol=None, timeframe=None, magic_number=None):
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT * FROM trades', conn)
    conn.close()
    
    df = apply_filters_to_dataframe(df, source, year, trade_type, symbol, timeframe, magic_number)
    
    if df.empty:
        return {'net_profit': 0, 'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'win_rate': 0, 'profit_factor': 0, 'expectancy': 0, 'sharpe_ratio': 0,
                'max_drawdown': 0, 'gross_profit': 0, 'gross_loss': 0, 'ret_dd': 0,
                'sqn': 0, 'r2_equity': 0, 'cagr': 0, 'avg_recovery_days': 0, 
                'consistency_green_months': 0, 'rr_ratio': 0}
    
    # Cálculos básicos
    total_trades = len(df)
    winning_trades = len(df[df['profit'] > 0])
    losing_trades = len(df[df['profit'] < 0])
    gross_profit = df[df['profit'] > 0]['profit'].sum()
    gross_loss = abs(df[df['profit'] < 0]['profit'].sum())
    net_profit = df['profit'].sum()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    avg_win = df[df['profit'] > 0]['profit'].mean() if winning_trades > 0 else 0
    avg_loss = abs(df[df['profit'] < 0]['profit'].mean()) if losing_trades > 0 else 0
    expectancy = ((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)) if total_trades > 0 else 0
    rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
    
    # Equity y Drawdown
    df_sorted = df.sort_values('close_time').copy()
    df_sorted['cumulative'] = df_sorted['profit'].cumsum()
    df_sorted['running_max'] = df_sorted['cumulative'].cummax()
    df_sorted['drawdown'] = df_sorted['cumulative'] - df_sorted['running_max']
    max_drawdown = df_sorted['drawdown'].min()
    max_drawdown_abs = abs(max_drawdown)
    
    ret_dd = (net_profit / max_drawdown_abs) if max_drawdown_abs > 0 else 0
    
    # ================================================================
    # SQN - CORREGIDO (R-expectancy como SQX)
    # ================================================================
    avg_loss_for_risk = avg_loss if avg_loss > 0 else 1
    r_expectancy = expectancy / avg_loss_for_risk
    df['R_multiples'] = df['profit'] / avg_loss_for_risk
    std_r = df['R_multiples'].std(ddof=1) if len(df) > 1 else 1
    sqn = (r_expectancy * (total_trades ** 0.5)) / std_r if std_r > 0 else 0
    
    # R² Equity
    if len(df_sorted) > 2:
        x = range(len(df_sorted))
        y = df_sorted['cumulative'].values
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
    
    # ================================================================
    # SHARPE - CORREGIDO (Sin anualizar)
    # ================================================================
    df_sorted_clean = df_sorted.dropna(subset=['close_time'])
    sharpe_ratio = 0
    
    if len(df_sorted_clean) > 1:
        df_sorted_clean['date'] = df_sorted_clean['close_time'].dt.date
        daily_returns = df_sorted_clean.groupby('date')['profit'].sum()
        
        if len(daily_returns) > 1:
            mean_daily = daily_returns.mean()
            std_daily = daily_returns.std(ddof=1)
            sharpe_ratio = (mean_daily / std_daily) if std_daily > 0 else 0
    
    # ================================================================
    # CAGR - Mantener aproximado (no tenemos balance inicial en BD)
    # ================================================================
    cagr = 0
    if len(df_sorted_clean) > 0:
        first_date = df_sorted_clean['close_time'].min()
        last_date = df_sorted_clean['close_time'].max()
        days_diff = (last_date - first_date).days
        years = days_diff / 365.25
        
        capital_required = 100000  # Capital real de la cuenta
        final_capital = capital_required + net_profit
        
        if years >= 1:
            if capital_required > 0 and final_capital > 0:
                cagr = ((final_capital / capital_required) ** (1 / years) - 1) * 100
            else:
                cagr = 0
        elif years > 0:
            if capital_required > 0:
                cagr = (net_profit / capital_required / years) * 100
            else:
                cagr = 0
    
    # Recovery Days
    recovery_times = []
    in_drawdown = False
    drawdown_start = None
    
    for idx, row in df_sorted.iterrows():
        if row['drawdown'] < 0 and not in_drawdown:
            in_drawdown = True
            drawdown_start = row['close_time']
        elif row['drawdown'] == 0 and in_drawdown:
            in_drawdown = False
            if drawdown_start and pd.notna(row['close_time']) and pd.notna(drawdown_start):
                recovery_days = (row['close_time'] - drawdown_start).days
                if recovery_days >= 0:
                    recovery_times.append(recovery_days)
    
    avg_recovery_days = sum(recovery_times) / len(recovery_times) if recovery_times else 0
    
    # Consistencia
    consistency_green_months = 0
    if len(df_sorted_clean) > 0:
        df_sorted_clean['year_month'] = df_sorted_clean['close_time'].dt.strftime('%Y-%m')
        monthly_profit = df_sorted_clean.groupby('year_month')['profit'].sum()
        green_months = (monthly_profit > 0).sum()
        total_months = len(monthly_profit)
        consistency_green_months = (green_months / total_months * 100) if total_months > 0 else 0
    
    return {
        'net_profit': round(net_profit, 2),
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'expectancy': round(expectancy, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'max_drawdown': round(max_drawdown, 2),
        'gross_profit': round(gross_profit, 2),
        'gross_loss': round(gross_loss, 2),
        'ret_dd': round(ret_dd, 2),
        'sqn': round(sqn, 2),
        'r2_equity': round(r2_equity, 4),
        'cagr': round(cagr, 2),
        'avg_recovery_days': round(avg_recovery_days, 1),
        'consistency_green_months': round(consistency_green_months, 1),
        'rr_ratio': round(rr_ratio, 2)
    }

def get_ea_monthly_performance(source=None, year=None, trade_type=None, symbol=None, timeframe=None, magic_number=None):
    conn = sqlite3.connect('trading_data.db')
    # ✅ AÑADIR timeframe A LA QUERY
    df = pd.read_sql_query('''SELECT magic_number, close_time, profit, source, symbol, type, comment, timeframe 
                              FROM trades 
                              WHERE magic_number IS NOT NULL AND magic_number > 0 
                              AND close_time IS NOT NULL
                              ORDER BY close_time''', conn)
    conn.close()
    
    # Aplicar filtros (ahora SÍ puede filtrar por timeframe)
    df = apply_filters_to_dataframe(df, source, year, trade_type, symbol, timeframe, magic_number)
    
    if df.empty:
        return []
    
    month_map = {
        1: 'ENE', 2: 'FEB', 3: 'MAR', 4: 'ABR', 5: 'MAY', 6: 'JUN',
        7: 'JUL', 8: 'AGO', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DIC'
    }
    
    df['month_num'] = df['close_time'].dt.month
    df['month_abbr'] = df['month_num'].map(month_map)
    
    result = []
    for magic in df['magic_number'].unique():
        magic_df = df[df['magic_number'] == magic].copy()
        ea_row = {'magic_number': int(magic)}
        
        magic_df_sorted = magic_df.sort_values('close_time')
        magic_df_sorted['cumulative'] = magic_df_sorted['profit'].cumsum()
        magic_df_sorted['running_max'] = magic_df_sorted['cumulative'].cummax()
        magic_df_sorted['drawdown'] = magic_df_sorted['cumulative'] - magic_df_sorted['running_max']
        max_dd = abs(magic_df_sorted['drawdown'].min())
        total_profit = magic_df_sorted['profit'].sum()
        ret_dd = (total_profit / max_dd) if max_dd > 0 else 0
        ea_row['ret_dd'] = ret_dd
        
        consecutive_losses = 0
        max_consecutive_loss = 0
        for profit in magic_df_sorted['profit']:
            if profit < 0:
                consecutive_losses += 1
                max_consecutive_loss = max(max_consecutive_loss, consecutive_losses)
            else:
                consecutive_losses = 0
        ea_row['max_consecutive_loss'] = max_consecutive_loss
        
        monthly = magic_df.groupby('month_abbr').agg({
            'profit': 'sum',
            'close_time': 'count'
        }).reset_index()
        monthly.columns = ['month_abbr', 'profit', 'trades']
        
        for _, row in monthly.iterrows():
            month = row['month_abbr']
            month_data = magic_df[magic_df['month_abbr'] == month]
            
            total_trades = len(month_data)
            winning_trades = len(month_data[month_data['profit'] > 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            ea_row[month] = {
                'profit': round(row['profit'], 2),
                'trades': int(row['trades']),
                'winning': round(win_rate, 1)
            }
        
        result.append(ea_row)
    
    return result

def get_drawdown_equity_daily(source=None, year=None, trade_type=None, symbol=None, timeframe=None, magic_number=None):
    conn = sqlite3.connect('trading_data.db')
    # ✅ AÑADIR timeframe AL SELECT
    df = pd.read_sql_query('SELECT close_time, profit, source, symbol, type, comment, magic_number, timeframe FROM trades', conn)
    conn.close()
    
    df = apply_filters_to_dataframe(df, source, year, trade_type, symbol, timeframe, magic_number)
    
    if df.empty:
        return []
    
    df = df.sort_values('close_time')
    df['date'] = df['close_time'].dt.date
    
    daily_data = df.groupby('date').agg({
        'profit': 'sum'
    }).reset_index()
    
    daily_data['equity'] = daily_data['profit'].cumsum()
    daily_data['running_max'] = daily_data['equity'].cummax()
    daily_data['drawdown'] = daily_data['equity'] - daily_data['running_max']
    
    daily_data['date'] = daily_data['date'].astype(str)
    
    return daily_data.to_dict('records')


def get_drawdown_data(source=None, year=None, trade_type=None, symbol=None, timeframe=None, magic_number=None):
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT close_time, profit, source, symbol, type, comment, magic_number FROM trades', conn)
    conn.close()
    
    df = apply_filters_to_dataframe(df, source, year, trade_type, symbol, timeframe, magic_number)
    
    if df.empty:
        return []
    
    df = df.sort_values('close_time')
    df['cumulative'] = df['profit'].cumsum()
    df['running_max'] = df['cumulative'].cummax()
    df['drawdown'] = df['cumulative'] - df['running_max']
    df['month'] = df['close_time'].dt.strftime('%Y-%m')
    
    monthly_dd = df.groupby('month').agg({
        'drawdown': 'min',
        'cumulative': 'last'
    }).reset_index()
    
    monthly_dd.columns = ['month', 'max_dd', 'equity']
    return monthly_dd.to_dict('records')


# ============================================================================
# RUTAS - DASHBOARD PRINCIPAL
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    """Calcula estadísticas globales con filtros"""
    try:
        source = request.args.get('source', 'all')
        year = request.args.get('year', 'all')
        trade_type = request.args.get('type', 'all')
        symbol = request.args.get('symbol', 'all')
        timeframe = request.args.get('timeframe', 'all')
        magic_number = request.args.get('magic_number', 'all')
        
        conn = sqlite3.connect('trading_data.db')
        
        # Contar EAs únicos
        count_query = 'SELECT COUNT(DISTINCT magic_number) as total_eas FROM trades WHERE magic_number IS NOT NULL AND magic_number != 0'
        total_eas = pd.read_sql_query(count_query, conn).iloc[0]['total_eas']
        
        query = 'SELECT close_time, profit FROM trades WHERE 1=1'
        params = []
        
        if source != 'all':
            query += ' AND source = ?'
            params.append(source)
        
        if year != 'all':
            query += " AND close_time LIKE ?"
            params.append(f'{year}%')
        
        if trade_type != 'all':
            query += ' AND type = ?'
            params.append(trade_type)
        
        if symbol != 'all':
            query += ' AND symbol = ?'
            params.append(symbol)
        
        if timeframe != 'all':
            query += ' AND timeframe = ?'
            params.append(timeframe)
        
        if magic_number != 'all':
            query += ' AND magic_number = ?'
            params.append(int(magic_number))
        
        query += ' ORDER BY close_time'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify({
                'net_profit': 0, 'total_trades': 0, 'total_eas': int(total_eas), 'win_rate': 0,
                'profit_factor': 0, 'expectancy': 0, 'sharpe_ratio': 0,
                'max_drawdown': 0, 'ret_dd': 0, 'sqn': 0, 'r2_equity': 0,
                'cagr': 0, 'rr_ratio': 0, 'avg_recovery_days': 0,
                'consistency_green_months': 0
            })
        
        # Convertir fecha
        df['close_time'] = pd.to_datetime(df['close_time'])
        df = df.sort_values('close_time')
        
        # ================================================================
        # CÁLCULOS BÁSICOS
        # ================================================================
        total_trades = len(df)
        net_profit = df['profit'].sum()
        
        winning_trades = len(df[df['profit'] > 0])
        losing_trades = len(df[df['profit'] < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = df[df['profit'] > 0]['profit'].sum()
        gross_loss = abs(df[df['profit'] < 0]['profit'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        avg_win = df[df['profit'] > 0]['profit'].mean() if winning_trades > 0 else 0
        avg_loss = abs(df[df['profit'] < 0]['profit'].mean()) if losing_trades > 0 else 0
        
        expectancy = ((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss))
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # ================================================================
        # EQUITY CURVE Y DRAWDOWN
        # ================================================================
        df['cumulative'] = df['profit'].cumsum()
        df['running_max'] = df['cumulative'].cummax()
        df['drawdown'] = df['cumulative'] - df['running_max']
        
        max_drawdown = df['drawdown'].min()
        max_drawdown_abs = abs(max_drawdown)
        
        ret_dd = (net_profit / max_drawdown_abs) if max_drawdown_abs > 0 else 0
        
        # ================================================================
        # MAX DD % - CORREGIDO (usando balance de $100,000)
        # ================================================================
        initial_balance = 100000  # FXBlue usa $100k inicial
        
        max_dd_idx = df['drawdown'].idxmin()
        peak_profit = df.loc[max_dd_idx, 'running_max']
        trough_profit = df.loc[max_dd_idx, 'cumulative']
        
        peak_total = initial_balance + peak_profit
        trough_total = initial_balance + trough_profit
        
        max_dd_percent = ((peak_total - trough_total) / peak_total * 100) if peak_total > 0 else 0
        
        # ================================================================
        # SQN - CORREGIDO (R-expectancy como SQX)
        # ================================================================
        avg_loss_for_risk = avg_loss if avg_loss > 0 else 1
        r_expectancy = expectancy / avg_loss_for_risk
        df['R_multiples'] = df['profit'] / avg_loss_for_risk
        std_r = df['R_multiples'].std(ddof=1) if len(df) > 1 else 1
        sqn = (r_expectancy * (total_trades ** 0.5)) / std_r if std_r > 0 else 0
        
        # ================================================================
        # R² EQUITY CURVE
        # ================================================================
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
        
        # ================================================================
        # CAGR - CORREGIDO (FXBlue usa $100,000 inicial)
        # ================================================================
        first_date = df['close_time'].min()
        last_date = df['close_time'].max()
        days_diff = (last_date - first_date).days
        
        if days_diff > 0:
            final_balance = initial_balance + net_profit
            years = days_diff / 365.25
            
            if years > 0 and final_balance > 0:
                cagr = ((final_balance / initial_balance) ** (1 / years) - 1) * 100
            else:
                cagr = 0
        else:
            cagr = 0
        
        # ================================================================
        # SHARPE RATIO - CORREGIDO (Sin anualizar)
        # ================================================================
        df['date'] = df['close_time'].dt.date
        daily_profit = df.groupby('date')['profit'].sum()
        
        if len(daily_profit) > 1:
            mean_daily = daily_profit.mean()
            std_daily = daily_profit.std(ddof=1)
            
            if std_daily > 0:
                sharpe_ratio = mean_daily / std_daily
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # ================================================================
        # AVG RECOVERY DAYS
        # ================================================================
        recovery_times = []
        in_drawdown = False
        drawdown_start = None
        
        for idx, row in df.iterrows():
            if row['drawdown'] < 0 and not in_drawdown:
                in_drawdown = True
                drawdown_start = row['close_time']
            elif row['drawdown'] == 0 and in_drawdown:
                in_drawdown = False
                if drawdown_start and pd.notna(row['close_time']):
                    recovery_days = (row['close_time'] - drawdown_start).days
                    if recovery_days >= 0:
                        recovery_times.append(recovery_days)
        
        avg_recovery_days = sum(recovery_times) / len(recovery_times) if recovery_times else 0
        
        # ================================================================
        # CONSISTENCIA % MESES VERDES
        # ================================================================
        df['year_month'] = df['close_time'].dt.strftime('%Y-%m')
        monthly_profit = df.groupby('year_month')['profit'].sum()
        green_months = (monthly_profit > 0).sum()
        total_months = len(monthly_profit)
        consistency_green_months = (green_months / total_months * 100) if total_months > 0 else 0
        
        return jsonify({
            'net_profit': round(net_profit, 2),
            'total_trades': total_trades,
            'total_eas': int(total_eas),
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_dd_percent': round(max_dd_percent, 2),
            'ret_dd': round(ret_dd, 2),
            'sqn': round(sqn, 2),
            'r2_equity': round(r2_equity, 4),
            'cagr': round(cagr, 2),
            'rr_ratio': round(rr_ratio, 2),
            'avg_recovery_days': round(avg_recovery_days, 1),
            'consistency_green_months': round(consistency_green_months, 1)
        })
        
    except Exception as e:
        print(f"Error en get_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/sources')
def get_sources():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT source FROM trades WHERE source IS NOT NULL ORDER BY source', conn)
    conn.close()
    
    sources_in_db = set(df['source'].tolist())
    all_sources = set(CSV_URLS.keys())
    final_sources = sorted(list(sources_in_db.union(all_sources)))
    
    return jsonify(final_sources)

@app.route('/api/symbols')
def get_symbols():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT symbol FROM trades WHERE symbol IS NOT NULL AND symbol != "" ORDER BY symbol', conn)
    conn.close()
    return jsonify(df['symbol'].tolist())

@app.route('/api/timeframes')
def get_timeframes():
    """Devuelve timeframes únicos desde la columna timeframe de la BD"""
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Leer directamente desde la columna timeframe
        c.execute('''SELECT DISTINCT timeframe 
                     FROM trades 
                     WHERE timeframe IS NOT NULL 
                     AND timeframe != 'Unknown'
                     ORDER BY timeframe''')
        
        timeframes = [row[0] for row in c.fetchall()]
        conn.close()
        
        print(f"📊 Timeframes disponibles: {timeframes}")
        
        return jsonify(timeframes)
        
    except Exception as e:
        print(f"❌ Error obteniendo timeframes: {str(e)}")
        return jsonify([])

@app.route('/api/monthly-filtered')
def get_monthly_filtered():
    source = request.args.get('source', 'all')
    year = request.args.get('year', 'all')
    trade_type = request.args.get('type', 'all')
    symbol = request.args.get('symbol', 'all')
    timeframe = request.args.get('timeframe', 'all')
    magic_number = request.args.get('magic_number', 'all')
    
    conn = sqlite3.connect('trading_data.db')
    # ✅ AÑADIR timeframe AL SELECT
    df = pd.read_sql_query('SELECT close_time, profit, comment, source, symbol, type, magic_number, timeframe FROM trades', conn)
    conn.close()
    
    df = apply_filters_to_dataframe(df, source, year, trade_type, symbol, timeframe, magic_number)
    
    if df.empty:
        return jsonify([])
    
    if year != 'all':
        target_year = int(year)
    else:
        target_year = None
    
    df['month'] = df['close_time'].dt.strftime('%Y-%m')
    monthly = df.groupby('month')['profit'].sum().reset_index()
    monthly.columns = ['month', 'profit']
    
    if target_year:
        all_months = pd.date_range(start=f'{target_year}-01-01', end=f'{target_year}-12-31', freq='MS')
    else:
        min_date = df['close_time'].min()
        max_date = df['close_time'].max()
        all_months = pd.date_range(start=min_date.replace(day=1), end=max_date.replace(day=1), freq='MS')
    
    all_months_df = pd.DataFrame({
        'month': all_months.strftime('%Y-%m')
    })
    
    result = all_months_df.merge(monthly, on='month', how='left')
    result['profit'] = result['profit'].fillna(0)
    
    return jsonify(result.to_dict('records'))

@app.route('/api/drawdown-equity-daily')
def get_dd_equity_daily():
    source = request.args.get('source', 'all')
    year = request.args.get('year', 'all')
    trade_type = request.args.get('type', 'all')
    symbol = request.args.get('symbol', 'all')
    timeframe = request.args.get('timeframe', 'all')
    magic_number = request.args.get('magic_number', 'all')
    
    return jsonify(get_drawdown_equity_daily(source, year, trade_type, symbol, timeframe, magic_number))

@app.route('/api/ea-monthly-performance')
def get_ea_monthly():
    """Análisis mensual por EA con filtros - ENRIQUECIDO CON NOMBRES"""
    try:
        source = request.args.get('source', None if request.args.get('source') == 'all' else request.args.get('source'))
        year = request.args.get('year', None if request.args.get('year') == 'all' else request.args.get('year'))
        trade_type = request.args.get('type', None if request.args.get('type') == 'all' else request.args.get('type'))
        symbol = request.args.get('symbol', None if request.args.get('symbol') == 'all' else request.args.get('symbol'))
        timeframe = request.args.get('timeframe', None if request.args.get('timeframe') == 'all' else request.args.get('timeframe'))
        magic_number = request.args.get('magic_number', None if request.args.get('magic_number') == 'all' else request.args.get('magic_number'))
        
        result = get_ea_monthly_performance(source, year, trade_type, symbol, timeframe, magic_number)
        
        # Enriquecer con nombres de EAs
        if result:
            magic_numbers = [ea['magic_number'] for ea in result]
            conn = sqlite3.connect('trading_data.db')
            placeholders = ','.join('?' * len(magic_numbers))
            ea_names = pd.read_sql_query(
                f'SELECT magic_number, caracteristicas FROM ea_characteristics WHERE magic_number IN ({placeholders})',
                conn, params=magic_numbers
            )
            conn.close()
            
            name_map = dict(zip(ea_names['magic_number'], ea_names['caracteristicas']))
            
            for ea in result:
                ea['name'] = name_map.get(ea['magic_number'], f"EA {ea['magic_number']}")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error en get_ea_monthly: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-data')
def update_data():
    print("\n" + "="*60)
    print("INICIANDO ACTUALIZACIÓN DE DATOS")
    print("="*60)
    
    results = {}
    for source, url in CSV_URLS.items():
        results[source] = fetch_and_store_csv(source, url)
    
    # ================================================================
    # ACTUALIZAR TIMEFRAMES DE REGISTROS EXISTENTES
    # ================================================================
    print("\n🔄 Actualizando timeframes de registros con 'Unknown'...")
    
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener trades sin timeframe detectado
        c.execute("SELECT id, comment FROM trades WHERE timeframe IS NULL OR timeframe = 'Unknown'")
        trades_to_update = c.fetchall()
        
        if trades_to_update:
            print(f"  📋 Procesando {len(trades_to_update)} registros...")
            
            updated_count = 0
            for trade_id, comment in trades_to_update:
                timeframe = extract_timeframe_from_comment(comment)
                if timeframe and timeframe != 'Unknown':
                    c.execute('UPDATE trades SET timeframe = ? WHERE id = ?', (timeframe, trade_id))
                    updated_count += 1
                    
                    # Mostrar algunos ejemplos
                    if updated_count <= 5:
                        print(f"    ✅ ID {trade_id}: {comment[:40]}... → {timeframe}")
            
            if updated_count > 5:
                print(f"    ... y {updated_count - 5} actualizaciones más")
            
            conn.commit()
            print(f"  ✅ Total timeframes actualizados: {updated_count}")
        else:
            print(f"  ✓ Todos los timeframes están actualizados")
        
        conn.close()
        
    except Exception as e:
        print(f"  ⚠️ Error actualizando timeframes: {e}")
    
    print("="*60)
    print("ACTUALIZACIÓN COMPLETADA")
    print("="*60 + "\n")
    
    return jsonify({
        'status': 'completed', 
        'results': results, 
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/last-update')
def last_update():
    conn = sqlite3.connect('trading_data.db')
    c = conn.cursor()
    c.execute('SELECT source, last_update, records_added FROM updates_log ORDER BY last_update DESC LIMIT 10')
    updates = c.fetchall()
    conn.close()
    return jsonify([{'source': u[0], 'last_update': u[1], 'records_added': u[2]} for u in updates])

# ============================================================================
# RUTAS - CARACTERÍSTICAS EAs (PENDIENTE DE REDISEÑO)
# ============================================================================

# Rutas pendientes de rediseñar

@app.route('/api/directions')
def get_directions():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT comment FROM trades WHERE comment IS NOT NULL', conn)
    conn.close()
    
    directions = set()
    for comment in df['comment'].values:
        direction = extract_direction_from_comment(comment)
        if direction:
            directions.add(direction)
    
    result = []
    if 'B' in directions:
        result.append('B')
    if 'S' in directions:
        result.append('S')
    if 'BS' in directions:
        result.append('BS')
    
    return jsonify(result)

@app.route('/api/debug-comments')
def debug_comments():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT comment FROM trades WHERE comment IS NOT NULL LIMIT 100', conn)
    conn.close()
    
    result = []
    for comment in df['comment'].values:
        parsed = parse_comment_full(comment)
        result.append({
            'comment': comment,
            **parsed
        })
    
    return jsonify(result)

@app.route('/api/currency-pairs')
def get_currency_pairs():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT comment FROM trades WHERE comment IS NOT NULL', conn)
    conn.close()
    
    pairs = set()
    for comment in df['comment'].values:
        parsed = parse_comment_full(comment)
        if parsed['currency_pair']:
            pairs.add(parsed['currency_pair'])
    
    return jsonify(sorted(list(pairs)))

@app.route('/api/strategies')
def get_strategies():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT comment FROM trades WHERE comment IS NOT NULL', conn)
    conn.close()
    
    strategies = set()
    for comment in df['comment'].values:
        parsed = parse_comment_full(comment)
        if parsed['strategy']:
            strategies.add(parsed['strategy'])
    
    return jsonify(sorted(list(strategies)))

@app.route('/api/ranges')
def get_ranges():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('SELECT DISTINCT comment FROM trades WHERE comment IS NOT NULL', conn)
    conn.close()
    
    ranges = set()
    for comment in df['comment'].values:
        parsed = parse_comment_full(comment)
        if parsed['range']:
            ranges.add(parsed['range'])
    
    return jsonify(sorted(list(ranges)))

@app.route('/api/magic-numbers')
def get_magic_numbers():
    conn = sqlite3.connect('trading_data.db')
    df = pd.read_sql_query('''SELECT DISTINCT magic_number 
                              FROM trades 
                              WHERE magic_number IS NOT NULL AND magic_number > 0 
                              ORDER BY magic_number''', conn)
    conn.close()
    return jsonify(df['magic_number'].tolist())

@app.route('/api/verify-eas')
def verify_eas():
    conn = sqlite3.connect('trading_data.db')
    
    query = '''SELECT magic_number, close_time, profit, comment, source, symbol, type 
               FROM trades 
               WHERE magic_number IS NOT NULL AND magic_number > 0
               ORDER BY magic_number, close_time'''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return jsonify({'error': 'No hay datos con magic numbers', 'eas': []})
    
    df['close_time'] = pd.to_datetime(df['close_time'], errors='coerce')
    df = df.dropna(subset=['close_time'])
    
    verification = []
    
    for magic in sorted(df['magic_number'].unique()):
        ea_data = df[df['magic_number'] == magic]
        
        total_trades = len(ea_data)
        first_trade = ea_data['close_time'].min().strftime('%Y-%m-%d') if pd.notna(ea_data['close_time'].min()) else 'N/A'
        last_trade = ea_data['close_time'].max().strftime('%Y-%m-%d') if pd.notna(ea_data['close_time'].max()) else 'N/A'
        
        total_profit = ea_data['profit'].sum()
        winning_trades = len(ea_data[ea_data['profit'] > 0])
        losing_trades = len(ea_data[ea_data['profit'] < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        symbols = ea_data['symbol'].unique().tolist()
        sources = ea_data['source'].unique().tolist()
        comments_sample = ea_data['comment'].dropna().unique()[:3].tolist()
        
        if len(ea_data['comment'].dropna()) > 0:
            first_comment = ea_data['comment'].dropna().iloc[0]
            parsed = parse_comment_full(first_comment)
            currency = parsed['currency_pair']
            timeframe = parsed['timeframe']
            strategy = parsed['strategy']
            direction = parsed['direction']
        else:
            currency = None
            timeframe = None
            strategy = None
            direction = None
        
        verification.append({
            'magic_number': int(magic),
            'total_trades': int(total_trades),
            'first_trade': first_trade,
            'last_trade': last_trade,
            'total_profit': round(total_profit, 2),
            'winning_trades': int(winning_trades),
            'losing_trades': int(losing_trades),
            'win_rate': round(win_rate, 1),
            'symbols': symbols,
            'sources': sources,
            'currency_pair': currency,
            'timeframe': timeframe,
            'strategy': strategy,
            'direction': direction,
            'comments_sample': comments_sample
        })
    
    return jsonify({
        'total_eas': len(verification),
        'total_trades_all': int(len(df)),
        'eas': verification
    })

@app.route('/api/unify-magic-numbers', methods=['POST'])
def unify_magic_numbers():
    try:
        data = request.json
        mappings = data.get('mappings', [])
        
        if not mappings:
            return jsonify({'error': 'No se proporcionaron mappings', 'success': False}), 400
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        results = []
        total_updated = 0
        
        for mapping in mappings:
            from_magic = mapping.get('from')
            to_magic = mapping.get('to')
            
            if not from_magic or not to_magic:
                continue
            
            c.execute('SELECT COUNT(*) FROM trades WHERE magic_number = ?', (from_magic,))
            count = c.fetchone()[0]
            
            if count > 0:
                c.execute('UPDATE trades SET magic_number = ? WHERE magic_number = ?', (to_magic, from_magic))
                
                c.execute('''INSERT OR REPLACE INTO magic_number_mappings (from_magic, to_magic)
                            VALUES (?, ?)''', (from_magic, to_magic))
                
                results.append({
                    'from': from_magic,
                    'to': to_magic,
                    'trades_updated': count,
                    'success': True
                })
                total_updated += count
            else:
                c.execute('''INSERT OR REPLACE INTO magic_number_mappings (from_magic, to_magic)
                            VALUES (?, ?)''', (from_magic, to_magic))
                
                results.append({
                    'from': from_magic,
                    'to': to_magic,
                    'trades_updated': 0,
                    'success': True,
                    'message': 'Mapeo guardado para futuros trades'
                })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'total_mappings': len(mappings),
            'total_trades_updated': total_updated,
            'results': results,
            'message': f'✅ Unificación completada. {len(mappings)} mapeos guardados para futuras importaciones automáticas.'
        })
        
    except Exception as e:
        print(f"ERROR en unify_magic_numbers: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/active-mappings')
def get_active_mappings():
    conn = sqlite3.connect('trading_data.db')
    c = conn.cursor()
    c.execute('SELECT from_magic, to_magic, created_at FROM magic_number_mappings ORDER BY from_magic')
    mappings = c.fetchall()
    conn.close()
    
    return jsonify([{
        'from': m[0],
        'to': m[1],
        'created_at': m[2]
    } for m in mappings])

@app.route('/api/trades-detail')
def get_trades_detail():
    try:
        magic_number = request.args.get('magic_number')
        month = request.args.get('month')
        year = request.args.get('year', 'all')
        
        month_map = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
        }
        
        conn = sqlite3.connect('trading_data.db')
        query = '''SELECT open_time, close_time, symbol, type, lots, open_price, 
                   close_price, profit, comment 
                   FROM trades 
                   WHERE magic_number = ?'''
        params = [int(magic_number)]
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        df['close_time'] = pd.to_datetime(df['close_time'], errors='coerce')
        df = df.dropna(subset=['close_time'])
        
        if month and month in month_map:
            month_num = month_map[month]
            df = df[df['close_time'].dt.month == month_num]
        
        if year != 'all':
            try:
                year_int = int(year)
                df = df[df['close_time'].dt.year == year_int]
            except ValueError:
                pass
        
        result = []
        for _, row in df.iterrows():
            try:
                result.append({
                    'open_time': str(row['open_time']) if pd.notna(row['open_time']) else '',
                    'close_time': row['close_time'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['close_time']) else '',
                    'symbol': str(row['symbol']),
                    'type': str(row['type']),
                    'lots': float(row['lots']) if pd.notna(row['lots']) else 0.0,
                    'open_price': float(row['open_price']) if pd.notna(row['open_price']) else 0.0,
                    'close_price': float(row['close_price']) if pd.notna(row['close_price']) else 0.0,
                    'profit': float(row['profit']) if pd.notna(row['profit']) else 0.0,
                    'comment': str(row['comment']) if pd.notna(row['comment']) else ''
                })
            except Exception:
                continue
        
        return jsonify(result)
        
    except Exception as e:
        print(f"ERROR en get_trades_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-ea', methods=['POST'])
def delete_ea():
    try:
        data = request.json
        magic_number = data.get('magic_number')
        
        if not magic_number:
            return jsonify({'error': 'Magic number requerido', 'success': False}), 400
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM trades WHERE magic_number = ?', (magic_number,))
        count = c.fetchone()[0]
        
        if count == 0:
            conn.close()
            return jsonify({'error': f'No se encontraron trades para el EA {magic_number}', 'success': False}), 404
        
        c.execute('DELETE FROM trades WHERE magic_number = ?', (magic_number,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'magic_number': magic_number,
            'trades_deleted': count,
            'message': f'✅ EA {magic_number} eliminado ({count} trades)'
        })
        
    except Exception as e:
        print(f"ERROR en delete_ea: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/add-mapping', methods=['POST'])
def add_mapping():
    try:
        data = request.json
        from_magic = data.get('from_magic')
        to_magic = data.get('to_magic')
        update_existing = data.get('update_existing', False)
        
        if not from_magic or not to_magic:
            return jsonify({'error': 'Magic numbers requeridos', 'success': False}), 400
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM trades WHERE magic_number = ?', (from_magic,))
        existing_count = c.fetchone()[0]
        
        c.execute('''INSERT OR REPLACE INTO magic_number_mappings (from_magic, to_magic)
                    VALUES (?, ?)''', (from_magic, to_magic))
        
        updated_count = 0
        if update_existing and existing_count > 0:
            c.execute('UPDATE trades SET magic_number = ? WHERE magic_number = ?', (to_magic, from_magic))
            updated_count = existing_count
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'from_magic': from_magic,
            'to_magic': to_magic,
            'existing_trades': existing_count,
            'trades_updated': updated_count,
            'message': f'✅ Mapeo añadido: {from_magic} → {to_magic}'
        })
        
    except Exception as e:
        print(f"ERROR en add_mapping: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/delete-mapping', methods=['POST'])
def delete_mapping():
    try:
        data = request.json
        from_magic = data.get('from_magic')
        
        if not from_magic:
            return jsonify({'error': 'Magic number requerido', 'success': False}), 400
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('SELECT to_magic FROM magic_number_mappings WHERE from_magic = ?', (from_magic,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': f'No se encontró mapeo para {from_magic}', 'success': False}), 404
        
        to_magic = result[0]
        
        c.execute('DELETE FROM magic_number_mappings WHERE from_magic = ?', (from_magic,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'from_magic': from_magic,
            'to_magic': to_magic,
            'message': f'✅ Mapeo eliminado: {from_magic} → {to_magic}'
        })
        
    except Exception as e:
        print(f"ERROR en delete_mapping: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/reset-trades', methods=['POST'])
def reset_trades():
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM trades')
        trades_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM magic_number_mappings')
        mappings_count = c.fetchone()[0]
        
        c.execute('DELETE FROM trades')
        c.execute('DELETE FROM updates_log')
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'trades_deleted': trades_count,
            'mappings_preserved': mappings_count,
            'message': f'✅ {trades_count} trades eliminados. {mappings_count} mapeos conservados.'
        })
        
    except Exception as e:
        print(f"ERROR en reset_trades: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/api/max-dd-year')
def max_dd_year():
    """Calcula el Max DD filtrado por año Y otros filtros del dashboard"""
    try:
        year = request.args.get('year', '2025')
        source = request.args.get('source', 'all')
        symbol = request.args.get('symbol', 'all')
        timeframe = request.args.get('timeframe', 'all')
        magic_number = request.args.get('magic_number', 'all')
        trade_type = request.args.get('type', 'all')
        
        print(f"\n📊 Calculando Max DD Year:")
        print(f"   Año: {year}")
        print(f"   Source: {source}")
        print(f"   Symbol: {symbol}")
        print(f"   Timeframe: {timeframe}")
        print(f"   Magic: {magic_number}")
        print(f"   Type: {trade_type}")
        
        conn = sqlite3.connect('trading_data.db')
        
        # Construir query base
        query = 'SELECT close_time, profit FROM trades WHERE 1=1'
        params = []
        
        # Filtro por año
        if year != 'all':
            query += " AND close_time LIKE ?"
            params.append(f'{year}%')
        
        # Filtro por source
        if source != 'all':
            query += ' AND source = ?'
            params.append(source)
        
        # Filtro por symbol
        if symbol != 'all':
            query += ' AND symbol = ?'
            params.append(symbol)
        
        # Filtro por timeframe
        if timeframe != 'all':
            query += ' AND timeframe = ?'
            params.append(timeframe)
        
        # Filtro por magic number
        if magic_number != 'all':
            query += ' AND magic_number = ?'
            params.append(int(magic_number))
        
        # Filtro por tipo
        if trade_type != 'all':
            query += ' AND type = ?'
            params.append(trade_type)
        
        query += ' ORDER BY close_time'
        
        print(f"   Query: {query}")
        print(f"   Params: {params}")
        
        df = pd.read_sql_query(query, conn, params=params)
        
        print(f"   📊 Trades encontrados: {len(df)}")
        
        if len(df) > 0:
            print(f"   📅 Primera fecha: {df['close_time'].iloc[0]}")
            print(f"   📅 Última fecha: {df['close_time'].iloc[-1]}")
            print(f"   💰 Profit total: ${df['profit'].sum():.2f}")
        
        conn.close()
        
        if df.empty:
            print("   ⚠️ No hay datos, retornando 0")
            return jsonify({'max_dd': 0, 'year': year})
        
        # Calcular drawdown
        df['cumulative'] = df['profit'].cumsum()
        df['running_max'] = df['cumulative'].cummax()
        df['drawdown'] = df['cumulative'] - df['running_max']
        
        max_dd_abs = abs(df['drawdown'].min())
        
        # Calcular Max DD como PORCENTAJE
        capital_inicial = 100000
        max_dd_percent = (max_dd_abs / capital_inicial * 100) if capital_inicial > 0 else 0
        
        print(f"   📉 Equity final: ${df['cumulative'].iloc[-1]:.2f}")
        print(f"   📉 Max equity: ${df['running_max'].max():.2f}")
        print(f"   💵 Max DD (absoluto): ${max_dd_abs:.2f}")
        print(f"   📊 Capital inicial estimado: ${capital_inicial:.2f}")
        print(f"   ✅ Max DD (porcentaje): {max_dd_percent:.2f}%")
        
        return jsonify({
            'max_dd': round(max_dd_percent, 2),  # ← AHORA ES PORCENTAJE
            'year': year
        })
        
    except Exception as e:
        print(f"❌ Error en max_dd_year: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'max_dd': 0}), 500
    

# ============================================================================
# FORZAR PATH PARA IMPORTS (para Python portable)
# ============================================================================
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# REGISTRO DE BLUEPRINTS
# ============================================================================
from caracteristicas_ea import caracteristicas_bp, init_ea_characteristics_db

app.register_blueprint(caracteristicas_bp)
app.register_blueprint(cuenta_real_bp)
# Inicializar tablas de características EA
init_ea_characteristics_db()

@app.route('/api/portfolio/stats')
def get_portfolio_stats():
    """Calcula estadísticas del portafolio de EAs seleccionados"""
    try:
        magic_numbers = request.args.get('magic_numbers', '')
        
        if not magic_numbers:
            return jsonify({'error': 'No magic numbers provided'}), 400
        
        magic_list = [int(m.strip()) for m in magic_numbers.split(',')]
        
        print(f"\n📊 Calculando stats del portafolio: {magic_list}")
        
        conn = sqlite3.connect('trading_data.db')
        
        # Obtener todos los CSVs de esos EAs
        query = 'SELECT filename, magic_number FROM ea_characteristics WHERE magic_number IN ({})'.format(
            ','.join('?' * len(magic_list))
        )

        print(f"  🔍 Query: {query}")
        print(f"  🔍 Buscando magic_numbers: {magic_list}")

        df_eas = pd.read_sql_query(query, conn, params=magic_list)

        print(f"  📦 EAs encontrados: {len(df_eas)}")
        if not df_eas.empty:
            print(f"  📋 Magic numbers encontrados: {df_eas['magic_number'].tolist()}")
            print(f"  📁 Archivos: {df_eas['filename'].tolist()}")

        conn.close()
        
        if df_eas.empty:
            return jsonify({
                'net_profit': 0, 'total_trades': 0, 'win_rate': 0,
                'profit_factor': 0, 'expectancy': 0, 'sharpe_ratio': 0,
                'ret_dd': 0, 'sqn': 0, 'r2_equity': 0, 'cagr': 0,
                'rr_ratio': 0
            })
        
        # Combinar todos los trades de todos los EAs
        all_trades = []
        has_balance = False
        initial_balance_total = 0
        
        for _, row in df_eas.iterrows():
            filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
            print(f"  📁 Leyendo: {filepath}")
            print(f"  ✓ Existe: {os.path.exists(filepath)}")
            
            if os.path.exists(filepath):
                print(f"  🔄 Procesando CSV...")
                try:
                    df = pd.read_csv(filepath, sep=';', encoding='utf-8')
                    print(f"  📊 Filas leídas: {len(df)}")
                    print(f"  📋 Columnas: {df.columns.tolist()[:5]}")  # Primeras 5 columnas
                    
                    if 'Profit/Loss' not in df.columns:
                        print(f"  ⚠️ No hay columna Profit/Loss, probando separador ','")
                        df = pd.read_csv(filepath, sep=',', encoding='utf-8')
                        print(f"  📊 Filas leídas con ',': {len(df)}")
                    
                    df.columns = df.columns.str.strip().str.replace('"', '')
                    print(f"  📋 Columnas limpias: {df.columns.tolist()[:5]}")
                    
                    # ================================================================
                    # DETECTAR Y LEER BALANCE INICIAL
                    # ================================================================
                    if 'Balance' in df.columns:
                        df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')
                        if not has_balance:
                            initial_balance_total = df['Balance'].iloc[0]
                            has_balance = True
                            print(f"  💰 Balance inicial detectado: ${initial_balance_total}")
                    
                    if 'Close time' in df.columns and 'Profit/Loss' in df.columns:
                        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
                        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
                        df = df.dropna(subset=['Close time', 'Profit/Loss'])
                        
                        print(f"  ✅ Trades válidos: {len(df)}")
                        all_trades.append(df[['Close time', 'Profit/Loss']])
                    else:
                        print(f"  ❌ Faltan columnas necesarias")
                        
                except Exception as e:
                    print(f"  ❌ Error leyendo {row['filename']}: {e}")
            else:
                print(f"  ❌ Archivo no existe")
        
        if not all_trades:
            return jsonify({
                'net_profit': 0, 'total_trades': 0, 'win_rate': 0,
                'profit_factor': 0, 'expectancy': 0, 'sharpe_ratio': 0,
                'ret_dd': 0, 'sqn': 0, 'r2_equity': 0, 'cagr': 0,
                'rr_ratio': 0
            })
        
        # Combinar todos los DataFrames
        combined_df = pd.concat(all_trades, ignore_index=True)
        combined_df = combined_df.sort_values('Close time')
        
        # ================================================================
        # CÁLCULOS BÁSICOS
        # ================================================================
        total_trades = len(combined_df)
        net_profit = combined_df['Profit/Loss'].sum()
        
        winning_trades = len(combined_df[combined_df['Profit/Loss'] > 0])
        losing_trades = len(combined_df[combined_df['Profit/Loss'] < 0])
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = combined_df[combined_df['Profit/Loss'] > 0]['Profit/Loss'].sum()
        gross_loss = abs(combined_df[combined_df['Profit/Loss'] < 0]['Profit/Loss'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        avg_win = combined_df[combined_df['Profit/Loss'] > 0]['Profit/Loss'].mean() if winning_trades > 0 else 0
        avg_loss = abs(combined_df[combined_df['Profit/Loss'] < 0]['Profit/Loss'].mean()) if losing_trades > 0 else 0
        
        expectancy = ((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss))
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # ================================================================
        # EQUITY Y DRAWDOWN
        # ================================================================
        combined_df['cumulative'] = combined_df['Profit/Loss'].cumsum()
        combined_df['running_max'] = combined_df['cumulative'].cummax()
        combined_df['drawdown'] = combined_df['cumulative'] - combined_df['running_max']
        
        max_drawdown_abs = abs(combined_df['drawdown'].min())
        ret_dd = (net_profit / max_drawdown_abs) if max_drawdown_abs > 0 else 0
        
        # ================================================================
        # SQN - CORREGIDO (R-expectancy como SQX)
        # ================================================================
        avg_loss_for_risk = avg_loss if avg_loss > 0 else 1
        r_expectancy = expectancy / avg_loss_for_risk
        combined_df['R_multiples'] = combined_df['Profit/Loss'] / avg_loss_for_risk
        std_r = combined_df['R_multiples'].std(ddof=1) if len(combined_df) > 1 else 1
        sqn = (r_expectancy * (total_trades ** 0.5)) / std_r if std_r > 0 else 0
        print(f"  📊 SQN calculado: {sqn:.2f} (R-expectancy: {r_expectancy:.2f})")
        
        # ================================================================
        # R² EQUITY
        # ================================================================
        if len(combined_df) > 2:
            x = range(len(combined_df))
            y = combined_df['cumulative'].values
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
        
        # ================================================================
        # CAGR - CORREGIDO (Con Balance si existe)
        # ================================================================
        first_date = combined_df['Close time'].min()
        last_date = combined_df['Close time'].max()
        days_diff = (last_date - first_date).days
        
        if days_diff > 0 and has_balance and initial_balance_total > 0:
            # Usar Balance real del CSV
            final_balance = initial_balance_total + net_profit
            years = days_diff / 365.25
            
            if final_balance > 0:
                cagr = ((final_balance / initial_balance_total) ** (1 / years) - 1) * 100
                print(f"  💰 CAGR con Balance real: {cagr:.2f}% (Inicial: ${initial_balance_total}, Final: ${final_balance})")
            else:
                cagr = 0
        elif days_diff > 0:
            # Fallback sin Balance
            capital_requerido = 100000  # Capital real de la cuenta
            equity_final = capital_requerido + net_profit
            
            if capital_requerido > 0 and equity_final > 0:
                cagr = ((equity_final / capital_requerido) ** (365.25 / days_diff) - 1) * 100
                print(f"  ⚠️ CAGR aproximado (sin Balance): {cagr:.2f}%")
            else:
                cagr = 0
        else:
            cagr = 0
        
        # ================================================================
        # SHARPE - CORREGIDO (Sin anualizar)
        # ================================================================
        combined_df['date'] = combined_df['Close time'].dt.date
        daily_profit = combined_df.groupby('date')['Profit/Loss'].sum()
        
        if len(daily_profit) > 1:
            mean_daily = daily_profit.mean()
            std_daily = daily_profit.std(ddof=1)
            sharpe_ratio = (mean_daily / std_daily) if std_daily > 0 else 0
            print(f"  📊 Sharpe Ratio: {sharpe_ratio:.2f} (sin anualizar)")
        else:
            sharpe_ratio = 0
        
        print(f"✅ Stats calculados para {len(magic_list)} EAs, {total_trades} trades")
        
        return jsonify({
            'net_profit': round(net_profit, 2),
            'total_trades': total_trades,
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'ret_dd': round(ret_dd, 2),
            'sqn': round(sqn, 2),
            'r2_equity': round(r2_equity, 4),
            'cagr': round(cagr, 2),
            'rr_ratio': round(rr_ratio, 2)
        })
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio/monthly')
def get_portfolio_monthly():
    """Rentabilidad mensual del portafolio"""
    try:
        magic_numbers = request.args.get('magic_numbers', '')
        
        if not magic_numbers:
            return jsonify([])
        
        magic_list = [int(m.strip()) for m in magic_numbers.split(',')]
        
        conn = sqlite3.connect('trading_data.db')
        query = 'SELECT filename FROM ea_characteristics WHERE magic_number IN ({})'.format(
            ','.join('?' * len(magic_list))
        )
        df_eas = pd.read_sql_query(query, conn, params=magic_list)
        conn.close()
        
        if df_eas.empty:
            return jsonify([])
        
        all_trades = []
        
        for _, row in df_eas.iterrows():
            filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath, sep=';', encoding='utf-8')
                    if 'Profit/Loss' not in df.columns:
                        df = pd.read_csv(filepath, sep=',', encoding='utf-8')
                    
                    df.columns = df.columns.str.strip().str.replace('"', '')
                    
                    if 'Close time' in df.columns and 'Profit/Loss' in df.columns:
                        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
                        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
                        df = df.dropna(subset=['Close time', 'Profit/Loss'])
                        all_trades.append(df[['Close time', 'Profit/Loss']])
                except:
                    continue
        
        if not all_trades:
            return jsonify([])
        
        combined_df = pd.concat(all_trades, ignore_index=True)
        combined_df = combined_df.sort_values('Close time')
        combined_df['month'] = combined_df['Close time'].dt.strftime('%Y-%m')
        
        monthly = combined_df.groupby('month')['Profit/Loss'].sum().reset_index()
        monthly.columns = ['month', 'profit']
        
        return jsonify(monthly.to_dict('records'))
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_monthly: {e}")
        return jsonify([])


@app.route('/api/portfolio/drawdown')
def get_portfolio_drawdown():
    """Drawdown diario del portafolio"""
    try:
        magic_numbers = request.args.get('magic_numbers', '')
        
        if not magic_numbers:
            return jsonify([])
        
        magic_list = [int(m.strip()) for m in magic_numbers.split(',')]
        
        conn = sqlite3.connect('trading_data.db')
        query = 'SELECT filename FROM ea_characteristics WHERE magic_number IN ({})'.format(
            ','.join('?' * len(magic_list))
        )
        df_eas = pd.read_sql_query(query, conn, params=magic_list)
        conn.close()
        
        if df_eas.empty:
            return jsonify([])
        
        all_trades = []
        
        for _, row in df_eas.iterrows():
            filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath, sep=';', encoding='utf-8')
                    if 'Profit/Loss' not in df.columns:
                        df = pd.read_csv(filepath, sep=',', encoding='utf-8')
                    
                    df.columns = df.columns.str.strip().str.replace('"', '')
                    
                    if 'Close time' in df.columns and 'Profit/Loss' in df.columns:
                        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
                        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
                        df = df.dropna(subset=['Close time', 'Profit/Loss'])
                        all_trades.append(df[['Close time', 'Profit/Loss']])
                except:
                    continue
        
        if not all_trades:
            return jsonify([])
        
        combined_df = pd.concat(all_trades, ignore_index=True)
        combined_df = combined_df.sort_values('Close time')
        combined_df['date'] = combined_df['Close time'].dt.date
        
        daily_data = combined_df.groupby('date')['Profit/Loss'].sum().reset_index()
        daily_data['equity'] = daily_data['Profit/Loss'].cumsum()
        daily_data['running_max'] = daily_data['equity'].cummax()
        daily_data['drawdown'] = daily_data['equity'] - daily_data['running_max']
        daily_data['date'] = daily_data['date'].astype(str)
        
        return jsonify(daily_data.to_dict('records'))
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_drawdown: {e}")
        return jsonify([])

@app.route('/api/portfolio/max-dd-year')
def get_portfolio_max_dd_year():
    """Calcula Max DD por año del portafolio"""
    try:
        magic_numbers = request.args.get('magic_numbers', '')
        year = request.args.get('year', str(datetime.now().year))
        
        if not magic_numbers:
            return jsonify({'max_dd': 0, 'year': year})
        
        magic_list = [int(m.strip()) for m in magic_numbers.split(',')]
        
        print(f"\n📊 Calculando Max DD Year del portfolio: {magic_list}, año {year}")
        
        conn = sqlite3.connect('trading_data.db')
        query = 'SELECT filename FROM ea_characteristics WHERE magic_number IN ({})'.format(
            ','.join('?' * len(magic_list))
        )
        df_eas = pd.read_sql_query(query, conn, params=magic_list)
        conn.close()
        
        if df_eas.empty:
            return jsonify({'max_dd': 0, 'year': year})
        
        all_trades = []
        
        for _, row in df_eas.iterrows():
            filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
            if os.path.exists(filepath):
                try:
                    df = pd.read_csv(filepath, sep=';', encoding='utf-8')
                    if 'Profit/Loss' not in df.columns:
                        df = pd.read_csv(filepath, sep=',', encoding='utf-8')
                    
                    df.columns = df.columns.str.strip().str.replace('"', '')
                    
                    if 'Close time' in df.columns and 'Profit/Loss' in df.columns:
                        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
                        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
                        df = df.dropna(subset=['Close time', 'Profit/Loss'])
                        
                        # Filtrar por año
                        if year != 'all':
                            df = df[df['Close time'].dt.year == int(year)]
                        
                        if not df.empty:
                            all_trades.append(df[['Close time', 'Profit/Loss']])
                except:
                    continue
        
        if not all_trades:
            return jsonify({'max_dd': 0, 'year': year})
        
        # Combinar todos los trades
        combined_df = pd.concat(all_trades, ignore_index=True)
        combined_df = combined_df.sort_values('Close time')
        
        # Calcular drawdown
        combined_df['cumulative'] = combined_df['Profit/Loss'].cumsum()
        combined_df['running_max'] = combined_df['cumulative'].cummax()
        combined_df['drawdown'] = combined_df['cumulative'] - combined_df['running_max']
        
        max_dd_abs = abs(combined_df['drawdown'].min())
        
        # Calcular como porcentaje
        capital_inicial = 100000  # Capital real de la cuenta
        max_dd_percent = (max_dd_abs / capital_inicial * 100) if capital_inicial > 0 else 0
        
        print(f"   ✅ Max DD: {max_dd_percent:.2f}%")
        
        return jsonify({
            'max_dd': round(max_dd_percent, 2),
            'year': year
        })
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_max_dd_year: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'max_dd': 0}), 500
    
@app.route('/api/portfolio/ea-monthly')
def get_portfolio_ea_monthly():
    """Análisis mensual por EA"""
    try:
        magic_numbers = request.args.get('magic_numbers', '')
        
        if not magic_numbers:
            return jsonify([])
        
        magic_list = [int(m.strip()) for m in magic_numbers.split(',')]
        
        result = []
        
        for magic in magic_list:
            conn = sqlite3.connect('trading_data.db')
            df_ea = pd.read_sql_query(
                'SELECT filename, caracteristicas FROM ea_characteristics WHERE magic_number = ?',
                conn, params=[magic]
            )
            conn.close()
            
            if df_ea.empty:
                continue
            
            filepath = os.path.join(UPLOAD_FOLDER, df_ea.iloc[0]['filename'])
            
            if not os.path.exists(filepath):
                continue
            
            try:
                df = pd.read_csv(filepath, sep=';', encoding='utf-8')
                if 'Profit/Loss' not in df.columns:
                    df = pd.read_csv(filepath, sep=',', encoding='utf-8')
                
                df.columns = df.columns.str.strip().str.replace('"', '')
                
                if 'Close time' not in df.columns or 'Profit/Loss' not in df.columns:
                    continue
                
                df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
                df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
                df = df.dropna(subset=['Close time', 'Profit/Loss'])
                
                df['month'] = df['Close time'].dt.strftime('%b').str.upper()
                
                monthly = df.groupby('month')['Profit/Loss'].sum().to_dict()
                
                ea_data = {
                    'magic_number': magic,
                    'name': df_ea.iloc[0]['caracteristicas'] or f'EA {magic}'
                }
                
                months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
                month_map = {'JAN': 'ENE', 'FEB': 'FEB', 'MAR': 'MAR', 'APR': 'ABR', 'MAY': 'MAY', 'JUN': 'JUN',
                            'JUL': 'JUL', 'AUG': 'AGO', 'SEP': 'SEP', 'OCT': 'OCT', 'NOV': 'NOV', 'DEC': 'DIC'}
                
                for month in months:
                    profit = 0
                    for eng_month, esp_month in month_map.items():
                        if esp_month == month and eng_month in monthly:
                            profit = monthly[eng_month]
                            break
                    ea_data[month] = profit
                
                ea_data['total'] = sum(monthly.values())
                
                result.append(ea_data)
                
            except Exception as e:
                print(f"Error procesando EA {magic}: {e}")
                continue
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_ea_monthly: {e}")
        return jsonify([])

@app.route('/api/portfolio/ea-details')
def get_portfolio_ea_details():
    """Obtiene detalles completos de los EAs en el portafolio"""
    try:
        magic_numbers = request.args.get('magic_numbers', '')
        
        if not magic_numbers:
            return jsonify([])
        
        magic_list = [int(m.strip()) for m in magic_numbers.split(',')]
        
        conn = sqlite3.connect('trading_data.db')
        query = '''SELECT magic_number, activo, direccion, timeframe, caracteristicas, 
                          walk_forward, fecha_futura 
                   FROM ea_characteristics 
                   WHERE magic_number IN ({})'''.format(','.join('?' * len(magic_list)))
        
        df = pd.read_sql_query(query, conn, params=magic_list)
        conn.close()
        
        return jsonify(df.to_dict('records'))
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_ea_details: {e}")
        return jsonify([])

@app.route('/api/portfolio/trades-detail/<int:magic_number>/<month>')
def get_portfolio_trades_detail(magic_number, month):
    """Obtiene trades de un EA específico en un mes específico"""
    try:
        year = request.args.get('year', str(datetime.now().year))
        
        # Mapeo de meses español a número
        month_map = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
        }
        
        month_num = month_map.get(month.upper())
        
        if not month_num:
            return jsonify({'error': 'Mes inválido'}), 400
        
        conn = sqlite3.connect('trading_data.db')
        df_ea = pd.read_sql_query(
            'SELECT filename FROM ea_characteristics WHERE magic_number = ?',
            conn, params=[magic_number]
        )
        conn.close()
        
        if df_ea.empty:
            return jsonify({'error': 'EA no encontrado'}), 404
        
        filepath = os.path.join(UPLOAD_FOLDER, df_ea.iloc[0]['filename'])
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404
        
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        if 'Profit/Loss' not in df.columns:
            df = pd.read_csv(filepath, sep=',', encoding='utf-8')
        
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.replace('"', '')
        
        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        df = df.dropna(subset=['Close time', 'Profit/Loss'])
        
        # Filtrar por año y mes
        df_filtered = df[
            (df['Close time'].dt.year == int(year)) & 
            (df['Close time'].dt.month == month_num)
        ]
        
        if df_filtered.empty:
            return jsonify({
                'trades': [],
                'summary': {'total': 0, 'profit': 0, 'win_rate': 0}
            })
        
        trades = []
        for _, row in df_filtered.iterrows():
            trades.append({
                'close_time': row['Close time'].strftime('%Y-%m-%d %H:%M'),
                'symbol': row.get('Symbol', '-'),
                'type': row.get('Type', '-'),
                'volume': float(row.get('Lots', 0) or 0),
                'open_price': float(row.get('Open price', 0) or 0),
                'close_price': float(row.get('Close price', 0) or 0),
                'profit': float(row['Profit/Loss']),
                'comment': row.get('Order comment', '-')
            })
        
        total = len(trades)
        winning = len([t for t in trades if t['profit'] > 0])
        profit_sum = sum(t['profit'] for t in trades)
        win_rate = (winning / total * 100) if total > 0 else 0
        
        return jsonify({
            'trades': trades,
            'summary': {
                'total': total,
                'profit': round(profit_sum, 2),
                'win_rate': round(win_rate, 2)
            }
        })
        
    except Exception as e:
        print(f"❌ Error en get_portfolio_trades_detail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============================================================================
# RUTAS - ANÁLISIS PROPFIRMS
# ============================================================================

@app.route('/api/propfirm/simulate', methods=['POST'])
def simulate_propfirm():
    """Simula desafíos de propfirm para los EAs seleccionados"""
    try:
        data = request.json
        magic_numbers = data.get('magic_numbers', [])
        config = data.get('config', {})
        
        print(f"\n🎯 Simulando Propfirm Challenge")
        print(f"   EAs: {magic_numbers}")
        print(f"   Config: {config}")
        
        if not magic_numbers:
            return jsonify({'error': 'No se proporcionaron EAs'}), 400
        
        capital = config.get('capital', 100000)
        threshold1 = config.get('threshold1', 8) / 100  # Convertir % a decimal
        threshold2 = config.get('threshold2', 5) / 100
        dd_daily_limit = config.get('ddDaily', 5) / 100
        dd_max_limit = config.get('ddMax', 10) / 100
        risk = config.get('risk', 2500)  # ← AÑADIR ESTA LÍNEA
        
        print(f"   💰 Capital: ${capital}")
        print(f"   📊 Umbral Fase 1: {threshold1*100}%")
        print(f"   📊 Umbral Fase 2: {threshold2*100}%")
        print(f"   ⚠️ Riesgo por operación: ${risk}")
        print(f"   🚫 DD Diario: {dd_daily_limit*100}%")
        print(f"   🚫 DD Máximo: {dd_max_limit*100}%")
        
        results = []
        
        for magic_number in magic_numbers:
            print(f"\n📊 Procesando EA {magic_number}...")
            
            # Obtener info del EA
            conn = sqlite3.connect('trading_data.db')
            df_ea = pd.read_sql_query(
                'SELECT filename, caracteristicas FROM ea_characteristics WHERE magic_number = ?',
                conn, params=[magic_number]
            )
            conn.close()
            
            if df_ea.empty:
                print(f"   ⚠️ EA {magic_number} no encontrado")
                continue
            
            filename = df_ea.iloc[0]['filename']
            ea_name = df_ea.iloc[0]['caracteristicas'] or f'EA {magic_number}'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            if not os.path.exists(filepath):
                print(f"   ⚠️ Archivo no encontrado: {filepath}")
                continue
            
            # Leer CSV
            df = pd.read_csv(filepath, sep=';', encoding='utf-8')
            if 'Profit/Loss' not in df.columns:
                df = pd.read_csv(filepath, sep=',', encoding='utf-8')
            
            df.columns = df.columns.str.strip().str.replace('"', '')
            
            if 'Close time' not in df.columns or 'Profit/Loss' not in df.columns:
                print(f"   ⚠️ Columnas necesarias no encontradas")
                continue
            
            df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
            df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
            df = df.dropna(subset=['Close time', 'Profit/Loss'])
            df = df.sort_values('Close time')
            
            print(f"   ✓ {len(df)} trades cargados")
            
            # SIMULAR DESAFÍOS (ahora SÍ tiene la variable risk definida)
            simulation = simulate_challenges(df, capital, threshold1, threshold2, dd_daily_limit, dd_max_limit, risk)
            
            results.append({
                'magic_number': magic_number,
                'name': ea_name,
                'completed': simulation['completed'],
                'avg_time': simulation['avg_time'],
                'best_time': simulation['best_time'],
                'success_rate': simulation['success_rate'],
                'total_months': simulation['total_months'],
                'susp_dd_max': simulation['susp_dd_max'],
                'susp_dd_daily': simulation['susp_dd_daily']
            })
        
        # Calcular resumen
        total_completed = sum(r['completed'] for r in results)
        avg_time_all = sum(r['avg_time'] for r in results) / len(results) if results else 0
        best_strategy = max(results, key=lambda x: x['completed'])['name'] if results else '-'
        
        summary = {
            'total_strategies': len(results),
            'completed_challenges': total_completed,
            'avg_time': avg_time_all,
            'best_strategy': best_strategy
        }
        
        print(f"\n✅ Simulación completada")
        print(f"   Total completados: {total_completed}")
        
        return jsonify({
            'summary': summary,
            'strategies': results
        })
        
    except Exception as e:
        print(f"❌ Error en simulate_propfirm: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
@app.route('/api/propfirm/strategy-trades', methods=['POST'])
def get_strategy_trades():
    """Devuelve trades escalados de una estrategia específica"""
    try:
        data = request.json
        magic_number = data.get('magic_number')
        config = data.get('config', {})
        
        print(f"\n📊 Obteniendo trades escalados de EA {magic_number}")
        
        # Obtener info del EA
        conn = sqlite3.connect('trading_data.db')
        df_ea = pd.read_sql_query(
            'SELECT filename FROM ea_characteristics WHERE magic_number = ?',
            conn, params=[magic_number]
        )
        conn.close()
        
        if df_ea.empty:
            return jsonify({'error': 'EA no encontrado'}), 404
        
        filepath = os.path.join(UPLOAD_FOLDER, df_ea.iloc[0]['filename'])
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404
        
        # Leer CSV
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        if 'Profit/Loss' not in df.columns:
            df = pd.read_csv(filepath, sep=',', encoding='utf-8')
        
        df.columns = df.columns.str.strip().str.replace('"', '')
        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        df = df.dropna(subset=['Close time', 'Profit/Loss'])
        df = df.sort_values('Close time')
        
        # Calcular escalado
        capital = config.get('capital', 100000)
        risk = config.get('risk', 2500)
        threshold1 = config.get('threshold1', 8) / 100
        threshold2 = config.get('threshold2', 5) / 100
        dd_daily_limit = config.get('ddDaily', 5) / 100
        dd_max_limit = config.get('ddMax', 10) / 100
        
        avg_loss = abs(df[df['Profit/Loss'] < 0]['Profit/Loss'].mean())
        if pd.isna(avg_loss) or avg_loss == 0:
            avg_loss = 100
        
        scaling_factor = risk / avg_loss
        df['Scaled_PnL'] = df['Profit/Loss'] * scaling_factor
        
        # Simular y marcar estados
        trades = []
        balance = capital
        peak_balance = capital
        phase = 1
        current_day = None
        day_start_balance = capital
        
        for idx, row in df.iterrows():
            trade_date = row['Close time']
            trade_day = trade_date.date()
            
            if current_day != trade_day:
                current_day = trade_day
                day_start_balance = balance
            
            scaled_pnl = row['Scaled_PnL']
            balance += scaled_pnl
            
            if balance > peak_balance:
                peak_balance = balance
            
            dd_from_peak = (peak_balance - balance) / peak_balance
            dd_daily = (day_start_balance - balance) / capital
            
            # Determinar estado
            status = 'active'
            if dd_from_peak > dd_max_limit:
                status = 'susp_dd_max'
                balance = capital
                peak_balance = capital
                phase = 1
                day_start_balance = capital
            elif dd_daily > dd_daily_limit:
                status = 'susp_dd_daily'
                balance = capital
                peak_balance = capital
                phase = 1
                day_start_balance = capital
            else:
                gain = (balance - capital) / capital
                if phase == 1 and gain >= threshold1:
                    phase = 2
                    status = 'phase1'
                elif phase == 2 and gain >= (threshold1 + threshold2):
                    status = 'completed'
                    balance = capital
                    peak_balance = capital
                    phase = 1
                    day_start_balance = capital
            
            trades.append({
                'close_time': trade_date.strftime('%Y-%m-%d %H:%M'),
                'symbol': row.get('Symbol', '-'),
                'type': row.get('Type', '-'),
                'original_pnl': float(row['Profit/Loss']),
                'scaled_pnl': float(scaled_pnl),
                'balance': float(balance),
                'status': status
            })
        
        return jsonify({
            'trades': trades,
            'scaling_factor': scaling_factor
        })
        
    except Exception as e:
        print(f"❌ Error en get_strategy_trades: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
    
def simulate_challenges(df, capital, threshold1, threshold2, dd_daily_limit, dd_max_limit, risk_per_trade):
    """Simula múltiples intentos de desafío con un EA - VERSIÓN CORREGIDA"""
    
    # PASO 1: Calcular el riesgo promedio del CSV original
    avg_loss = abs(df[df['Profit/Loss'] < 0]['Profit/Loss'].mean())
    
    if pd.isna(avg_loss) or avg_loss == 0:
        avg_loss = 100  # Fallback si no hay pérdidas
    
    # PASO 2: Calcular factor de escalado
    scaling_factor = risk_per_trade / avg_loss
    
    print(f"      💡 Riesgo original: ${avg_loss:.2f}")
    print(f"      💡 Riesgo objetivo: ${risk_per_trade}")
    print(f"      💡 Factor de escalado: {scaling_factor:.2f}x")
    
    # PASO 3: Escalar todos los trades
    df['Scaled_PnL'] = df['Profit/Loss'] * scaling_factor
    
    # Variables de simulación
    completed_challenges = 0
    challenge_times = []
    susp_dd_max = 0
    susp_dd_daily = 0
    
    # Estado del desafío actual
    phase = 1
    balance = capital
    peak_balance = capital
    start_date = None
    start_trade_idx = 0
    
    # Control diario
    current_day = None
    day_start_balance = capital
    
    print(f"      🎯 Objetivo Fase 1: ${capital * (1 + threshold1):.2f}")
    print(f"      🎯 Objetivo Fase 2: ${capital * (1 + threshold1 + threshold2):.2f}")
    print(f"      ⚠️ DD Diario límite: {dd_daily_limit*100:.1f}%")
    print(f"      ⚠️ DD Máximo límite: {dd_max_limit*100:.1f}%")
    
    for idx, row in df.iterrows():
        trade_date = row['Close time']
        scaled_pnl = row['Scaled_PnL']
        
        # Iniciar desafío si es el primero
        if start_date is None:
            start_date = trade_date
            start_trade_idx = idx
        
        # Detectar nuevo día
        trade_day = trade_date.date()
        if current_day != trade_day:
            current_day = trade_day
            day_start_balance = balance
        
        # APLICAR TRADE
        balance += scaled_pnl
        
        # Actualizar pico
        if balance > peak_balance:
            peak_balance = balance
        
        # CALCULAR DDs
        dd_from_peak = (peak_balance - balance) / peak_balance
        dd_daily = (day_start_balance - balance) / capital  # DD diario respecto al capital inicial
        
        # VERIFICAR DD MÁXIMO
        if dd_from_peak > dd_max_limit:
            susp_dd_max += 1
            print(f"         ❌ Trade {idx}: SUSP DD MAX ({dd_from_peak*100:.2f}%) - Balance: ${balance:.2f}")
            
            # RESETEAR y CONTINUAR
            phase = 1
            balance = capital
            peak_balance = capital
            start_date = None
            day_start_balance = capital
            continue
        
        # VERIFICAR DD DIARIO
        if dd_daily > dd_daily_limit:
            susp_dd_daily += 1
            print(f"         ❌ Trade {idx}: SUSP DD DIARIO ({dd_daily*100:.2f}%) - Balance: ${balance:.2f}")
            
            # RESETEAR y CONTINUAR
            phase = 1
            balance = capital
            peak_balance = capital
            start_date = None
            day_start_balance = capital
            continue
        
        # VERIFICAR OBJETIVOS
        gain = (balance - capital) / capital
        
        if phase == 1 and gain >= threshold1:
            # ✅ FASE 1 COMPLETADA
            print(f"         ✅ Trade {idx}: FASE 1 COMPLETADA ({gain*100:.2f}%) - Balance: ${balance:.2f}")
            phase = 2
        
        elif phase == 2 and gain >= (threshold1 + threshold2):
            # 🎉 DESAFÍO COMPLETADO
            days_taken = (trade_date - start_date).days
            trades_taken = idx - start_trade_idx + 1
            challenge_times.append(days_taken)
            completed_challenges += 1
            
            print(f"         🎉 Trade {idx}: DESAFÍO #{completed_challenges} COMPLETADO en {days_taken} días ({trades_taken} trades)")
            
            # RESETEAR y CONTINUAR
            phase = 1
            balance = capital
            peak_balance = capital
            start_date = None
            day_start_balance = capital
    
    # CALCULAR ESTADÍSTICAS FINALES
    avg_time = sum(challenge_times) / len(challenge_times) if challenge_times else 0
    best_time = min(challenge_times) if challenge_times else 0
    
    total_months = (df['Close time'].max() - df['Close time'].min()).days / 30.44 if len(df) > 0 else 0
    total_attempts = completed_challenges + susp_dd_max + susp_dd_daily
    success_rate = (completed_challenges / total_attempts * 100) if total_attempts > 0 else 0
    
    print(f"\n      📊 RESUMEN:")
    print(f"         ✅ Completados: {completed_challenges}")
    print(f"         ❌ Susp DD Max: {susp_dd_max}")
    print(f"         ❌ Susp DD Diario: {susp_dd_daily}")
    print(f"         📈 Tasa éxito: {success_rate:.1f}%")
    
    return {
        'completed': completed_challenges,
        'avg_time': avg_time,
        'best_time': best_time,
        'success_rate': success_rate,
        'total_months': int(total_months),
        'susp_dd_max': susp_dd_max,
        'susp_dd_daily': susp_dd_daily
    }

if __name__ == '__main__':
    init_db()
    init_ea_characteristics_db()
    init_cuenta_real_db()  # ← AÑADIR ESTA LÍNEA
    
    print("\n" + "="*60)
    print("🚀 REYGON TRADING DASHBOARD")
    print("="*60)
    print("Base de datos inicializada ✓")
    print("Sistema de unificación automática activado ✓")
    print("Cuenta Real activada ✓")
    print("Servidor Flask iniciado ✓")
    print("\nVisita: http://localhost:5000")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)