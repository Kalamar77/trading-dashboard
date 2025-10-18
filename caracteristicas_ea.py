from flask import Blueprint, request, jsonify
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import re
from werkzeug.utils import secure_filename
import os

caracteristicas_bp = Blueprint('caracteristicas', __name__)

UPLOAD_FOLDER = 'uploads_ea'
ALLOWED_EXTENSIONS = {'csv'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_filename(filename):
    """
    Parsea el nombre del archivo con formato flexible:
    ACTIVO_DIRECCION_TEMPORALIDAD_CARACTERISTICAS_WALKFORWARD_FECHA_MAGIC.csv
    
    Ejemplo: XAU_B_H1_LWMA_6-32_07-05-2026_52037.csv
    """
    try:
        import re
        
        name = filename.replace('.csv', '').replace('.CSV', '')
        parts = [p for p in name.split('_') if p]
        
        print(f"📋 Parseando: {filename}")
        print(f"   Partes: {parts}")
        
        if len(parts) < 3:
            print(f"⚠️ Muy pocas partes (mínimo 3)")
            return None
        
        # Patrones de detección
        timeframe_pattern = re.compile(r'^(M1|M5|M15|M30|H1|H2|H4|H6|H8|H12|D1|W1|MN1?)$', re.IGNORECASE)
        fecha_pattern = re.compile(r'^\d{2}-\d{2}-\d{4}$')
        walk_forward_pattern = re.compile(r'^(\d+-\d+%?|ORIG%?)$', re.IGNORECASE)  # ✅ Acepta números Y ORIG
        direccion_values = ['B', 'S', 'BS', 'SB']
        
        # Inicializar
        activo = parts[0]
        direccion = None
        timeframe = None
        caracteristicas = []
        walk_forward = None
        fecha_futura = None
        magic_number = None
        
        # Clasificar cada parte
        for i, part in enumerate(parts[1:], 1):
            if i == len(parts) - 1 and part.isdigit():
                magic_number = part
            elif fecha_pattern.match(part):
                fecha_futura = part
            elif walk_forward_pattern.match(part):
                walk_forward = part
            elif timeframe_pattern.match(part):
                timeframe = part.upper()
            elif part.upper() in direccion_values:
                direccion = part.upper()
            else:
                caracteristicas.append(part)
        
        # Valores por defecto
        direccion = direccion or 'BS'
        timeframe = timeframe or 'H1'
        caracteristicas_str = '_'.join(caracteristicas) if caracteristicas else 'Strategy'
        walk_forward = walk_forward or 'N/A'
        fecha_futura = fecha_futura or ''
        magic_number = magic_number or '0'
        
        # Mapear dirección
        direccion_map = {
            'B': 'Buy',
            'S': 'Sell',
            'BS': 'Buy/Sell',
            'SB': 'Buy/Sell'
        }
        direccion_full = direccion_map.get(direccion, 'Buy/Sell')
        
        print(f"✅ Resultado:")
        print(f"   Activo: {activo}")
        print(f"   Dirección: {direccion_full}")
        print(f"   Timeframe: {timeframe}")
        print(f"   Características: {caracteristicas_str}")
        print(f"   Walk Forward: {walk_forward}")
        print(f"   Fecha Futura: {fecha_futura}")
        print(f"   Magic Number: {magic_number}")
        
        return {
            'activo': activo,
            'direccion': direccion_full,
            'timeframe': timeframe,
            'caracteristicas': caracteristicas_str,
            'walk_forward': walk_forward,
            'fecha_futura': fecha_futura,
            'magic_number': magic_number,
            'symbol': activo,
            'strategy': caracteristicas_str,
            'trade_type': direccion_full
        }
        
    except Exception as e:
        print(f"❌ Error parseando: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
    
def init_ea_characteristics_db():
    """Inicializa las tablas para características de EAs"""
    conn = sqlite3.connect('trading_data.db')
    c = conn.cursor()
    
    # Tabla principal de EAs con sus características (ACTUALIZADA)
    c.execute('''CREATE TABLE IF NOT EXISTS ea_characteristics
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  magic_number INTEGER UNIQUE,
                  activo TEXT,
                  direccion TEXT,
                  timeframe TEXT,
                  caracteristicas TEXT,
                  walk_forward TEXT,
                  fecha_futura TEXT,
                  symbol TEXT,
                  strategy TEXT,
                  range_config TEXT,
                  trade_type TEXT,
                  filename TEXT,
                  upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
                  total_backtests INTEGER DEFAULT 0,
                  best_params TEXT,
                  notes TEXT,
                  comment TEXT)''')
    
    # Tabla de resultados de backtesting
    c.execute('''CREATE TABLE IF NOT EXISTS ea_backtest_results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  magic_number INTEGER,
                  test_number INTEGER,
                  net_profit REAL,
                  total_trades INTEGER,
                  win_rate REAL,
                  profit_factor REAL,
                  max_drawdown REAL,
                  sharpe_ratio REAL,
                  parameters TEXT,
                  upload_date TEXT DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (magic_number) REFERENCES ea_characteristics(magic_number))''')
    
    conn.commit()
    conn.close()
    
    # Actualizar tabla si es necesaria
    upgrade_ea_characteristics_table()

def upgrade_ea_characteristics_table():
    """Añade nuevas columnas si no existen"""
    conn = sqlite3.connect('trading_data.db')
    c = conn.cursor()
    
    # Obtener columnas existentes
    c.execute("PRAGMA table_info(ea_characteristics)")
    existing_columns = [col[1] for col in c.fetchall()]
    
    # Añadir columnas nuevas si no existen
    new_columns = {
        'activo': 'TEXT',
        'direccion': 'TEXT',
        'caracteristicas': 'TEXT',
        'walk_forward': 'TEXT',
        'fecha_futura': 'TEXT',
        'comment': 'TEXT'
    }
    
    for column_name, column_type in new_columns.items():
        if column_name not in existing_columns:
            try:
                c.execute(f'ALTER TABLE ea_characteristics ADD COLUMN {column_name} {column_type}')
                print(f"✅ Columna '{column_name}' añadida a ea_characteristics")
            except Exception as e:
                print(f"⚠️ No se pudo añadir columna '{column_name}': {e}")
    
    conn.commit()
    conn.close()

# ============================================================================
# RUTAS
# ============================================================================

@caracteristicas_bp.route('/api/ea/upload', methods=['POST'])
def upload_ea_csv():
    """Sube y procesa CSVs de características de EAs"""
    try:
        if 'files[]' not in request.files:
            return jsonify({'error': 'No hay archivos', 'success': False}), 400
        
        files = request.files.getlist('files[]')
        
        if not files or files[0].filename == '':
            return jsonify({'error': 'No se seleccionaron archivos', 'success': False}), 400
        
        results = []
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Parsear nombre del archivo
                parsed = parse_filename(filename)
                
                if not parsed:
                    results.append({
                        'filename': filename,
                        'success': False,
                        'error': 'Formato incorrecto. Debe ser: ACTIVO_DIRECCION__TEMPORALIDAD_CARACTERISTICAS_WALKFORWARD_FECHA_MAGIC.csv (Ej: DAX_B__H1_HULLMOVING_8-24%_17-02-2026_41193.csv)'
                    })
                    continue
                
                # Guardar archivo
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                # Leer CSV con punto y coma como delimitador
                try:
                    # Intentar leer con punto y coma primero
                    df = pd.read_csv(filepath, sep=';', encoding='utf-8')
                    
                    # Limpiar nombres de columnas (quitar comillas y espacios)
                    df.columns = df.columns.str.strip().str.replace('"', '')
                    
                    # Verificar que tenga columnas de trades individuales
                    if 'Profit/Loss' not in df.columns:
                        # Intentar con coma como delimitador
                        df = pd.read_csv(filepath, sep=',', encoding='utf-8')
                        df.columns = df.columns.str.strip().str.replace('"', '')
                    
                    if 'Profit/Loss' not in df.columns:
                        results.append({
                            'filename': filename,
                            'success': False,
                            'error': 'CSV no tiene la columna "Profit/Loss" requerida'
                        })
                        continue
                    
                    # Limpiar valores entre comillas
                    for col in df.columns:
                        if df[col].dtype == 'object':
                            df[col] = df[col].astype(str).str.strip().str.replace('"', '')
                    
                    # Convertir Profit/Loss a numérico
                    df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
                    
                    # Calcular estadísticas agregadas
                    total_trades = len(df)
                    net_profit = df['Profit/Loss'].sum()
                    
                    winning_trades = len(df[df['Profit/Loss'] > 0])
                    losing_trades = len(df[df['Profit/Loss'] < 0])
                    
                    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                    
                    gross_profit = df[df['Profit/Loss'] > 0]['Profit/Loss'].sum()
                    gross_loss = abs(df[df['Profit/Loss'] < 0]['Profit/Loss'].sum())
                    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
                    
                    # Calcular drawdown
                    df_sorted = df.sort_values('Close time') if 'Close time' in df.columns else df
                    df_sorted['cumulative'] = df_sorted['Profit/Loss'].cumsum()
                    df_sorted['running_max'] = df_sorted['cumulative'].cummax()
                    df_sorted['drawdown'] = df_sorted['cumulative'] - df_sorted['running_max']
                    max_drawdown_abs = abs(df_sorted['drawdown'].min())

                    # Calcular Max DD como PORCENTAJE
                    capital_inicial = 100000  # Capital real de la cuenta
                    max_drawdown = (max_drawdown_abs / capital_inicial * 100) if capital_inicial > 0 else 0
                    
                    # Calcular Sharpe (simplificado)
                    profit_std = df['Profit/Loss'].std() if len(df) > 1 else 0
                    avg_profit = df['Profit/Loss'].mean()
                    sharpe_ratio = (avg_profit / profit_std) if profit_std > 0 else 0
                    
                    # Insertar o actualizar EA
                    c.execute('''INSERT OR REPLACE INTO ea_characteristics 
                                (magic_number, activo, direccion, timeframe, caracteristicas,
                                walk_forward, fecha_futura, symbol, strategy, trade_type, 
                                filename, upload_date, total_backtests)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (int(parsed['magic_number']), 
                            parsed['activo'],
                            parsed['direccion'],
                            parsed['timeframe'],
                            parsed['caracteristicas'],
                            parsed['walk_forward'],
                            parsed['fecha_futura'],
                            parsed['symbol'],
                            parsed['strategy'],
                            parsed['trade_type'],
                            filename,
                            datetime.now().isoformat(),
                            1))
                    
                    # Borrar backtest anterior de este EA
                    c.execute('DELETE FROM ea_backtest_results WHERE magic_number = ?', 
                             (int(parsed['magic_number']),))
                    
                    # Insertar resultado agregado del backtest
                    c.execute('''INSERT INTO ea_backtest_results 
                                (magic_number, test_number, net_profit, total_trades, 
                                 win_rate, profit_factor, max_drawdown, sharpe_ratio, parameters)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                             (int(parsed['magic_number']),
                              1,
                              float(net_profit),
                              int(total_trades),
                              float(win_rate),
                              float(profit_factor),
                              float(max_drawdown),
                              float(sharpe_ratio),
                              f'{{"winning_trades": {winning_trades}, "losing_trades": {losing_trades}, "gross_profit": {gross_profit:.2f}, "gross_loss": {gross_loss:.2f}}}'))
                    
                    results.append({
                        'filename': filename,
                        'success': True,
                        'magic_number': parsed['magic_number'],
                        'trades': total_trades,
                        'net_profit': round(net_profit, 2),
                        'win_rate': round(win_rate, 1),
                        'symbol': parsed['symbol'],
                        'strategy': parsed['strategy']
                    })
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"ERROR procesando {filename}:")
                    print(error_detail)
                    
                    results.append({
                        'filename': filename,
                        'success': False,
                        'error': f'Error procesando CSV: {str(e)}'
                    })
        
        conn.commit()
        conn.close()
        
        successful = len([r for r in results if r.get('success')])
        
        return jsonify({
            'success': True,
            'total_files': len(files),
            'successful': successful,
            'results': results,
            'message': f'✅ {successful}/{len(files)} archivos procesados correctamente'
        })
        
    except Exception as e:
        print(f"ERROR en upload_ea_csv: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'success': False}), 500

@caracteristicas_bp.route('/api/ea/list', methods=['GET'])
def list_eas():
    """Lista todos los EAs cargados"""
    try:
        conn = sqlite3.connect('trading_data.db')
        
        query = '''SELECT 
                   magic_number, 
                   COALESCE(activo, symbol) as activo,
                   COALESCE(direccion, '') as direccion,
                   COALESCE(timeframe, '') as timeframe,
                   COALESCE(caracteristicas, strategy) as caracteristicas,
                   COALESCE(walk_forward, range_config) as walk_forward,
                   COALESCE(fecha_futura, '') as fecha_futura,
                   symbol, 
                   strategy, 
                   range_config, 
                   trade_type, 
                   filename, 
                   upload_date, 
                   total_backtests, 
                   best_params, 
                   notes
                   FROM ea_characteristics
                   ORDER BY upload_date DESC'''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        # Reemplazar NaN con strings vacíos
        df = df.fillna('')
        
        # Mapear tipos de trade a nombres legibles
        def format_trade_type(tt):
            if tt == 'B':
                return 'Buy'
            elif tt == 'S':
                return 'Sell'
            elif tt == 'BS' or tt == 'Buy/Sell':
                return 'Buy/Sell'
            return '-'
        
        df['trade_type_formatted'] = df['trade_type'].apply(format_trade_type)
        
        print(f"📊 Devolviendo {len(df)} EAs")
        if len(df) > 0:
            print(f"   Primer EA - walk_forward: {df.iloc[0]['walk_forward']}, fecha_futura: {df.iloc[0]['fecha_futura']}")
        
        return jsonify(df.to_dict('records'))
        
    except Exception as e:
        print(f"ERROR en list_eas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@caracteristicas_bp.route('/api/ea/backtest-results/<int:magic_number>', methods=['GET'])
def get_backtest_results(magic_number):
    """Obtiene los resultados de backtesting de un EA"""
    try:
        conn = sqlite3.connect('trading_data.db')
        
        query = '''SELECT test_number, net_profit, total_trades, win_rate, 
                   profit_factor, max_drawdown, sharpe_ratio
                   FROM ea_backtest_results
                   WHERE magic_number = ?
                   ORDER BY net_profit DESC'''
        
        df = pd.read_sql_query(query, conn, params=[magic_number])
        conn.close()
        
        if df.empty:
            return jsonify([])
        
        return jsonify(df.to_dict('records'))
        
    except Exception as e:
        print(f"ERROR en get_backtest_results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@caracteristicas_bp.route('/api/ea/delete/<int:magic_number>', methods=['POST'])
def delete_ea(magic_number):
    """Elimina un EA y sus backtests"""
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener nombre del archivo para eliminarlo
        c.execute('SELECT filename FROM ea_characteristics WHERE magic_number = ?', (magic_number,))
        result = c.fetchone()
        
        if result:
            filename = result[0]
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
        
        # Eliminar de base de datos
        c.execute('DELETE FROM ea_backtest_results WHERE magic_number = ?', (magic_number,))
        c.execute('DELETE FROM ea_characteristics WHERE magic_number = ?', (magic_number,))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ EA {magic_number} eliminado correctamente'
        })
        
    except Exception as e:
        print(f"ERROR en delete_ea: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@caracteristicas_bp.route('/api/ea/update-info', methods=['POST'])
def update_ea_info():
    """Actualiza comentario y fecha futura de un EA"""
    try:
        data = request.json
        magic_number = data.get('magic_number')
        notes = data.get('notes', '')
        future_date = data.get('future_date', '')
        
        if not magic_number:
            return jsonify({'error': 'Magic number requerido', 'success': False}), 400
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('''UPDATE ea_characteristics 
                     SET notes = ?, best_params = ? 
                     WHERE magic_number = ?''',
                 (notes, future_date, magic_number))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '✅ Información actualizada correctamente'
        })
        
    except Exception as e:
        print(f"ERROR en update_ea_info: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@caracteristicas_bp.route('/api/ea/info/<int:magic_number>', methods=['GET'])
def get_ea_info(magic_number):
    """Obtiene comentario y fecha futura de un EA"""
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        c.execute('''SELECT notes, best_params 
                     FROM ea_characteristics 
                     WHERE magic_number = ?''', (magic_number,))
        
        result = c.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'notes': '', 'future_date': ''})
        
        return jsonify({
            'notes': result[0] or '',
            'future_date': result[1] or ''
        })
        
    except Exception as e:
        print(f"ERROR en get_ea_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@caracteristicas_bp.route('/api/ea/monthly-analysis/<int:magic_number>', methods=['GET'])
def get_ea_monthly_analysis(magic_number):
    """Obtiene análisis mensual detallado de un EA - TODOS LOS AÑOS"""
    try:
        print(f"\n{'='*60}")
        print(f"📊 Analizando mensualmente EA: {magic_number} (Todos los años)")
        print(f"{'='*60}")
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener información del EA
        c.execute('''SELECT filename FROM ea_characteristics WHERE magic_number = ?''', 
                 (magic_number,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            print(f"❌ EA {magic_number} no encontrado en BD")
            return jsonify({'error': 'EA no encontrado'}), 404
        
        filename = result[0]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        print(f"📁 Archivo: {filename}")
        
        if not os.path.exists(filepath):
            conn.close()
            print(f"❌ Archivo no existe: {filepath}")
            return jsonify({'error': 'Archivo CSV no encontrado'}), 404
        
        # Leer CSV
        print(f"📖 Leyendo CSV...")
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        print(f"   Filas originales: {len(df)}")
        
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        # Limpiar valores
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.replace('"', '')
        
        # Convertir columnas
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        
        if 'Close time' not in df.columns:
            conn.close()
            return jsonify({'error': 'CSV no tiene columna Close time'}), 400
        
        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
        df = df.dropna(subset=['Close time', 'Profit/Loss'])
        
        if df.empty:
            conn.close()
            print(f"⚠️ DataFrame vacío")
            return jsonify([])
        
        df = df.sort_values('Close time')
        
        print(f"   Rango de fechas: {df['Close time'].min()} a {df['Close time'].max()}")
        
        # Mapeo de meses
        month_map = {
            1: 'ENE', 2: 'FEB', 3: 'MAR', 4: 'ABR', 5: 'MAY', 6: 'JUN',
            7: 'JUL', 8: 'AGO', 9: 'SEP', 10: 'OCT', 11: 'NOV', 12: 'DIC'
        }
        
        df['year'] = df['Close time'].dt.year
        df['month_num'] = df['Close time'].dt.month
        df['month_abbr'] = df['month_num'].map(month_map)
        
        # Obtener años únicos
        years = sorted(df['year'].unique(), reverse=True)
        
        print(f"   Años encontrados: {years}")
        
        # Crear resultado con una fila por año
        result = []
        
        for year in years:
            df_year = df[df['year'] == year].copy()
            
            # Calcular RET/DD para el año
            df_year['cumulative'] = df_year['Profit/Loss'].cumsum()
            df_year['running_max'] = df_year['cumulative'].cummax()
            df_year['drawdown'] = df_year['cumulative'] - df_year['running_max']
            max_dd = abs(df_year['drawdown'].min())
            total_profit = df_year['Profit/Loss'].sum()
            ret_dd = (total_profit / max_dd) if max_dd > 0 else 0
            
            # Calcular max consecutive losses
            consecutive_losses = 0
            max_consecutive_loss = 0
            for profit in df_year['Profit/Loss']:
                if profit < 0:
                    consecutive_losses += 1
                    max_consecutive_loss = max(max_consecutive_loss, consecutive_losses)
                else:
                    consecutive_losses = 0
            
            year_row = {
                'year': int(year),
                'magic_number': int(magic_number),
                'ret_dd': round(ret_dd, 2),
                'max_consecutive_loss': max_consecutive_loss
            }
            
            # Agrupar por mes
            monthly = df_year.groupby('month_abbr').agg({
                'Profit/Loss': 'sum',
                'Close time': 'count'
            }).reset_index()
            monthly.columns = ['month_abbr', 'profit', 'trades']
            
            # Añadir datos mensuales
            for _, row in monthly.iterrows():
                month = row['month_abbr']
                month_data = df_year[df_year['month_abbr'] == month]
                
                total_trades = len(month_data)
                winning_trades = len(month_data[month_data['Profit/Loss'] > 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                year_row[month] = {
                    'profit': round(row['profit'], 2),
                    'trades': int(row['trades']),
                    'winning': round(win_rate, 1)
                }
            
            result.append(year_row)
            
            print(f"   {year}: ${total_profit:.2f} | RET/DD: {ret_dd:.2f}")
        
        conn.close()
        
        print(f"\n✅ Análisis mensual completado - {len(result)} años")
        print(f"{'='*60}\n")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"\n❌ ERROR en get_ea_monthly_analysis:")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return jsonify({'error': str(e)}), 500

@caracteristicas_bp.route('/api/ea/drawdown-chart/<int:magic_number>', methods=['GET'])
def get_ea_drawdown_chart(magic_number):
    """Obtiene datos para el gráfico de drawdown de un EA específico"""
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener información del EA
        c.execute('''SELECT filename FROM ea_characteristics WHERE magic_number = ?''', 
                 (magic_number,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'EA no encontrado'}), 404
        
        filename = result[0]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            conn.close()
            return jsonify({'error': 'Archivo CSV no encontrado'}), 404
        
        # Leer CSV
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        # Limpiar valores
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.replace('"', '')
        
        # Convertir columnas
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        
        if 'Close time' not in df.columns:
            conn.close()
            return jsonify({'error': 'CSV no tiene columna Close time'}), 400
        
        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
        df = df.dropna(subset=['Close time', 'Profit/Loss'])
        df = df.sort_values('Close time')
        
        # Agrupar por fecha
        df['date'] = df['Close time'].dt.date
        daily_df = df.groupby('date').agg({
            'Profit/Loss': 'sum'
        }).reset_index()
        
        # Calcular equity y drawdown
        daily_df['equity'] = daily_df['Profit/Loss'].cumsum()
        daily_df['running_max'] = daily_df['equity'].cummax()
        daily_df['drawdown'] = daily_df['equity'] - daily_df['running_max']
        
        # Convertir a formato JSON
        labels = [d.strftime('%Y-%m-%d') for d in daily_df['date']]
        equity_data = daily_df['equity'].round(2).tolist()
        drawdown_data = daily_df['drawdown'].round(2).tolist()
        
        conn.close()
        
        return jsonify({
            'labels': labels,
            'equity': equity_data,
            'drawdown': drawdown_data
        })
        
    except Exception as e:
        print(f"ERROR en get_ea_drawdown_chart: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@caracteristicas_bp.route('/api/ea/trades-detail/<int:magic_number>/<string:month>', methods=['GET'])
def get_ea_trades_detail(magic_number, month):
    """Obtiene el detalle de trades de un EA específico para un mes"""
    try:
        year = request.args.get('year', 'all')
        
        print(f"\n📋 Obteniendo trades - EA: {magic_number}, Mes: {month}, Año: {year}")
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener información del EA
        c.execute('''SELECT filename FROM ea_characteristics WHERE magic_number = ?''', 
                 (magic_number,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'EA no encontrado'}), 404
        
        filename = result[0]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            conn.close()
            return jsonify({'error': 'Archivo CSV no encontrado'}), 404
        
        # Leer CSV
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        # Limpiar valores
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.replace('"', '')
        
        # Convertir columnas
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        
        if 'Close time' not in df.columns:
            conn.close()
            return jsonify({'error': 'CSV no tiene columna Close time'}), 400
        
        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
        df = df.dropna(subset=['Close time', 'Profit/Loss'])
        
        # Filtrar por año si se especifica
        if year != 'all':
            try:
                year_int = int(year)
                df = df[df['Close time'].dt.year == year_int]
            except ValueError:
                pass
        
        # Mapeo de meses
        month_map = {
            'ENE': 1, 'FEB': 2, 'MAR': 3, 'ABR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AGO': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DIC': 12
        }
        
        month_num = month_map.get(month.upper())
        if not month_num:
            conn.close()
            return jsonify({'error': 'Mes inválido'}), 400
        
        # Filtrar por mes
        df = df[df['Close time'].dt.month == month_num]
        
        print(f"   Trades encontrados: {len(df)}")
        
        if df.empty:
            conn.close()
            return jsonify({'trades': [], 'summary': {'total': 0, 'profit': 0, 'win_rate': 0}})
        
        # Ordenar por fecha
        df = df.sort_values('Close time', ascending=False)
        
        # Preparar datos para JSON - MANEJO ROBUSTO DE NaN
        trades = []
        for _, row in df.iterrows():
            try:
                # Función auxiliar para manejar NaN
                def safe_str(value, default=''):
                    if pd.isna(value) or value == 'nan' or value == 'NaN':
                        return default
                    return str(value).strip()
                
                def safe_float(value, default=0.0):
                    try:
                        if pd.isna(value):
                            return default
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                
                trade = {
                    'close_time': row['Close time'].strftime('%Y-%m-%d %H:%M:%S'),
                    'symbol': safe_str(row.get('Symbol', 'N/A'), 'N/A'),
                    'type': safe_str(row.get('Type', 'N/A'), 'N/A'),
                    'volume': safe_float(row.get('Volume', 0), 0.0),
                    'open_price': safe_float(row.get('Open price', 0), 0.0),
                    'close_price': safe_float(row.get('Close price', 0), 0.0),
                    'profit': safe_float(row.get('Profit/Loss', 0), 0.0),
                    'comment': safe_str(row.get('Comment', ''), '')
                }
                
                trades.append(trade)
                
            except Exception as e:
                print(f"   ⚠️ Error procesando trade: {e}")
                continue
        
        # Calcular resumen
        total_trades = len(df)
        total_profit = df['Profit/Loss'].sum()
        winning_trades = len(df[df['Profit/Loss'] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        print(f"   ✅ Trades procesados: {len(trades)}")
        
        conn.close()
        
        return jsonify({
            'trades': trades,
            'summary': {
                'total': total_trades,
                'profit': round(float(total_profit), 2),
                'win_rate': round(float(win_rate), 1)
            }
        })
        
    except Exception as e:
        print(f"❌ ERROR en get_ea_trades_detail: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@caracteristicas_bp.route('/api/ea/detailed-stats/<int:magic_number>', methods=['GET'])
def get_detailed_stats(magic_number):
    """Obtiene estadísticas detalladas de un EA específico"""
    try:
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener información del EA
        c.execute('''SELECT filename FROM ea_characteristics WHERE magic_number = ?''', 
                 (magic_number,))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'EA no encontrado'}), 404
        
        filename = result[0]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            conn.close()
            return jsonify({'error': 'Archivo CSV no encontrado'}), 404
        
        # Leer CSV
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        # Limpiar valores
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.replace('"', '')
        
        # Convertir columnas importantes
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        
        # Convertir Balance si existe
        if 'Balance' in df.columns:
            df['Balance'] = pd.to_numeric(df['Balance'], errors='coerce')
        
        # Parsear fechas
        if 'Close time' in df.columns:
            df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
            df = df.dropna(subset=['Close time'])
            df = df.sort_values('Close time')
        else:
            conn.close()
            return jsonify({'error': 'CSV no tiene columna "Close time"'}), 400
        
        # ================================================================
        # CÁLCULOS BÁSICOS
        # ================================================================
        total_trades = len(df)
        winning_trades = len(df[df['Profit/Loss'] > 0])
        losing_trades = len(df[df['Profit/Loss'] < 0])
        
        net_profit = df['Profit/Loss'].sum()
        gross_profit = df[df['Profit/Loss'] > 0]['Profit/Loss'].sum()
        gross_loss = abs(df[df['Profit/Loss'] < 0]['Profit/Loss'].sum())
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        avg_win = df[df['Profit/Loss'] > 0]['Profit/Loss'].mean() if winning_trades > 0 else 0
        avg_loss = abs(df[df['Profit/Loss'] < 0]['Profit/Loss'].mean()) if losing_trades > 0 else 0
        
        expectancy = ((win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)) if total_trades > 0 else 0
        rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # ================================================================
        # EQUITY CURVE Y DRAWDOWN
        # ================================================================
        df['cumulative'] = df['Profit/Loss'].cumsum()
        df['running_max'] = df['cumulative'].cummax()
        df['drawdown'] = df['cumulative'] - df['running_max']
        
        max_drawdown = df['drawdown'].min()
        max_drawdown_abs = abs(max_drawdown)
        
        # RET/DD
        ret_dd = (net_profit / max_drawdown_abs) if max_drawdown_abs > 0 else 0
        
        # ================================================================
        # SQN - CORREGIDO (R-expectancy como SQX)
        # ================================================================
        avg_loss_for_risk = avg_loss if avg_loss > 0 else 1
        r_expectancy = expectancy / avg_loss_for_risk
        df['R_multiples'] = df['Profit/Loss'] / avg_loss_for_risk
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
        # CAGR - CORREGIDO (Usando Balance real del CSV)
        # ================================================================
        first_date = df['Close time'].min()
        last_date = df['Close time'].max()
        days_diff = (last_date - first_date).days
        total_months = days_diff / 30.44 if days_diff > 0 else 0
        
        if days_diff > 0 and 'Balance' in df.columns:
            initial_balance = df['Balance'].iloc[0]
            final_balance = df['Balance'].iloc[-1]
            
            if initial_balance > 0 and final_balance > 0:
                years = days_diff / 365.25
                cagr = ((final_balance / initial_balance) ** (1 / years) - 1) * 100
            else:
                cagr = 0
        else:
            # Fallback si no hay columna Balance
            capital_required = 100000  # Capital real de la cuenta
            final_capital = capital_required + net_profit
            
            if capital_required > 0 and final_capital > 0:
                cagr = ((final_capital / capital_required) ** (365.25 / days_diff) - 1) * 100
            else:
                cagr = 0
        
        # ================================================================
        # SHARPE RATIO - CORREGIDO (Sin anualizar)
        # ================================================================
        df['date'] = df['Close time'].dt.date
        daily_profit = df.groupby('date')['Profit/Loss'].sum()
        equity_curve = daily_profit.cumsum()
        
        # Calcular Sharpe sin anualizar
        if len(daily_profit) > 1:
            mean_daily = daily_profit.mean()
            std_daily = daily_profit.std(ddof=1)
            
            if std_daily > 0:
                sharpe_ratio = mean_daily / std_daily  # ← SIN ANUALIZAR
            else:
                sharpe_ratio = 0
        else:
            sharpe_ratio = 0
        
        # ================================================================
        # MAX DD POR AÑO - CORREGIDO (Usando Peak real)
        # ================================================================
        df['year'] = df['Close time'].dt.year
        current_year = datetime.now().year

        if current_year in df['year'].values:
            df_year = df[df['year'] == current_year].copy()
            df_year['cumulative_year'] = df_year['Profit/Loss'].cumsum()
            df_year['running_max_year'] = df_year['cumulative_year'].cummax()
            df_year['drawdown_year'] = df_year['cumulative_year'] - df_year['running_max_year']
            
            # Encontrar el DD máximo
            max_dd_idx = df_year['drawdown_year'].idxmin()
            peak = df_year.loc[max_dd_idx, 'running_max_year']
            
            # Si hay Balance, sumar al peak
            if 'Balance' in df.columns:
                initial_balance = df['Balance'].iloc[0]
                peak_total = peak + initial_balance
                trough = df_year.loc[max_dd_idx, 'cumulative_year'] + initial_balance
                max_dd_year = ((peak_total - trough) / peak_total * 100) if peak_total > 0 else 0
            else:
                # Sin Balance, calcular relativo al peak de profit
                max_dd_year_abs = abs(df_year['drawdown_year'].min())
                max_dd_year = (max_dd_year_abs / peak * 100) if peak > 0 else 0
        else:
            max_dd_year = 0
        
        # ================================================================
        # AVG RECOVERY DAYS
        # ================================================================
        recovery_times = []
        in_drawdown = False
        drawdown_start = None
        
        for idx, row in df.iterrows():
            if row['drawdown'] < 0 and not in_drawdown:
                in_drawdown = True
                drawdown_start = row['Close time']
            elif row['drawdown'] == 0 and in_drawdown:
                in_drawdown = False
                if drawdown_start and pd.notna(row['Close time']) and pd.notna(drawdown_start):
                    recovery_days = (row['Close time'] - drawdown_start).days
                    if recovery_days >= 0:
                        recovery_times.append(recovery_days)
        
        avg_recovery_days = sum(recovery_times) / len(recovery_times) if recovery_times else 0
        
        # ================================================================
        # CONSISTENCIA % MESES VERDES
        # ================================================================
        df['year_month'] = df['Close time'].dt.strftime('%Y-%m')
        monthly_profit = df.groupby('year_month')['Profit/Loss'].sum()
        green_months = (monthly_profit > 0).sum()
        total_months_calc = len(monthly_profit)
        consistency_green_months = (green_months / total_months_calc * 100) if total_months_calc > 0 else 0
        
        # ================================================================
        # STAGNATION IN DAYS
        # ================================================================
        max_stagnation_days = 0
        current_peak = equity_curve.iloc[0] if len(equity_curve) > 0 else 0
        last_peak_date = equity_curve.index[0] if len(equity_curve) > 0 else None
        
        for date, equity in equity_curve.items():
            if equity > current_peak:
                if last_peak_date:
                    days_stagnation = (date - last_peak_date).days
                    max_stagnation_days = max(max_stagnation_days, days_stagnation)
                
                current_peak = equity
                last_peak_date = date
        
        if last_peak_date and len(equity_curve) > 0:
            last_date = equity_curve.index[-1]
            current_stagnation = (last_date - last_peak_date).days
            max_stagnation_days = max(max_stagnation_days, current_stagnation)
        
        # ================================================================
        # AVG TRADES PER MONTH
        # ================================================================
        avg_trades_per_month = total_trades / total_months_calc if total_months_calc > 0 else 0
        
        conn.close()
        
        # ================================================================
        # RETORNAR TODOS LOS KPIs
        # ================================================================
        return jsonify({
            'net_profit': round(net_profit, 2),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_dd_year': round(max_dd_year, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'ret_dd': round(ret_dd, 2),
            'sqn': round(sqn, 2),
            'r2_equity': round(r2_equity, 4),
            'cagr': round(cagr, 2),
            'avg_recovery_days': round(avg_recovery_days, 1),
            'consistency_green_months': round(consistency_green_months, 1),
            'rr_ratio': round(rr_ratio, 2),
            'stagnation_days': int(max_stagnation_days),
            'avg_trades_per_month': round(avg_trades_per_month, 1),
            'first_trade_date': first_date.strftime('%Y-%m-%d'),
            'last_trade_date': last_date.strftime('%Y-%m-%d'),
            'total_days': days_diff,
            'total_months': int(total_months)
        })
        
    except Exception as e:
        print(f"ERROR en get_detailed_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@caracteristicas_bp.route('/api/ea/max-dd-year', methods=['GET'])
def get_ea_max_dd_year():
    """Calcula Max DD por año de los backtests de EAs"""
    try:
        year = request.args.get('year', '2025')
        magic_number = request.args.get('magic_number', 'all')
        
        print(f"\n📊 Calculando Max DD Year (EAs):")
        print(f"   Año: {year}")
        print(f"   Magic: {magic_number}")
        
        conn = sqlite3.connect('trading_data.db')
        
        # Query para obtener trades de backtests
        query = '''SELECT filename FROM ea_characteristics WHERE 1=1'''
        params = []
        
        if magic_number != 'all':
            query += ' AND magic_number = ?'
            params.append(int(magic_number))
        
        df_eas = pd.read_sql_query(query, conn, params=params)
        
        if df_eas.empty:
            conn.close()
            return jsonify({'max_dd': 0, 'year': year})
        
        all_trades = []
        
        # Leer CSVs
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
                except Exception as e:
                    print(f"Error leyendo {row['filename']}: {e}")
        
        conn.close()
        
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
        
        print(f"   ✅ Max DD (porcentaje): {max_dd_percent:.2f}%")
        
        return jsonify({
            'max_dd': round(max_dd_percent, 2),
            'year': year
        })
        
    except Exception as e:
        print(f"❌ Error en get_ea_max_dd_year: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'max_dd': 0}), 500    

@caracteristicas_bp.route('/api/ea/max-dd-year-selected', methods=['GET'])
def get_ea_max_dd_year_selected():
    """Calcula Max DD por año de un EA específico"""
    try:
        magic_number = request.args.get('magic_number')
        year = request.args.get('year', str(datetime.now().year))
        
        if not magic_number:
            return jsonify({'error': 'Magic number requerido', 'max_dd': 0}), 400
        
        print(f"\n📊 Calculando Max DD Year para EA {magic_number}, año {year}")
        
        conn = sqlite3.connect('trading_data.db')
        c = conn.cursor()
        
        # Obtener archivo del EA
        c.execute('SELECT filename FROM ea_characteristics WHERE magic_number = ?', 
                 (int(magic_number),))
        result = c.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'EA no encontrado', 'max_dd': 0}), 404
        
        filename = result[0]
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            conn.close()
            return jsonify({'error': 'Archivo no encontrado', 'max_dd': 0}), 404
        
        # Leer CSV
        df = pd.read_csv(filepath, sep=';', encoding='utf-8')
        df.columns = df.columns.str.strip().str.replace('"', '')
        
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip().str.replace('"', '')
        
        df['Profit/Loss'] = pd.to_numeric(df['Profit/Loss'], errors='coerce')
        df['Close time'] = pd.to_datetime(df['Close time'], errors='coerce')
        df = df.dropna(subset=['Close time', 'Profit/Loss'])
        df = df.sort_values('Close time')
        
        # Filtrar por año
        if year != 'all':
            df = df[df['Close time'].dt.year == int(year)]
        
        if df.empty:
            conn.close()
            return jsonify({'max_dd': 0, 'year': year})
        
        # Calcular drawdown
        df['cumulative'] = df['Profit/Loss'].cumsum()
        df['running_max'] = df['cumulative'].cummax()
        df['drawdown'] = df['cumulative'] - df['running_max']
        
        max_dd_abs = abs(df['drawdown'].min())
        
        # Calcular como porcentaje
        capital_inicial = 100000  # Capital real de la cuenta
        max_dd_percent = (max_dd_abs / capital_inicial * 100) if capital_inicial > 0 else 0
        
        conn.close()
        
        print(f"   ✅ Max DD: {max_dd_percent:.2f}%")
        
        return jsonify({
            'max_dd': round(max_dd_percent, 2),
            'year': year
        })
        
    except Exception as e:
        print(f"❌ Error en get_ea_max_dd_year_selected: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'max_dd': 0}), 500    