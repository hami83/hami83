# Import necessary functions
import sqlite3
from typing import Dict, List, Tuple
import requests
import logging
import time

from datetime               import datetime, timezone
from pymodbus.constants     import Endian
from pymodbus.payload       import BinaryPayloadDecoder
from pymodbus.client.serial import ModbusSerialClient
from pymodbus.client.tcp    import ModbusTcpClient

# from database import connect_db_modbus_rtu, close_db

"""

MODBUS RTU (SERIAL) & TCP/IP GATEWAY ver. 1.2

---

Initial Completion Date:    18 October 2024
Version Update Date:        21 October 2024

Version Updates:
- (1.2) Combined Modbus RTU & TCP/IP Gateway

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

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants & Configuration -- Digital Energy Meter
# 1) For RTU Configuration
RTU_SLAVE_ID            = 1                     # Default Modbus Address ID (001 in decimal)  
PORT_NUMBER             = "/dev/ttyUSB2"        # USB Port Number for Workstation
# 2) For TCP/IP Configuration
TCP_IP_ADDRESS          = None                  # IP Address for TCP/IP Gateway
TCP_SLAVE_ID            = None                  # Default Modbus Address ID (001 in decimal)
# 3) For Database Configuration
RAW_ERROR_VALUE         = 1                     # Modbus Error Code (TBC)
DB_NAME                 = "modbus_inepro380.db" # Database Name

# -------------------------------------------------------------------------- #
# Modbus RTU (Serial) & TCP/IP Database

def register_address_list():

    """ 
    To generate a list of register addresses based on Inepro 380 Modbus Address Mapping
    
    """

    electrical_parameters = [
        "L1 Voltage (V)",
        "L2 Voltage (V)",
        "L3 Voltage (V)",
        "L1 Current (A)",
        "L2 Current (A)",
        "L3 Current (A)",
        "Total Active Power (kWh)",
        "L1 Active Power (kWh)",
        "L2 Active Power (kWh)",
        "L3 Active Power (kWh)",
    ]

    electrical_address = [
        0x2008, # L1 Voltage
        0x200C, # L2 Voltage
        0x2010, # L3 Voltage
        0x2068, # L1 Current
        0x206C, # L2 Current
        0x2070, # L3 Current
        0x2080, # Total Active Power
        0x2088, # L1 Active Power
        0x208C, # L2 Active Power
        0x2090, # L3 Active Power
    ]

    # Unit Value is based on the relevant Modbus address mapping
    unit_value = {
        "(V)":      1,
        "(A)":      1,
        "(Hz)":     1,
        "(%)":      1,
        "(VA)":     1,
        "(W)":      1,
        "(var)":    1,
        "(PF)":     1,
        "(kWh)":    1,
        "(kvarh)":  1,
    }

    # Datablocks for each electrical parameter (in 16-bit registers)
    datablocks = [
        4, # L1 Voltage - 64-bit
        4, # L2 Voltage - 64-bit
        4, # L3 Voltage - 64-bit
        4, # L1 Current - 64-bit
        4, # L2 Current - 64-bit
        4, # L3 Current - 64-bit
        4, # Total Active Power - 64-bit
        4, # L1 Active Power - 64-bit
        4, # L2 Active Power - 64-bit
        4, # L3 Active Power - 64-bit
    ]

    address_to_datablock = dict(zip(electrical_address, datablocks))

    return electrical_parameters, electrical_address, unit_value, address_to_datablock


# -------------------------------------------------------------------------- #
# MODBUS RTU CONNECTION & READINGS

def modbus_rtu_read(
    electrical_address:     List[int], 
    address_to_datablock:   Dict[int, int],
) -> List:

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
        with ModbusSerialClient(
            port        = PORT_NUMBER, 
            baudrate    = 2400,
        ) as client:

            for address in electrical_address:
                
                datablock_size = address_to_datablock.get(address, None)

                read_input = client.read_input_registers(
                    address = address, 
                    count   = datablock_size, 
                    slave   = RTU_SLAVE_ID,
                )

                if not read_input.isError():
                    output = convert_hex_to_float(read_input, datablock_size)
                    if output is not None:
                        meter_readings_rtu.append(output)
                    else:
                        meter_readings_rtu.append(None) # Handle Error in reading
                else:
                    meter_readings_rtu.append(None)     # Handle Error in reading

        return meter_readings_rtu
    
    except Exception as e:
        logging.error(f"❌ Error in modbus_rtu_read: {e}")
        raise e

    finally:
        client.close()  # Close SQLite3 connection

def modbus_tcp_read(
    electrical_address:     List[int], 
    address_to_datablock:   Dict[int, int],
) -> List:
    try:
        meter_readings_tcp = []
        with ModbusTcpClient(
            host        = TCP_IP_ADDRESS,
        ) as client:

            for address in electrical_address:
                
                datablock_size = address_to_datablock.get(address, None)

                read_input = client.read_holding_registers(
                    address = address, 
                    count   = datablock_size, 
                    slave   = TCP_SLAVE_ID,
                )

                if not read_input.isError():
                    output = read_input.registers
                    meter_readings_tcp.extend(output)
                else:
                    meter_readings_tcp.append(None)     # Handle Error in reading

        return meter_readings_tcp
    
    except Exception as e:
        logging.error(f"❌ Error in modbus_tcp_read: {e}")
        raise e

    finally:
        client.close()  # Close SQLite3 connection

def convert_hex_to_float(
    hex_value:      object,
    datablock_size: int,
) -> Tuple[float, None, None]:
    
    """ 
    Convert Hexadecimal value to Float 

    """

    try:
        if not hex_value.isError():
            registers   = hex_value.registers
            decoder     = BinaryPayloadDecoder.fromRegisters(
                registers   = registers, 
                byteorder   = Endian.BIG, 
                wordorder   = Endian.BIG,
            )
            if datablock_size == 4:
                output      = decoder.decode_64bit_float()
            if datablock_size == 2:
                output      = decoder.decode_32bit_float()
            return output
        else:
            logging.error("❌ Error in reading registers")
            return (None, None)
        
    except Exception as e:
        logging.error(f"❌ Error in convert_hex_to_float: {e}")
        raise e

def unit_adjustment(
    electrical_parameters:  List[str],
    unit_value:             Dict[str, int], 
    electrical_address:     List[int],
    address_to_datablock:   Dict[int, int],
) -> List[float] | None:

    """ To adjust the value based on the unit """
    try:

        list_meter_reading  = process_list_meter_reading(electrical_address, address_to_datablock)
        raw_value           = []
        compiled_value      = []

        # Process Corrected Meter Values based on Meter Description & Unit Value
        for i, description in enumerate(electrical_parameters):
            # Find the substring in parentheses (assuming it's always in parentheses)
            start   = description.find('(')
            end     = description.find(')')

            if start != -1 and end != -1:                   # If both parentheses are found
                unit_str    = description[start:end + 1]    # Extract the unit string, e.g., '(V)'
                value       = unit_value.get(unit_str)      # Get the value from unit_value dictionary
                error_value = RAW_ERROR_VALUE / value       # To determine Error

                # Perform division if the value is found
                if value is not None and i < len(list_meter_reading):
                    raw_value   = list_meter_reading[i]
                    meter_value = raw_value / value         # Corrected Meter Value
                    if meter_value == error_value:          # Filter out Error values
                        meter_value = None
                    compiled_value.append(meter_value)

        return compiled_value                               # List of corrected meter data

    except Exception as e:
        logging.error(f"❌ Error in unit_adjustment: {e}")
        raise e

def process_list_meter_reading(
    electrical_address:     List[int],
    address_to_datablock:   Dict[int, int],
):
    """ To list meter readings """
    if TCP_IP_ADDRESS is not None:
        list_meter_reading  = modbus_tcp_read(electrical_address, address_to_datablock)
        return list_meter_reading
    
    elif RTU_SLAVE_ID is not None:
        list_meter_reading  = modbus_rtu_read(electrical_address, address_to_datablock)
        return list_meter_reading
    
    else:
        logging.error("❌ Error in Modbus Equipment Configuration")
        return []

def main():
    """ To run the program """
    while True:

        initialise_modbus_database()

        (electrical_parameters, 
         electrical_address, 
         unit_value, 
         address_to_datablock) = register_address_list()
        
        values = unit_adjustment(
            electrical_parameters   = electrical_parameters, 
            unit_value              = unit_value, 
            electrical_address      = electrical_address, 
            address_to_datablock    = address_to_datablock)
        logging.info(f"Values: {values}")
        logging.info(f"Timestamp: {datetime.now(timezone.utc)}")

        process_and_store_readings(values)

        try:
            resp = requests.post(
                "https://mssmartcharging.energyon-csms.com/lora/power_update", 
                json = {
                    "application_id":   "777", 
                    "voltage":          values[0], 
                    "current":          values[1], 
                    "power":            values[2],
                },
            )

            logging.info(f"Response: {resp}")
        
        except Exception as e:
            logging.error(f"Error: {e}")

        time.sleep(1)


if __name__ == "__main__":
    main()

# -------------------------------------------------------------------------- #
# Modbus RTU (Serial) & TCP/IP Database

# To adjust according to register_address_list
def initialise_modbus_database():
    """ Initialise the database for Modbus TCP """
    
    with sqlite3.connect(DB_NAME) as conn:        
        conn.execute('''CREATE TABLE IF NOT EXISTS POWER_METER 
                        (ID                 INTEGER         PRIMARY KEY     AUTOINCREMENT,
                        Time_Now            DATETIME        NOT NULL,
                        L1_Voltage          DECIMAL(10,5),
                        L2_Voltage          DECIMAL(10,5),
                        L3_Voltage          DECIMAL(10,5),
                        L1_Current          DECIMAL(10,5),
                        L2_Current          DECIMAL(10,5),
                        L3_Current          DECIMAL(10,5),
                        Total_Active_Power  DECIMAL(10,5),
                        L1_Active_Power     DECIMAL(10,5),
                        L2_Active_Power     DECIMAL(10,5),
                        L3_Active_Power     DECIMAL(10,5),
                     );''')
        conn.commit()

def process_and_store_readings(values):
    """Store the meter readings into the SQLite database."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO POWER_METER 
                                (Time_Now, 
                                L1_Voltage, 
                                L2_Voltage, 
                                L3_Voltage, 
                                L1_Current, 
                                L2_Current, 
                                L3_Current, 
                                Total_Active_Power, 
                                L1_Active_Power, 
                                L2_Active_Power, 
                                L3_Active_Power) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                           [datetime.now()] + values)
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"❌ Error in process_and_store_readings: {e}")
