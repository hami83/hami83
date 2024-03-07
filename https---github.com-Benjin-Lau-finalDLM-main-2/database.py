import sqlite3

def create_db_fromCSMS():
    conn = sqlite3.connect('evse_database.db')
    c = conn.cursor()
    # Create table
    c.execute('''
        CREATE TABLE IF NOT EXISTS evse_data (
            cp_id TEXT,
            evse_max_a DECIMAL(10,5),
            evse_meter DECIMAL(10,5),
            evse_status INTEGER
        )
    ''')

    c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_cp_id ON evse_data(cp_id)') # Create unique index on cp_id
    conn.close() # Close the connection

def connect_db_fromCSMS():
    # Connect to SQLite database
    conn = sqlite3.connect('evse_database.db')
    c = conn.cursor()
    return conn, c

# def create_db_toCSMS():
#     conn = sqlite3.connect('EVSEactual.db')
#     c = conn.cursor()
#     # Create table
#     c.execute('''
#         CREATE TABLE IF NOT EXISTS evse_actual (
#             EVSE TEXT,
#             TIME_10 DECIMAL(10,5)
#         )
#     ''')

#     conn.close() # Close the connection

def connect_db_toCSMS():
    # Connect to SQLite database
    conn = sqlite3.connect('evse_proposed_cp.db')
    c = conn.cursor()
    return conn, c

def create_db_modbus_rtu():
    conn = sqlite3.connect('MeterDataRTU.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS POWER_METER
                        (ID         INTEGER         PRIMARY KEY     AUTOINCREMENT,
                        TIME_NOW    DATETIME        NOT NULL,
                        V           DECIMAL(10,5),
                        A           DECIMAL(10,5),
                        FREQ        DECIMAL(10,5),
                        P           DECIMAL(10,5),
                        Q           DECIMAL(10,5),
                        S           DECIMAL(10,5),
                        PF          DECIMAL(10,5));''')
    conn.close() # Close the connection

def connect_db_modbus_rtu():
    # Connect to SQLite database
    conn = sqlite3.connect('MeterDataRTU.db')
    c = conn.cursor()
    return conn, c

def create_db_fromDLM(num):
    conn = sqlite3.connect('evse_proposed_cp1.db')
    c = conn.cursor()
    # Create table
    c.execute('''
        CREATE TABLE IF NOT EXISTS EVSE_N (
            TIME_NOW DATETIME NOT NULL,
            EVSE_N INTEGER NOT NULL
        )
    ''')
    column = ["CP_ID     INTEGER     NOT NULL",    # No primary key declared
              "TIME_NOW DATETIME    NOT NULL"]
    for i in range(1,num+1):
        column.append(f"TIME_{i} DECIMAL(10,5)")
    EVSEproposed_table = f"CREATE TABLE IF NOT EXISTS DLM_CURRENT ({', '.join(column)})"
    c.execute(EVSEproposed_table)

    conn.close() # Close the connection

def connect_db_fromDLM():
    # Connect to SQLite database
    conn = sqlite3.connect('evse_proposed_cp.db')
    c = conn.cursor()
    return conn, c

def close_db(conn):
    conn.commit() # Commit the transaction
    conn.close() # Close the connection