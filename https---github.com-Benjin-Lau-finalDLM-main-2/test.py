import sqlite3

def test():
    EVSE_n = 2
    EVSE_dict = {}  # Create an empty dictionary to hold the EVSE objects

    # TESTING ONLY - TO BE REPLACED
    EVSE_1_t_minus_1, EVSE_2_t_minus_1, EVSE_T_t_minus_1 = EVSE_dummy_data()

    # Create the EVSE objects and add them to the dictionary
    for i in range(1, EVSE_n + 1):
        EVSE_name = f"EVSE_{i}"  # Generating the variable name dynamically
        EVSE_Cap_t_minus_1 = locals()[f"EVSE_{i}_t_minus_1"]  # Retrieve the value using locals()
        EVSE_state = 1
        EVSE_dict[EVSE_name] = EVSE_Cap_t_minus_1, EVSE_state

    # Accessing the created EVSE objects
    for EVSE_name, EVSE_Cap_t_minus_1 in EVSE_dict.items():
        print(f"At time t-1, {EVSE_name} is charging at {EVSE_Cap_t_minus_1}A")

    print(EVSE_dict)

    # 1) LIMIT: To calculate Total Max EVSE Capacity in use (n) at time (t)
    for i in range(1, EVSE_n +1):
        EVSE_dict[f'EVSE_{i}']





    for i in range(1, EVSE_n+1):
        print(EVSE_dict[f'EVSE_{i}'])

    EVSE_Cap_max = 32

    return

def EVSE_dummy_data():
        
    # Connect to dummyEVSE.db
    try:
        connect_sql = sqlite3.connect('dummyEVSE.db')
        cursor = connect_sql.cursor()
        connect_sql.execute('''CREATE TABLE IF NOT EXISTS EVSE
        (ID          INTEGER        PRIMARY KEY     AUTOINCREMENT,
        TIME_NOW    DATETIME        NOT NULL,
        EVSE_1      DECIMAL(10,5),
        EVSE_2      DECIMAL(10,5),
        EVSE_T      DECIMAL(10,5));''')

        # Fetch previous EVSE_1 data 
        cursor.execute(f"select * from EVSE")
        record = cursor.fetchone()
        [id, time, EVSE_1_t_minus_1, EVSE_2_t_minus_1, EVSE_T_t_minus_1] = record

        cursor.close()

    except sqlite3.Error as error:
        print("Failed to read data from table...", error)
    
    finally:
        if (connect_sql):
            connect_sql.close()
            print("The Sqlite connection is closed")

    return EVSE_1_t_minus_1, EVSE_2_t_minus_1, EVSE_T_t_minus_1

test()