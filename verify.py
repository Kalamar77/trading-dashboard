import sqlite3

def extract_timeframe_from_comment(comment):
    if not comment or not isinstance(comment, str):
        return None
    
    comment_upper = str(comment).upper()
    
    # Lista de patrones en orden de prioridad (más específicos primero)
    timeframe_patterns = [
        ('H12', 'H12'), ('12H', 'H12'),
        ('H8', 'H8'), ('8H', 'H8'),
        ('H6', 'H6'), ('6H', 'H6'),
        ('H4', 'H4'), ('4H', 'H4'),
        ('H2', 'H2'), ('2H', 'H2'),
        ('H1', 'H1'), ('1H', 'H1'),
        ('M30', 'M30'), ('30M', 'M30'),
        ('M15', 'M15'), ('15M', 'M15'),
        ('M5', 'M5'), ('5M', 'M5'),
        ('M1', 'M1'), ('1M', 'M1'),
        ('D1', 'D1'), ('1D', 'D1'),
        ('W1', 'W1'),
        ('MN', 'MN'),
    ]
    
    for pattern, standard in timeframe_patterns:
        if pattern in comment_upper:
            return standard
    
    return None

print("=" * 80)
print("ACTUALIZANDO TODOS LOS TIMEFRAMES")
print("=" * 80)

conn = sqlite3.connect('trading_data.db')
c = conn.cursor()

# Obtener TODOS los trades
c.execute("SELECT id, comment FROM trades")
all_trades = c.fetchall()

print(f"\n📊 Total trades: {len(all_trades)}")

updated = 0
examples = []

for trade_id, comment in all_trades:
    timeframe = extract_timeframe_from_comment(comment)
    
    if timeframe:
        c.execute('UPDATE trades SET timeframe = ? WHERE id = ?', (timeframe, trade_id))
        updated += 1
        
        if len(examples) < 10:
            examples.append(f"  ✅ ID {trade_id}: {comment[:50]}... → {timeframe}")

conn.commit()

print(f"\n✅ Trades actualizados: {updated}")
print(f"\nEjemplos:")
for ex in examples:
    print(ex)

# Mostrar estadísticas
c.execute('SELECT timeframe, COUNT(*) as count FROM trades GROUP BY timeframe ORDER BY count DESC')
stats = c.fetchall()

print(f"\n" + "=" * 80)
print("ESTADÍSTICAS FINALES:")
print("=" * 80)
for timeframe, count in stats:
    print(f"  {timeframe:10} → {count:5} trades")

conn.close()

input("\nPresiona Enter para cerrar...")