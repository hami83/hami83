# Import necessary functions
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client.serial import ModbusSerialClient
from database import connect_db_modbus_rtu, close_db
from datetime import datetime
import logging
import time
import itertools as it
import threading

"""

MODBUS RTU (SERIAL) GATEWAY ver. 1.0.1
---
Initial Completion Date: 11 January 2024
Version Update Date: 11 January 2024

Version Updates:
None
---
SUMMARISED INFORMATION

Functions:  modbus_rtu_read                 To read data via Modbus RTU
            unit_adjustment                 To adjust the unit value with reference to Smart Meter User Manual
                                            To remove (i.e., None) Error values
            process_and_store_readings      To store data into created database
            get_latest_reading              To fetch latest readings from database
            main                            To run program
            

Additional Notes:
Many Modbus devices & libraries use 0-based indexing for addresses.
When a register is labeled as 0001 in the documentation, it is accessed as 0 (software implementation). 
However, this is not a universal rule.

"""

# -------------------------------------------------------------------------- #
# PREREQUISITES

# Constants & Configuration -- Socomec Countis M03
rtu_slave_id = 1                            # Default Modbus Address ID (001 in decimal)  
rtu_address_p1_range = range(1-1, 31-1, 6)  # First part of RTU Address Map
rtu_address_p2_range = range(71-1, 79-1, 2) # Second part of RTU Address Map
raw_error_value = 1                         # Modbus Error Code (TBC)
port_number = "COM3"                        # USB Port Number for Laptop

# Meter Description in MODBUS RTU -- Socomec Countis MO03 (0001 to 0079) - 1
rtu_meter_description = [
    "Voltage (V)",                      # 01) 0001
    "Current (A)",                      # 02) 0007
    "Active Power (W)",                 # 03) 0013
    "Apparent Power (VA)",              # 04) 0019
    "Reactive Power (var)",             # 05) 0025
    "Power Factor (PF)",                # 06) 0031
    "Frequency (Hz)",                   # 07) 0071
    "Import Active Energy (kWh)",       # 08) 0073
    "Export Active Energy (kWh)",       # 09) 0075
    "Import Reactive Energy (kvarh)",   # 10) 0077
    "Export Reactive Energy (kvarh)",   # 11) 0079 
]

# -------------------------------------------------------------------------- #
# MODBUS RTU CONNECTION & READINGS

def modbus_rtu_read():
    """ 

    Read Data from Modbus RTU -- Socomec Countis M03 
    ---

    >> DEFAULT VALUES <<
    Modbus Address (ID)             = 001
    Baud Rate (1200/2400/4800/9600) = 2400 bps
    Parity (None/Even/Odd)          = None
    Data Bit                        = 8
    Stop Bit                        = 1
    Format                          = Float (32-bit)

    >> DEBUG-BASED <<
    Byte Order                      = BIG
    Word Order                      = BIG

    """
    
    try:
        meter_readings_rtu = []
        with ModbusSerialClient(port=port_number, baudrate=2400) as client:

            for address in it.chain(rtu_address_p1_range, rtu_address_p2_range):
                read_input = client.read_input_registers(address=address, count=2, slave=rtu_slave_id)
                if not read_input.isError():
                    registers = read_input.registers
                    decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
                    output = decoder.decode_32bit_float()
                    meter_readings_rtu.append(output)
                else:
                    meter_readings_rtu.append(None)  # Handle Error in reading
        return meter_readings_rtu
    finally:
        client.close()  # Close SQLite3 connection

def unit_adjustment():
    """ To adjust the value based on the unit """
    list_meter_reading = modbus_rtu_read()
    raw_value = []
    compiled_value = []

    # Unit Value is based on the relevant Modbus address mapping
    unit_value = {
        "(V)": 1,
        "(A)": 1,
        "(Hz)": 1,
        "(%)": 1,
        "(VA)": 1,
        "(W)": 1,
        "(var)": 1,
        "(PF)": 1,
        "(kWh)": 1,
        "(kvarh)": 1,
    }

    # Process Corrected Meter Values based on Meter Description & Unit Value
    for i, description in enumerate(rtu_meter_description):
        # Find the substring in parentheses (assuming it's always in parentheses)
        start = description.find('(')
        end = description.find(')')

        if start != -1 and end != -1:               # If both parentheses are found
            unit_str = description[start:end + 1]   # Extract the unit string, e.g., '(V)'
            value = unit_value.get(unit_str)        # Get the value from unit_value dictionary
            error_value = raw_error_value/value     # To determine Error

            # Perform division if the value is found
            if value is not None and i < len(list_meter_reading):
                raw_value = list_meter_reading[i]
                meter_value = raw_value / value     # Corrected Meter Value
                if meter_value == error_value:      # Filter out Error values
                    meter_value = None
                compiled_value.append(meter_value)

    return compiled_value                           # List of corrected meter data

def process_and_store_readings(meter_readings_rtu):
    """ Process and store the readings in the database """
    current_timestamp = datetime.utcnow().isoformat()
    building_status = dict(zip(rtu_meter_description, meter_readings_rtu))
    
    # TEMPORARY - TO FIGURE OUT HOW TO AUTOMATICALLY SLOT IN VALUES APPROPRIATELY
    # To extract out specific values
    voltage = building_status["Voltage (V)"]
    current = building_status["Current (A)"]
    freq = building_status["Frequency (Hz)"]
    power = building_status["Active Power (W)"]
    reactive_power = building_status["Reactive Power (var)"]
    app_power = building_status["Apparent Power (VA)"]
    pf = building_status["Power Factor (PF)"]

    conn, c = connect_db_modbus_rtu()
    c = conn.cursor()
    c.execute(f"INSERT INTO POWER_METER \
    (TIME_NOW, V, A, FREQ, P, Q, S, PF)\
        VALUES ('{current_timestamp}', '{voltage}', '{current}', \
        '{freq}', '{power}', '{reactive_power}', '{app_power}', '{pf}' )")
    close_db(conn)

def get_latest_reading(column):
    """ Get the latest reading for a specific column the database. """
    conn, c = connect_db_modbus_rtu()
    c = conn.cursor()
    c.execute(f"select {column} from POWER_METER")
    all_record = c.fetchall()
    length = len(all_record) - 1
    data_t = all_record[length][0]           # data @ time t
    data_t_minus_1 = all_record[length-1][0] # data @ time t-1

    return data_t, data_t_minus_1

def run():
    readings = unit_adjustment()
    process_and_store_readings(readings)
    [result_t, result_t_minus_1] = get_latest_reading('A')

    return result_t, result_t_minus_1

# -------------------------------------------------------------------------- #
# Main Loop for Modbus RTU
    
def main():
    # initialise_db_rtu()

    while True:
        readings = unit_adjustment()
        process_and_store_readings(readings)
        [result_t, result_t_minus_1] = get_latest_reading('A')
        logging.info(f"Current t is {result_t}A, and Current t-1 is {result_t_minus_1}A")
        time.sleep(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

# -------------------------------------------------------------------------- #
# Debug for Byte Order & Word Order combination for Modbus RTU
    
# def debug_read():
#     try:
#         with ModbusSerialClient(port='COM3', baudrate=2400, parity='N', stopbits=1, bytesize=8) as client:
#             read_input = client.read_input_registers(address=0, count=2, slave=rtu_slave_id)
#             if not read_input.isError():
#                 for byteorder in [Endian.BIG, Endian.LITTLE]:
#                     for wordorder in [Endian.BIG, Endian.LITTLE]:
#                         decoder = BinaryPayloadDecoder.fromRegisters(read_input.registers, byteorder=byteorder, wordorder=wordorder)
#                         voltage = decoder.decode_32bit_float()
#                         print(f"Byte Order: {byteorder}, Word Order: {wordorder}, Voltage: {voltage} V")
#                 return voltage
#             else:
#                 print("Error reading voltage")
#                 return None
#     finally:
#         client.close()

# # debug
# def main():
#     initialise_db_rtu()

#     while True:
#         debug_read()
#         time.sleep(1)
