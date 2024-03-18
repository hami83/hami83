# Import necessary functions
import time
import modbus_rtu
# import modbus_tcp
import sqlite3
import math                     # round down values to 1 decimal place
import logging
from exportData import post_api
from database import close_db, connect_db_fromDLM
from AC_load import AC_load_serial
import requests
import pandas as pd
from copy import deepcopy

"""
---------------------------------------------------------------------------------------------------------------------------
DYNAMIC LOAD MANAGEMENT (DLM) ver 1.1.1
---------------------------------------------------------------------------------------------------------------------------
Initial Completion Date: 11 January 2024
Version Update Date: 15 March 2024

Version Updates:
---------------------------------------------------------------------------------------------------------------------------
- 18 March 2023:    Updated algorithm (SCENARIO 3)
                    To take into consideration max. rated EV charging current
- 15 March 2024:    Updated algorithm (SCENARIO 3)
                    To take into consideration 6A minimum permissible EV charging current
- 17 January 2024:  Added threshold_gradient() - temporarily hard-coded
                    Amended evse_proposed_cp for database update based on cp_id
                    Deleted load_total_evse_count() & get_total_load()
- 11 January 2024:  Initial Version
                    
---------------------------------------------------------------------------------------------------------------------------
SUMMARISED INFORMATION
---------------------------------------------------------------------------------------------------------------------------
Functions:  1) __init__                 To set initial values
            2) get_total_load           To get onsite total load from modbus tcp or rtu
            3) threshold_gradient       To calculate threshold gradient in triggering DLM based of gradient of total load
            4) calculate_gradient       To calculate gradient of total load (time t - time t-1)
            5) dlm_threshold            To determine conditions in the triggering or releasing of DLM & Charging Profile Change
            6) perform_dlm              To perform DLM & determine new Charging Profile
            7) evse_actual_cp           To read actual values from EVSE database (cp_id, evse_max_a, evse_meter, evse_status)
            8) evse_proposed_cp         To load proposed Charging Profile to EVSE proposed database (CP_ID, TIME_10)

---------------------------------------------------------------------------------------------------------------------------
DEFINITIONS
---------------------------------------------------------------------------------------------------------------------------
VARIABLE NAME       DEFINITION                                              UNIT            DATATYPE
>> Fixed Variables <<
time_interval       Time interval between each iteration                    seconds         int
site_capacity       Maximum site capacity                                   amperes         float
timeslots           Number of timeslots to store in database                -               integer
cp_proposed_db      EVSE proposed database name                             -               string
cp_actual_db        EVSE actual database name                               -               string
EVSE_n_max          Maximum current rating for each EVSE                    amperes         string

>> Thresholds <<
trigger_percent     Percentage of site capacity to trigger DLM              percentage      float
release_percent     Percentage of site capacity to release DLM              percentage      float
trigger_threshold   Trigger threshold for DLM activation                    amperes         float
release_threshold   Release threshold for DLM deactivation                  amperes         float
threshold_gradient  Threshold gradient to trigger Charging Profile change   amperes/second  float

>> Currents <<
C_CP_t              Available charging capacity, which includes             amperes         float
                    1) Used EVSE current
                    2) Unused current based off trigger threshold
C_CP_t_minus_1      Available charging capacity at time t-1                 amperes         float
EVSE_T_t_minus_1    Total EVSE current = C_CP_t_minus_1 or 
---------------------------------------------------------------------------------------------------------------------------
"""

class EVSEManager:
    # (START/8) PREREQUISITES
    def __init__(self):
        # SET GRADIENT THRESHOLD
        self.time_interval = 1          # Assuming a 1-second resolution, adjust as needed
        self.site_capacity = 20         # Max. Site Capacity in A (ampere)
        self.dlm_active = False         # Flag to track DLM activation
        self.C_CP_t_minus_1 = 0         # Default to prevent errors

        # THRESHOLDS FOR TRIGGERING DLM
        self.trigger_percent = 0.75
        self.release_percent = 0.4
        self.trigger_threshold = self.trigger_percent * self.site_capacity     # 0.75*20 = 15A
        self.release_threshold = self.release_percent * self.site_capacity     # 0.40*20 = 8A

        # DATABASE & TABLE CREATION with constructed COLUMN DEFINITIONS
        self.timeslots = 10
        self.cp_proposed_db = "evse_proposed_cp.db"
        self.cp_actual_db = "evse_database.db"
        self.column_definitions = ["CP_ID     INTEGER     NOT NULL",    # No primary key declared
                                   "TIME_NOW DATETIME    NOT NULL"]     # Sqlite3 will create ROWID as internal primary key
        for i in range(1, self.timeslots+1):                            # Each row represents current per iteration
            self.column_definitions.append(f"TIME_{i} DECIMAL(10,5)")
        self.EVSEproposed_table = f"CREATE TABLE IF NOT EXISTS DLM_CURRENT ({', '.join(self.column_definitions)})" 

        # TO GET MAX. CURRENT RATING FOR EACH EVSE
        self.EVSE_n_max = {}                                    # Create dictionary to store EVSE max current rating
        for cp_id, evse in self.evse_actual_cp().items():         
            self.EVSE_n_max[cp_id] = float(evse['evse_max_a'])  # Max. Current Rating for each EVSE (based off evse_database)

    # (2/8) TO GET TOTAL LOAD (AMPERES) FROM BUILDING MAIN METER (via MODBUS)
    def get_total_load(self):
        [total_load_t, total_load_t_minus_1] = modbus_rtu.run() # From Modbus RTU gateway
        return  total_load_t, total_load_t_minus_1

    ################################################################################
    # -- DYNAMIC LOAD MANAGEMENT
    ################################################################################

    # (3/8) TO DYNAMICALLY CALCULATE GRADIENT THRESHOLD (WORK IN PROGRESS!!)
    def threshold_gradient(self):
        # Function to intelligently select appropriate threshold gradient
        threshold_gradient = 1  # Temporary

        return threshold_gradient
    
    # (4/8) TO CALCULATE GRADIENT OF TOTAL_LOAD &
    #       To DETERMINE WHEN TO TRIGGER CHARGING PROFILE UPDATE
    def calculate_gradient(self, total_load_t, total_load_t_minus_1):
        return (total_load_t - total_load_t_minus_1) / self.time_interval

    # (5/8) TO TRIGGER-RELEASE (DLM) BASED ON THRESHOLD
    def dlm_threshold(self, No_of_EVSEs_in_use):
        """ 
        SUMMARY OF DLM THRESHOLD

        To determine if Charging Profile is calulated using:
        1) Smart Charging @ Cloud
        2) DLM @ Edge
        Based on gradient of Total Load (t) -- i.e., def calculate_gradient

        Contains:
        - Trigger requirements for DLM Activation
        - Trigger requirements for DLM Deactivation
        - Trigger requirements for the CHANGE in Charging Profile

        No_of_EVSEs_in_use is in reference to the number of EVSEs (in use) in evse_database.db

        """

        # PREREQUISITES for TRIGGER-RELEASE
        threshold_gradient = self.threshold_gradient()
        cp_change = False    
        
        print("Start")   
        print(f"dlm_active:{self.dlm_active}")                                   # [Flag] To track Charging Profile change

        # TO GET TOTAL LOAD DATA @ TIME T & T-1
        [total_load_t, total_load_t_minus_1] = self.get_total_load()
        print("____________________________________")
        print(f"MAIN METER DATA: total load @ time t = {total_load_t}A")
        print(f"MAIN METER DATA: total load @ time t-1 = {total_load_t_minus_1}A")
        print(f"DLM trigger threshold is {self.trigger_threshold}A & release threshold is {self.release_threshold}A")

        # print(f"Meter value from CSMS is:{response}")
            
        # [CONDITION]   Is Total Load (t) >= Trigger Threshold? [FLAG]
        # [ANSWER]      {YES} ACTIVATE DLM!
        if self.dlm_active == False:
            if total_load_t >= self.trigger_threshold:
                self.dlm_active = True
                print("Inside here")   
                print(f"dlm_active:{self.dlm_active}") 
                print(f"DLM Triggered & Now Active! Total Load: {total_load_t} A")
                
        # [ANSWER]      {NO} DLM DOES NOT START...
            else:
                print(f"DLM is Inactive... Smart Charging @ Cloud... Total Load: {total_load_t} A")

        # [CONDITION]   Is DLM is CURRENTLY ACTIVE? [FLAG]
        # [ANSWER]      {YES} Proceed to CHECK GRADIENT
        if self.dlm_active == True:
            total_load_gradient = self.calculate_gradient(total_load_t, total_load_t_minus_1)  # Import gradient

            # [CONDITION]   Is TOTAL LOAD >= RELEASE threshold?
            # [ANSWER]      {YES} DLM continues to be ACTIVE until total_load_t falls below release_threshold
            if total_load_t >= self.release_threshold:
                print(f"Set Gradient Threshold is {threshold_gradient}. Actual Gradient from total load (t-1) to total load (t) is {total_load_gradient}.")

                ###########################################################################
                # TRIGGER CHARGING PROFILE CHANGE!
                ###########################################################################

                # [CONDITION]   Is total_load_gradient >= threshold_gradient 
                #               OR <= -threshold_gradient 
                #               OR total_load_t > trigger_threshold (> 12A)?
                # [ANSWER]      {YES} To TRIGGER CHARGING PROFILE CHANGE
                if (total_load_gradient >= threshold_gradient) or (total_load_gradient <= -threshold_gradient) or (total_load_t > self.trigger_threshold):
                    cp_change = True
                    if total_load_gradient >= threshold_gradient:
                        print(f"Change in Charging Profile Required due to Steep Increase in Gradient by {total_load_gradient-threshold_gradient}!")
                    elif total_load_gradient <= -threshold_gradient:
                        print(f"Change in Charging Profile Required due to Steep Decrease in Gradient by {total_load_gradient-threshold_gradient}!")
                    else:
                        print(f"!!! Change in Charging Profile Required due to total load exceeding {self.trigger_percent*100}% of maximum site capacity!!!")
                    # TO TRIGGER PERFORM CHARGING PROFILE CHANGE
                    print("*****************************************************")
                    self.perform_dlm(total_load_t, self.site_capacity, self.C_CP_t_minus_1) 
                
                # ANSWER: NO
                else:
                    print("Charging Profile Change is NOT Required... BUT DLM is still active!")
                    cp_change = False   # Deactivate Charging Profile change
            # 
            else:
                print(f"DLM is no longer active as the Total Load is {total_load_t}A. Commence Smart Charging.")
                self.dlm_active = False # Deactivate DLM
        # [ANSWER] {NO} Iterate
        else:
            pass

    # (6/8) TO PERFORM DLM WHEN GRADIENT MEETS THRESHOLD
    def perform_dlm(self, total_load_t, site_capacity, C_CP_t_minus_1):
        
        # PREREQUISITES for DLM
        EVSE_proposed_rates = {}    # Empty dictionary to hold calculated charging rates for EVSEs
        EVSE_proposed_current = {}  # Empty dictionary to hold calculated charging capacity (current) for EVSEs @ time t
        EVSE_Max_t = {}             # Empty dictionary to hold max. charging current based on EVSE specs
        EV_state_t = {}             # Empty dictionary to hold state of EVSE (Fully Charged = 1, Otherwise = 0)
        EVSE_T_t_minus_1 = 0        # Initialise
        print("DLM is still active... Tabulating if Charging Profile change/update is required...")

        # Calculate Available Site Charging Capacity at time t
        EVSE_T_t_minus_1 = round(sum(float(evse['evse_meter']) for cp_id, evse in self.evse_actual_cp().items()), 1)
        C_CP_t_minus_1 = min(EVSE_T_t_minus_1, total_load_t)
        C_CP_t = min(C_CP_t_minus_1, total_load_t) + (self.trigger_percent * site_capacity - total_load_t)
        print(f"COMPARE: Total_Load_t is {total_load_t}, whereas charging limit of {self.trigger_percent*100}% maximum site capacity is {site_capacity*self.trigger_percent}A.")
        print(f"AVAILABLE CHARGING CAPACITY: C_CP_t is {C_CP_t}A, whereas C_CP_t_minus_1 is {C_CP_t_minus_1}A")
        print("*****************************************************")

        """
        There are 4 (four) Scenarios for DLM performance.

        Scenario 1: When site total load exceeds maximum site capacity,
                    Result: Emergency STOP.
        Scenario 2: When available EVSE Charging Capacity @ time t (C_CP_t) == time t-1 (C_CP_t_minus_1),
                    Result: Charging Profile remains unchanged.
        Scenario 3: When available EVSE Charging Capacity (C_CP_t) is above 0,
                    Result: Calculate new PROPOSED Charging Profile,
                            Take reference from previous ACTUAL Charging Profile.
        Scenario 4: When available EVSE Charging Capacity (C_CP_t) is equal or less than 0,
                    Result: Set all EVSEs to 0,
                            Available EVSE Charging Capacity (C_CP_t) = 0.

        THE FOLLOWING FUNCTION(S) CHANGES THE C_CP_t (available charging capacity) VALUE!
        """

        # SCENARIO 1: Is total_load_t >= site_capacity?
        # YES: EMERGENCY STOP! All proposed charging current shall be 0
        if total_load_t >= site_capacity:

            # Proposed EVSE current = 0 & Available Site Charging Capacity @ time t, C_CP_t = 0

            # Create a dictionary containing {cp_id: proposed_current}
            for cp_id, evse in self.evse_actual_cp().items():
                EVSE_proposed_current[cp_id] = [0]
            C_CP_t = sum(sum(EVSE_proposed_current[cp_id]) for cp_id in EVSE_proposed_current)
        
            # Flag of description
            print(f"RESULT: Stopped Charging! Charging Profile: All EVSE values are {C_CP_t}A!")
            if total_load_t > site_capacity:
                print(f"EVSEs stopped charging as total load (t), {total_load_t}A, exceeds maximum site capacity, {site_capacity}A!")
            else:
                print(f"EVSEs stopped charging as total load (t) hits maximum site capacity of {site_capacity}A!")

            self.check_for_updates(EVSE_proposed_current)

            # Update EVSEproposed db with new Charging Current values @ time t
            self.evse_proposed_cp(EVSE_proposed_current)

            return EVSE_proposed_current
        
        # SCENARIO 2: Is C_CP_t = C_CP_t_minus_1?
        # YES: Charging Profile remains Unchanged
        elif C_CP_t == C_CP_t_minus_1:
            print("RESULT: Charging Profile Remains Unchanged!")
            print(f"CP Remains unchanged as C_CP_t is {C_CP_t}A, whereas C_CP_t_minus_1 is {C_CP_t_minus_1}A")
            C_CP_t_minus_1 = C_CP_t   # Updated previous C_CP_t with new C_CP_t

        # NO: Go to ANOTHER Condition
        # SCENARIO 3: Is C_CP_t > 0?
        elif C_CP_t > 0:

            #############################################################################
            # Conduct EV Charging Control / Change in Charging Profile (CP)
            #############################################################################

            """
            ---------------------------------------------------------------------------------------------------------------------------
            FUNCTIONS & VARIABLES DEFINITION
            ---------------------------------------------------------------------------------------------------------------------------
            EV_state_t              Status of EVSEs (Fully Charged/Not Charging (fault) = 1, Otherwise = 0)
            EVSE_Max_t              Max. Charging Current for each EVSE
            EVSE_Max_Total_t        Total Max. Charging Current for all EVSEs in USE at time t
            EVSE_proposed_rates     Proposed Charging Rate (%) for each EVSE
            EVSE_proposed_current   Proposed Charging Current (A) for each EVSE
            EVSE_to_adjust          Charging Profile of EVSEs to adjust based off unused current

            C_CP_t_minus_1          Actual EVSE current values at time t-1 based off EVSE database
            current_pool            Difference between proposed current and max. rated current when proposed > max. rated
            min_cp_id               CP ID with the smallest proposed current value (ignoring 0)
            min_evse                Smallest proposed current value (ignoring 0)

            unused_current          Unused current for redistribution after distributing available charging current
            fixed_unused_current    Fixed copy as reference for unused current for redistribution after distributing available charging current
            unused_current_exist    This is True when unused current is more than zero            
            ---------------------------------------------------------------------------------------------------------------------------
            """
            print(f"Charging Profile shall be Updated based on DLM!")

            # RETRIEVE: EVSE actual values @ time t & Total Max
            C_CP_t_minus_1 = round(sum(float(evse['evse_meter']) for cp_id, evse in self.evse_actual_cp().items()), 1)

            # DETERMINE:    No. of EVSEs (EV_state_i: Fully Charged / Not Charging (Fault) = 1, Not Fully Charged = 0)
            for cp_id, evse in self.evse_actual_cp().items():
                EV_state_t[cp_id] = int(evse['evse_status'])    # Create a dictionary containing {cp_id: evse_status}

            # INITIALISATION
            EVSE_Max_Total_t = 0    # Summation of Max. Rated Current of EVSEs in use at time t
            unused_current = 0      # Unused current for redistribution
            EVSE_to_adjust = []     # List of EVSEs for current adjustment

            # SUM: Calculate POTENTIAL Total Max EVSE Capacity in use (n) @ time t
            EVSE_Max_t = {key: self.EVSE_n_max[key] * (1 - EV_state_t[key]) for key in self.EVSE_n_max if key in EV_state_t}
            EVSE_Max_Total_t = sum(EVSE_Max_t.values()) # TIP: Value of EVSE_Max_Total_t changes as EVSE_n changes

            # REPLACE:      EVSE values at time t-1 with new values at time t
            # CALCULATE:    Charging Rate of EACH EVSE in use at time t
            #               Charging Capacity for EACH EVSE in use at time t
            print("Proposed Charging Rates & Charging Capacities of each EVSEs (based on DLM) shall be calculated!")
            for cp_id, evse in self.evse_actual_cp().items():
                if EVSE_Max_Total_t != 0:
                    EVSE_proposed_rates[cp_id] = ((EVSE_Max_t[cp_id] * (1 - EV_state_t[cp_id]) / EVSE_Max_Total_t))
                    EVSE_proposed_current[cp_id] = [math.floor((EVSE_proposed_rates[cp_id] * C_CP_t) * 10) / 10]
                    # If proposed EVSE current is more than max. rated EVSE current, use max. rated EVSE current instead
                    if EVSE_proposed_current[cp_id][0] > self.EVSE_n_max[cp_id]:
                        current_pool = EVSE_proposed_current[cp_id][0] - self.EVSE_n_max[cp_id]
                        unused_current += current_pool
                        EVSE_proposed_current[cp_id] = [self.EVSE_n_max[cp_id]]
                else:
                    print(f"NOTICE: No EVSE in use or all EVSEs fully charged @ time t")
            print("*****************************************************")
            print(f"Distributed Charging Rates to each EVSE: ", EVSE_proposed_rates)

            # FLAG INITIALISATION:  Unused current availability (Boolean)
            unused_current_exist = unused_current > 0

            # CALCULATE:    Potential unused current & sort out to adjustable EVSE list
            if any(0 < current[0] < 6 for current in EVSE_proposed_current.values()) or unused_current_exist:

                # CHECK & RECALCULATE: If the proposed current is less than the minimal current for EVSE charging
                EVSE_proposed_fixed = deepcopy(EVSE_proposed_current)   # Storage reference of previously calculated proposed current values

                # CALCULATE:    Total weighted value for EVSE proposed current
                total_weighted_value = sum([EVSE_proposed_fixed[cp_id][0] for cp_id in EVSE_proposed_fixed])

                # SORT: To determine a list of EVSEs to be adjusted
                for cp_id, evse in EVSE_proposed_current.items():
                    # DETERMINE:    Only cp_ids with proposed current < max. rated current is added to adjustable list
                    # OTHERWISE:    Ignore cp_ids (not to be adjusted at all)
                    if EVSE_proposed_current[cp_id][0] < self.EVSE_n_max[cp_id]:    
                        if 0 < evse[0] < 6:
                            unused_current += evse[0]
                            EVSE_to_adjust.append(cp_id)
                        elif evse[0] >= 6:
                            EVSE_to_adjust.append(cp_id)

                fixed_unused_current = unused_current

            # CONDITION:    As long as there is Unused Current leftover
            #               OR any of EVSE Proposed Current in each EVSE (cp_id) is between 0 and 6
            while unused_current_exist or any(0 < current[0] < 6 for current in EVSE_proposed_current.values()):
                for cp_id, evse in EVSE_proposed_current.items():

                    # Only applied to EVSEs which are to be adjusted (ignore EVSEs which are 0A)
                    # EVSEs to be adjusted shall pop one at a time until While condition is False
                    if cp_id in EVSE_to_adjust:
                        
                        # CALCULATE:    Add potentially Unused Current to Proposed Current
                        add_on_current = (EVSE_proposed_fixed[cp_id][0] / total_weighted_value) * fixed_unused_current
                        if EVSE_proposed_current[cp_id][0] < 6 and EVSE_proposed_current[cp_id][0] != 0:
                            EVSE_proposed_current[cp_id] = [0]              # EVSEs used in unused_current shall be 0 
                        EVSE_proposed_current[cp_id][0] += add_on_current   # Add weighted leftover current to proposed current for cp_id
                        unused_current -= add_on_current                    # Removed added-on current from unused_current pool

                    # NO:   It means that EVSE is either not in use, or has too low of a current proposed to be used
                    else:
                        EVSE_proposed_current[cp_id][0] = 0
                
                # print("Updated Proposed EVSE Current: ", EVSE_proposed_current)
      
                # CONDITION:    After calculating new Proposed Current in above, check if it fits criteria
                #               If it doesn't, remove cp_id from EVSE_to_adjust, and While-loop again
                if any(0 < current[0] < 6 for current in EVSE_proposed_current.values()):
                    unused_current = fixed_unused_current               # Reset unused current to initial unused current value
                    EVSE_proposed_current = deepcopy(EVSE_proposed_fixed)   # EVSE proposed current shall reset to initial proposed values

                    # Identifies cp_id with the smallest evse current in adjutable EVSE list for removal
                    min_cp_id = None                                    # Initialised min. cp_id with None
                    min_evse = float('inf')                             # Initialise min. evse current with a very large number

                    for evse in EVSE_to_adjust:
                        # Check cp_id in EVSE_proposed_current, and smallest number shall be identified
                        if evse in EVSE_proposed_current and EVSE_proposed_current[evse][0] < min_evse:
                            min_cp_id = evse                            # Identify smallest cp_id
                            min_evse = EVSE_proposed_current[evse][0]   # Identify smallest evse current
                    
                    if min_cp_id is not None:
                        EVSE_to_adjust.remove(min_cp_id)                # Remove smallest cp_id from adjustable EVSE list

                    # CALCULATE:    New total weighted value in adjustable EVSE list
                    total_weighted_value = sum([EVSE_proposed_fixed[cp_id][0] for cp_id in EVSE_to_adjust])
                else:
                    unused_current_exist = False

                # print("Is there any unused current?: ", unused_current)
                # print("new total weight: ", total_weighted_value)
                # print("To adjust: ",EVSE_to_adjust)

            for cp_id in EVSE_proposed_current:
                EVSE_proposed_current[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 10) / 10]

            print(f"Distributed Charging Capacities to each EVSE: ", EVSE_proposed_current)
            print("*****************************************************")
            
            self.check_for_updates(EVSE_proposed_current)
            self.evse_proposed_cp(EVSE_proposed_current)    # Update EVSEproposed db with new Charging Current values @ time t
            # EVSE_T_proposed_current = sum(EVSE_proposed_current[cp_id][0] for cp_id in EVSE_proposed_current) # Total Proposed EVSE Charging Current

            return EVSE_proposed_current
        
        # SCENARIO 4: Available EVSE Charging Capacity (C_CP_t) <= 0
        else:
            print("CP RESULT: Stopped Charging!")
            print(f"EVSEs stop charging as C_CP_t is {C_CP_t}A, whereas C_CP_t_minus_1 is {C_CP_t_minus_1}A")
            # raise Exception(DESCRIPTION_CP_stop)

            # Proposed EVSE current = 0 & Available Site Charging Capacity @ time t, C_CP_t = 0
            for cp_id, evse in self.evse_actual_cp().items():
                EVSE_proposed_current[cp_id] = [0]
            C_CP_t = sum(sum(EVSE_proposed_current[cp_id]) for cp_id in EVSE_proposed_current)


            self.check_for_updates(EVSE_proposed_current)
        
            # Update EVSEproposed db with new Charging Current values @ time t
            self.evse_proposed_cp(EVSE_proposed_current)
            return EVSE_proposed_current

    # (7/8) TO RETRIEVE EVSE DATA (I.E., ACTUAL CHARGING PROFILE)
    def evse_actual_cp(self):

        CP_actual = {}  # Initialise CP_actual for EVSE_T_t_minus_1 & C_CP_t_minus_1
        
        # Connect to self.cp_actual_db
        try:
            conn = sqlite3.connect(self.cp_actual_db)
            cursor = conn.cursor()

            # Fetch previous actual EVSE data at time t-1 (ACTUAL CURRENT)
            cursor.execute(f"select cp_id, evse_max_a, evse_meter, evse_status from evse_data")
            record = cursor.fetchall()           

            # Organize data into a dictionary
            for row in record:
                cp_id, evse_max_a, evse_meter, evse_status = row
                CP_actual[cp_id] = {'evse_max_a': evse_max_a, 'evse_meter': evse_meter, 'evse_status': evse_status}

            cursor.close()

        except sqlite3.Error as error:
            print("Failed to read data from table...", error)
            
        finally:
            if (conn):
                conn.close()    # Close SQLite3 connection

        return CP_actual

    # (END/8) INSERT new PROPOSED data (i.e., PROPOSED CURRENT values for EVSE)
    def evse_proposed_cp(self, EVSE_proposed_current):

        # Connect to Proposed Charging Profile Database
        try:
            conn, c = connect_db_fromDLM()

            # Replace DLM VALUES in each TIMESLOT (triggers when Charging Profile is updated)
            for cp_id, values in EVSE_proposed_current.items():
                
                # Check if the CP_ID already exists in the table
                c.execute("SELECT CP_ID FROM DLM_CURRENT WHERE CP_ID = ?", (cp_id,))
                exists = c.fetchone()

                # Shift values in TIME columns to make room for new values
                for i in range(1, self.timeslots, 1):      
                    c.execute(f'''
                        UPDATE DLM_CURRENT
                        SET TIME_{i} = CASE
                            WHEN TIME_{i+1} IS NULL THEN 0
                            ELSE TIME_{i+1} 
                            END
                        WHERE CP_ID = ?
                    ''', (cp_id,)) # Insert or update the latest value
                
                # If cp_id exists in EVSE_proposed_current dictionary as keys
                if exists:  # Update the latest value of existing cp_id to latest timeslot
                    c.execute(f'''
                        UPDATE DLM_CURRENT
                        SET TIME_NOW = DATETIME('now'), TIME_{self.timeslots} = ?
                        WHERE CP_ID = ?
                    ''', (values[-1], cp_id))
                else:       # Insert a new row for a new unique cp_id
                    time_columns = ", ".join([f"TIME_{i}" for i in range(1, self.timeslots + 1)])
                    time_values = ", ".join(['?'] * self.timeslots)
                    c.execute(f'''
                        INSERT INTO DLM_CURRENT (CP_ID, TIME_NOW, {time_columns})
                        VALUES (?, DATETIME('now'), {time_values})
                    ''', (cp_id, *([0]*(self.timeslots-1)), values[-1]))

            # Delete rows for CP_IDs not in EVSE_proposed_current dictionary
            all_cp_ids = list(EVSE_proposed_current.keys())
            c.execute(f'''
                DELETE FROM DLM_CURRENT
                WHERE CP_ID NOT IN ({','.join('?'*len(all_cp_ids))})
            ''', all_cp_ids)

            close_db(conn)

        except sqlite3.Error as error:
            print("Failed to read data from table...", error)
        
        finally:
            if (conn):
                conn.close()
                # print("The Sqlite connection is closed")

    def check_for_updates(self,EVSE_proposed_current):
        conn, c = connect_db_fromDLM()

        # Get the initial value of TIME_10
        c.execute('SELECT TIME_10 FROM DLM_CURRENT')
        initial_value = c.fetchone()

        # If the current value is different from the initial value, call another function
        if EVSE_proposed_current != initial_value:
            post_api(EVSE_proposed_current)
            print("To update AC Load!!!!!!!!!!!!!!!!!")
            AC_load_serial(EVSE_proposed_current)
            # Iterate over the EVSE_proposed_current dictionary
            # for charge_point_id, limit in EVSE_proposed_current.items():
            #     limit = limit[0]  # Get the first item from the list
            #     body2 = [{"cp_id": charge_point_id, "value": limit}]
            #     manual_evse_meter(body2)
        # else:
            # print("False")
            
        close_db(conn)

# TO RUN DLM_test_run.py + modbus_rtu.py ONLY
# if __name__ == "__main__":
#     evse_manager = EVSEManager()  
#     while True:
#         No_of_EVSEs_in_use = len(evse_manager.evse_actual_cp().keys())
#         evse_manager.dlm_threshold(No_of_EVSEs_in_use)
#         time.sleep(1) 

# DEBUG
# if __name__ == "__main__":
#     evse_manager = EVSEManager()
#     print("entire actual cp: ", evse_manager.evse_actual_cp())
#     print("no. of evses: ", len(evse_manager.evse_actual_cp().keys()))
#     print("the type is: ", type(len(evse_manager.evse_actual_cp().keys())))
#     for cp_id, evse in evse_manager.evse_actual_cp().items():
#         # evse is DLM.evse_actual_cp()[cp_id]
#         print("this is cp_id: ", cp_id)
#         print("this is max. current: ", evse['evse_max_a'])
#         print("this is charging current: ", evse['evse_meter'])
#         print("this is evse status: ", evse['evse_status'])
#         print("Type: ", type(evse['evse_status']))        

# if __name__ == "__main__":
#     evse_manager = EVSEManager()  
#     print("No. of EVSEs: ", evse_manager.load_previous_evse_count())
#     print("Datatype: ", type(evse_manager.load_previous_evse_count()))
#     print("This is the no. of EVSEs: ", len(evse_manager.evse_actual_cp().keys()))
#     print("Datatype: ", type(len(evse_manager.evse_actual_cp().keys())))
