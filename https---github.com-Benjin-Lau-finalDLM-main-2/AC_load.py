# Import necessary functions
import pyvisa

def AC_load_serial(EVSE_proposed_current):
    """
    This is for serial connection (RS232) to Programmable AC Load
    """
    rm = pyvisa.highlevel.ResourceManager()         # Get resource manager
    instrument_id = ["ASRL4::INSTR"]                # Define the instrument ID (COM PORT)
    instrument_data = {}
    EVSE_proposed_current = EVSE_proposed_current   # e.g., {"LOSc": [5]}
    print("This is EVSE_proposed_current in AC_load control: ", EVSE_proposed_current)
    
    for cp_id, current in EVSE_proposed_current.items():
        index = list(EVSE_proposed_current).index(cp_id)
        id_value = instrument_id[index]
        instrument_data[cp_id] = {"current" : current[-1],
                                  "instrument id" : id_value}
    print("Data: ",instrument_data)   # to check 

    try:
        for cp_id, values in instrument_data.items():
            
            with rm.open_resource(values["instrument id"]) as inst:
                inst.clear()                    # Start by clearing device                
                inst.baud_rate = 57600          # Change baud rate to 57600
                inst.read_termination = '\n'    # Declare termination character

                print(inst.query("*IDN?\n"))
                inst.timeout = 2000
                print(inst.write("LOAD ON\n"))
                inst.timeout = 2000
                print(inst.write("CURR:PEAK:MAX 25\n"))
                inst.timeout = 2000
                print(inst.write(f"CURR {values['current']}\n"))
                inst.timeout = 2000
                print(inst.query("MEAS:CURR?\n"))   
                inst.timeout = 2000
                
                print("_________________________________")
                print("AC Load has successfully been updated!")

    except pyvisa.VisaIOError as e:
        print(f"Error: {e}")
        
    rm.close() # Close the connection

# AC_load_serial()
