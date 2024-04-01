# Import necessary functions
import time
import modbus_rtu
# import modbus_tcp
import sqlite3
import math                     # round down values to 1 decimal place
import logging
from exportData import post_api
from database import close_db, connect_db_fromDLM_current, connect_db_fromDLM_power
from AC_load import AC_load_serial
import requests
import pandas as pd
from copy import deepcopy

"""
---------------------------------------------------------------------------------------------------------------------------
DYNAMIC LOAD MANAGEMENT (DLM) ver 1.2.0
---------------------------------------------------------------------------------------------------------------------------
Initial Completion Date: 11 January 2024
Version Update Date: 15 March 2024

Version Updates (Notes):
---------------------------------------------------------------------------------------------------------------------------
- 04 April 2024:    1.2.0   Added the following
                            (3) get_line_loads() - used to collect current data for three-phase systems
                            (8) redistribute_charging_capacity() - to assign charging profile to EVSE
- 18 March 2024:    1.1.1   Updated algorithm (SCENARIO 3)
                            To take into consideration max. rated EV charging current
- 15 March 2024:    1.1.0   Updated algorithm (SCENARIO 3)
                            To take into consideration 6A minimum permissible EV charging current
- 17 January 2024:  1.0.1   Added threshold_gradient() - temporarily hard-coded
                            Amended evse_proposed_current_cp for database update based on cp_id
                            Deleted load_total_evse_count() & get_total_load()
- 11 January 2024:  1.0.0   Initial Version
                    
---------------------------------------------------------------------------------------------------------------------------
SUMMARISED INFORMATION
---------------------------------------------------------------------------------------------------------------------------
Functions:  01) __init__                        To set initial values
            02) get_total_load                  To get onsite total load from modbus tcp or rtu
            03) get_line_loads                  To get onsite line load (L1, L2, L3) from modbus tcp or rtu
            04) threshold_gradient              To calculate threshold gradient in triggering DLM based of gradient of total load
            05) calculate_gradient              To calculate gradient of total load (time t - time t-1)
            06) dlm_threshold                   To determine conditions in the triggering or releasing of DLM & Charging Profile Change
            07) perform_dlm                     To perform DLM & determine new Charging Profile
            08) redistribute_charging_capacity  To redistribute existing charging capacity by assigning charging profile ot EVSEs in use
            09) evse_actual_cp                  To read actual values from EVSE database (cp_id, evse_max_a, evse_meter, evse_status)
            10) evse_proposed_current_cp        To load proposed Charging Profile to EVSE proposed database (CP_ID, TIME_10)


---------------------------------------------------------------------------------------------------------------------------
DEFINITIONS
---------------------------------------------------------------------------------------------------------------------------
VARIABLE NAME               DEFINITION                                              UNIT            DATATYPE
>> Fixed Variables <<
time_interval               Time interval between each iteration                    seconds         int
site_capacity               Maximum site capacity                                   amperes         float
timeslots                   Number of timeslots to store in database                -               integer
cp_proposed_current_db      EVSE proposed database name                             -               string
cp_actual_db                EVSE actual database name                               -               string
EVSE_n_max                  Maximum current rating for each EVSE                    amperes         string

>> Thresholds <<
trigger_percent             Percentage of site capacity to trigger DLM              percentage      float
release_percent             Percentage of site capacity to release DLM              percentage      float
trigger_threshold           Trigger threshold for DLM activation                    amperes         float
release_threshold           Release threshold for DLM deactivation                  amperes         float
threshold_gradient          Threshold gradient to trigger Charging Profile change   amperes/second  float

>> Currents <<
C_CP_t                      Available charging capacity, which includes             amperes         float
                            1) Used EVSE current
                            2) Unused current based off trigger threshold
C_CP_t_minus_1              Available charging capacity at time t-1                 amperes         float
EVSE_T_t_minus_1            Total EVSE charging current at time t-1                 amperes         float

---------------------------------------------------------------------------------------------------------------------------
"""

class EVSEManager:
    # (START/10) PREREQUISITES1
    def __init__(self):
        # SITE INFORMATION
        self.site_capacity = 20         # Max. Site Capacity in A (ampere)
        self.site_voltage = 400
        self.phase_voltage = 230
        self.line_cap = self.site_capacity/3
        
        # SET GRADIENT THRESHOLD
        self.time_interval = 1          # Assuming a 1-second resolution, adjust as needed
        self.dlm_active = False         # Flag to track DLM activation
        self.C_CP_t_minus_1 = 0         # Default to prevent errors

        # THRESHOLDS FOR TRIGGERING DLM
        self.trigger_percent = 0.75
        self.release_percent = 0.4
        self.trigger_threshold = self.trigger_percent * self.site_capacity     # 0.75*20 = 15A
        self.release_threshold = self.release_percent * self.site_capacity     # 0.40*20 = 8A

        # DATABASE & TABLE CREATION with constructed COLUMN DEFINITIONS
        self.timeslots = 10
        self.cp_proposed_current_db = "evse_proposed_current_cp.db"
        self.cp_proposed_power_db = "evse_proposed_power_cp.db"
        self.cp_actual_db = "evse_database.db"
        self.column_definitions = ["CP_ID     INTEGER     NOT NULL",    # No primary key declared
                                   "TIME_NOW DATETIME    NOT NULL"]     # Sqlite3 will create ROWID as internal primary key
        for i in range(1, self.timeslots+1):                            # Each row represents current per iteration
            self.column_definitions.append(f"TIME_{i} DECIMAL(10,5)")
        self.EVSEproposed_current_table = f"CREATE TABLE IF NOT EXISTS DLM_CURRENT ({', '.join(self.column_definitions)})"
        self.EVSEproposed_power_table = f"CREATE TABLE IF NOT EXISTS DLM_POWER ({', '.join(self.column_definitions)})"

        # TO GET MAX. CURRENT RATING & STATE FOR EACH EVSE
        self.EVSE_n_max = {}                                    # Create dictionary to store EVSE max current rating                                   
        for cp_id, evse in self.evse_actual_cp().items():         
            self.EVSE_n_max[cp_id] = float(evse['evse_max_a'])  # Max. Current Rating for each EVSE (based off evse_database)

    # (2/10) TO GET TOTAL LOAD (AMPERES) FROM BUILDING MAIN METER (via MODBUS)
    def get_total_load(self):
        [total_load_t, total_load_t_minus_1] = modbus_rtu.total_current() # From Modbus RTU gateway
        return  total_load_t, total_load_t_minus_1

    # (3/10) TO GET LINE LOAD (AMPERES) FOR EACH PHASE FROM BUILDING MAIN METER (via MODBUS)
    def get_line_loads(self):
        [site_L1_current, site_L2_current, site_L3_current] = modbus_rtu.line_current()
        line_loads =   {"L1": site_L1_current,
                        "L2": site_L2_current,
                        "L3": site_L3_current}
        return line_loads

    ################################################################################
    # -- DYNAMIC LOAD MANAGEMENT
    ################################################################################

    # (4/10) TO DYNAMICALLY CALCULATE GRADIENT THRESHOLD (WORK IN PROGRESS!!)
    def threshold_gradient(self):
        # Function to intelligently select appropriate threshold gradient
        threshold_gradient = 1  # Temporary

        return threshold_gradient
    
    # (5/10) TO CALCULATE GRADIENT OF TOTAL_LOAD &
    #       To DETERMINE WHEN TO TRIGGER CHARGING PROFILE UPDATE
    def calculate_gradient(self, total_load_t, total_load_t_minus_1):
        return (total_load_t - total_load_t_minus_1) / self.time_interval

    # (6/10) TO TRIGGER-RELEASE (DLM) BASED ON THRESHOLD
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

    # (7/10) TO PERFORM DLM WHEN GRADIENT MEETS THRESHOLD
    def perform_dlm(self, total_load_t, site_capacity, C_CP_t_minus_1):
        
        # PREREQUISITES for DLM
        EVSE_proposed_current = {}  # Empty dictionary to hold calculated charging capacity (current) for EVSEs @ time t
        EVSE_proposed_power = {}    # Empty dictionary to hold calculated charging capacity (power) for EVSEs @ time t
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
                EVSE_proposed_power[cp_id] = [0]
            C_CP_t = sum(sum(EVSE_proposed_current[cp_id]) for cp_id in EVSE_proposed_current)
        
            # Flag of description
            print(f"RESULT: Stopped Charging! Charging Profile: All EVSE values are {C_CP_t}A!")
            if total_load_t > site_capacity:
                print(f"EVSEs stopped charging as total load (t), {total_load_t}A, exceeds maximum site capacity, {site_capacity}A!")
            else:
                print(f"EVSEs stopped charging as total load (t) hits maximum site capacity of {site_capacity}A!")

            self.check_for_updates(EVSE_proposed_current)   # Check for updates
            self.evse_proposed_current_cp(EVSE_proposed_power)    # Update EVSEproposed db with new Charging Power values @ time t
            self.evse_proposed_current_cp(EVSE_proposed_current)    # Update EVSEproposed db with new Charging Current values @ time t

            return EVSE_proposed_power #,EVSE_proposed_current
        
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

            # RUN REDISTRIBUTION OF CHARGING CAPACITY
            EVSE_proposed_power = self.redistribute_charging_capacity(C_CP_t)
            
            self.check_for_updates(EVSE_proposed_current)
            self.evse_proposed_current_cp(EVSE_proposed_current)    # Update EVSEproposed db with new Charging Current values @ time t
            # EVSE_T_proposed_current = sum(EVSE_proposed_current[cp_id][0] for cp_id in EVSE_proposed_current) # Total Proposed EVSE Charging Current

            return EVSE_proposed_power #,EVSE_proposed_current
        
        # SCENARIO 4: Available EVSE Charging Capacity (C_CP_t) <= 0
        else:
            print("CP RESULT: Stopped Charging!")
            print(f"EVSEs stop charging as C_CP_t is {C_CP_t}A, whereas C_CP_t_minus_1 is {C_CP_t_minus_1}A")
            # raise Exception(DESCRIPTION_CP_stop)

            # Proposed EVSE current = 0 & Available Site Charging Capacity @ time t, C_CP_t = 0
            for cp_id, evse in self.evse_actual_cp().items():
                EVSE_proposed_current[cp_id] = [0]
                EVSE_proposed_power[cp_id] = [0]
            C_CP_t = sum(sum(EVSE_proposed_current[cp_id]) for cp_id in EVSE_proposed_current)
            
            self.check_for_updates(EVSE_proposed_current)
            self.evse_proposed_current_cp(EVSE_proposed_current)    # Update EVSEproposed db with new Charging Current values @ time t
            
            return EVSE_proposed_power #,EVSE_proposed_current

    ####################################################################################################################################
    # (8/10) TO REDISTRIBUTE EXISTING CHARGING CAPACITY BY ASSIGNING CHARGING PROFILE TO EVSEs IN USE
    def redistribute_charging_capacity(self, C_CP_t):
        
        # INITIALISE VARIABLES
        evse_data = self.evse_actual_cp()   # EVSE information
        EV_state_t = {}                     # State of charge for each EVSE
        EVSE_Max_Total_t = 0                # Total available capacity for all EVSEs
        EVSE_proposed_rates = {}            # Proposed charging rates for each EVSE
        EVSE_proposed_current = {}          # Proposed charging current for each EVSE
        EVSE_proposed_current_3P = {}       # Proposed charging current for each EVSE (three-phase)
        EVSE_proposed_power = {}            # Proposed charging power for each EVSE
        EVSE_to_adjust = []                 # List of EVSEs to be adjusted
        unused_current = 0                  # Unused current available for redistribution
        total_allocated_current = 0         # Total current allocated to EVSEs (to be used to determine unused_current)

        # TO GET MAX. CURRENT RATING FOR EACH EVSE
        for cp_id, evse in evse_data.items():
            self.EVSE_n_max[cp_id] = float(evse['evse_max_a'])
            EV_state_t[cp_id] = int(evse['evse_status'])
        
        # Calculate available capacity for each line
        line_cap_avail = {line: self.line_cap - load for line, load in self.get_line_loads.items()}                           # Store available line capacity

        # SUM: Calculate POTENTIAL Total Max EVSE Capacity in use (n) @ time t
        EVSE_Max_t = {key: self.EVSE_n_max[key] * (1 - EV_state_t[key]) for key in self.EVSE_n_max if key in EV_state_t}  # Calculate maximum permissible current for each EVSE
        EVSE_Max_Total_t = sum(EVSE_Max_t.values())                                                             # TIP: Value of EVSE_Max_Total_t changes as EVSE_n changes

        # (1/3) INITIAL (BASE) CALCULATION FOR PROPOSED CHARGING RATES & CURRENT:
        '''
        ---------------------------------------------------------------------------------------------------------------------------
        INITIAL (BASE) CALCULATION FOR PROPOSED CHARGING RATES & CURRENT:
        REPLACE:    EVSE values at time t-1 with new values at time t
        CALCULATE:  Proposed Charging Rates for EACH EVSE in use at time t
                    Proposed Charging Current for EACH EVSE in use at time t
        ---------------------------------------------------------------------------------------------------------------------------
        '''
        for cp_id, evse in evse_data.items():
            if EVSE_Max_Total_t != 0:
                
                # CALCULATE:    Proposed EVSE charging rates (%) based on EVSE_Max_t, EV_state_t & EVSE_Max_Total_t
                EVSE_proposed_rates[cp_id] = ((EVSE_Max_t[cp_id] * (1 - EV_state_t[cp_id]) / EVSE_Max_Total_t))    
                
                # GET:  Line type installed/assigned (i.e., L1, L2, L3) for each EVSE
                lines = evse['line']

                # CONDITION:    If EVSE is THREE-PHASE, distribute EVENLY across ALL lines
                if evse['phase'] == 'three-phase':  
                    
                    # GET:  Numerical value of the line capacity with the least amount of current capacity available               
                    min_line_cap_avail = min(max(line_cap_avail[line], 0) for line in lines)
                    
                    # CALCULATE:    Proposed EVSE charging profile (A) for THREE-PHASE EVSE
                    ''' 
                    CALCULATE:  Adjust proposed current based on (FOR THREE-PHASE EVSEs)
                                1) Any available (minimum) line capacity (i.e., L1 / L2 / L3), or 
                                2) Weighted proposed rates * Available charging capacity at time t, or
                                3) EVSE_max_t for each EVSE
                                Of the SMALLEST value
                    '''
                    EVSE_proposed_current[cp_id] =  [min((math.floor(min_line_cap_avail * 10) / 10), \
                                                    (math.floor((EVSE_proposed_rates[cp_id] * C_CP_t / 3) * 10) / 10), \
                                                    (math.floor(self.EVSE_n_max[cp_id]/3 * 10) / 10))]
                    EVSE_proposed_current_3P[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 3 * 10) / 10]

                    # UPDATE:   Remove assigned Proposed Current from EACH line (3P Balanced Load)
                    for line in lines:
                        line_cap_avail[line] -= EVSE_proposed_current[cp_id][0]

                # OTHERWISE:    If EVSE is SINGLE-PHASE, distribute SOLELY across INSTALLED line
                elif evse['phase'] == 'single-phase':

                    # CALCULATE:    Proposed EVSE charging profile (A) for SINGLE-PHASE EVSE
                    ''' 
                    CALCULATE:  Adjust proposed current based on (FOR SINGLE-PHASE EVSEs)
                                1) Available line capacity (either L1 or L2 or L3), or 
                                2) Weighted proposed rates * Available charging capacity at time t, or
                                3) EVSE_max_t for each EVSE
                                Of the SMALLEST value
                    '''
                    correct_line_cap_avail = line_cap_avail[lines] if line_cap_avail[lines] >= 0 else 0
                    EVSE_proposed_current[cp_id] =  [min(correct_line_cap_avail, \
                                                    (math.floor((EVSE_proposed_rates[cp_id] * C_CP_t) * 10) / 10), \
                                                    (self.EVSE_n_max[cp_id]))]
                    EVSE_proposed_current_3P[cp_id] = EVSE_proposed_current[cp_id]
                    
                    # UPDATE:   Remove assigned Proposed Current from INSTALLED line
                    line_cap_avail[lines] -= EVSE_proposed_current[cp_id][0]
                    
                # UPDATE:   Add initial proposed current to total allocated current
                total_allocated_current += EVSE_proposed_current_3P[cp_id][0]

                # CONVERT: From current to power
                if evse['type'] == 'DC':
                    EVSEpower_AC = 1.732 * self.site_voltage * EVSE_proposed_current_3P[cp_id][0]
                    EVSEpower_DC = EVSEpower_AC * evse['efficiency']/100
                    EVSE_proposed_power[cp_id] = [(math.floor(EVSEpower_DC) * 10)/10]
                elif evse['type'] == 'AC':
                    if evse['phase'] == 'three-phase':
                        EVSEpower_AC = 1.732 * self.site_voltage * EVSE_proposed_current_3P[cp_id][0]
                    elif evse['phase'] == 'single-phase':
                        EVSEpower_AC = self.phase_voltage * EVSE_proposed_current_3P[cp_id][0]
                    EVSE_proposed_power[cp_id] = [(math.floor(EVSEpower_AC) * 10)/10]
            else:
                print(f"NOTICE: No EVSE in use or all EVSEs fully charged @ time t")

        unused_current = math.floor((C_CP_t - total_allocated_current) * 10) / 10   # Calculate unused current
        unused_current_exist = unused_current > 0                                   # Flag to indicate if unused current exists

        # (2/3) ASSIGN EVSEs INTO ADJUSTABLE EVSE LIST
        '''
        ---------------------------------------------------------------------------------------------------------------------------
        EVSE ADJUSTABLE LIST shall >> NOT << include:
        1) EVSEs with proposed current = 0 (i.e., not charging)
        2) EVSEs connected to lines with 0 available capacity after initial distribution
        3) EVSEs with proposed current == max. rated current

        What happens to EVSEs which are >> NOT IN << the Adjustable List?
        - Total weighted value is reduced by the proposed current of EVSEs not in the adjustable list
        - Proposed current remains the same / untouched as the initial proposed current

        What happens to EVSEs which are >> IN << the Adjustable List?
        - EVSE cp_id is added to the adjustable list
        - Available line capacity is added by the proposed current of EVSEs in the adjustable list
        - Total allocated current is reduced by the proposed current of EVSEs in adjustable list

        CALCULATION INCLUDES:
        - UPDATE:   total_weighted_value shall be updated according to EVSEs in adjustable list
        ---------------------------------------------------------------------------------------------------------------------------
        '''
        # CALCULATE:    Updated total allocated current & sort out to adjustable EVSE list while balancing loads
        if any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()) or unused_current_exist:

            # RESET:    FIXED vesions of Proposed EVSE Current (3P) for future use
            EVSE_proposed_fixed_3P = {cp_id: deepcopy(evse) for cp_id, evse in EVSE_proposed_current_3P.items()}

            # CALCULATE:    Total Weighted Current value for each EVSE in USE based off Total Rated Current
            total_weighted_value = sum([EVSE_proposed_fixed_3P[cp_id][0] for cp_id in EVSE_proposed_fixed_3P])

            # SORT:     Determine list of EVSEs in Use in which the Charging Profile shall be adjusted/updated
            for cp_id, evse in EVSE_proposed_current_3P.items():
                # DETERMINE:    If EVSE proposed CP is less than rated value
                #               Add to list
                if EVSE_proposed_current_3P[cp_id][0] < self.EVSE_n_max[cp_id]: 
                    if 0 < evse[0] < 6 or evse[0] >= 6:
                        lines = evse_data[cp_id]['line']                                        # Determine Line Type based off EVSE installation

                        # CONDITION:    If EVSE is three-phase
                        if evse_data[cp_id]['phase'] == 'three-phase':
                            min_line = min(lines, key=line_cap_avail.get)                       # Get current value of line with smallest capacity
                            if line_cap_avail[min_line] <= 0:                                   # IF: Smallest line capacity == 0
                                total_weighted_value -= EVSE_proposed_current_3P[cp_id][0]      # Exclude from list & Remove from total weighted rated value
                            else:                                                               # IF: Smallest line capacity > 0
                                EVSE_to_adjust.append(cp_id)                                    # Add EVSE to list
                        # OTHERWISE:    If EVSE is single-phase
                        elif evse_data[cp_id]['phase'] == 'single-phase':
                            if line_cap_avail[lines] <= 0:
                                total_weighted_value -= EVSE_proposed_current_3P[cp_id][0]
                            else:
                                EVSE_to_adjust.append(cp_id)
                    else:
                        pass
                # OTHERWISE:    Exclude from Adjustable List
                else:
                    total_weighted_value -= EVSE_proposed_current_3P[cp_id][0]                  # Remove from total weighted rated value

        # CALCULATE:    Unused Current based off Available Charging Capacity & initial Allocated Current 
        unused_current = math.floor((C_CP_t - total_allocated_current) * 10) / 10               # Calculate unused current

        # (3/3) UNUSED CURRENT REDISTRIBUTION, INCLUDING CHARGING PROFILE UNDER MIN. CHARGING CURRENT:
        '''
        ---------------------------------------------------------------------------------------------------------------------------
        UNUSED CURRENT REDISTRIBUTION CRITERIA:
        1) Any Unused Current Exist (i.e., unused current is more than 0), or
        2) Any of EVSE Charging Profile is a value between 0 and 6
        3) Adjustable EVSE List is EMPTY (force stop)
        ---------------------------------------------------------------------------------------------------------------------------
        '''
        while unused_current_exist or any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()):

            # CONDITION:    If there is no EVSE to adjust, break out of While-loop (protection against infinite loop)
            if not EVSE_to_adjust:
                break

            # CONDITION:    Only applied to EVSEs which are to be adjusted (ignore EVSEs which are 0A)
            #               EVSEs to be adjusted shall pop one at a time until While condition is False
            for cp_id, evse in EVSE_proposed_current_3P.items():
                if cp_id in EVSE_to_adjust:

                    add_on_current = 0                  # Initialise add-on current to 0
                    lines = evse_data[cp_id]['line']    # Get line type (i.e., L1 / L2 / L3) for each EVSE

                    # CALCULATE:    (Updated) Add-on Current based off Unused Current to initial Proposed Current
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        # Get minimum line capacity available (positive value only)              
                        min_line_cap_avail = min(max(line_cap_avail[line], 0) for line in lines)
                        add_on_current =    min(min_line_cap_avail, \
                                            ((EVSE_proposed_fixed_3P[cp_id][0] / total_weighted_value) * unused_current))
                        for line in lines:
                            line_cap_avail[line] += EVSE_proposed_fixed_3P[cp_id][0] / 3                # Increase first available line capacity for all lines
                    elif evse_data[cp_id]['phase'] == 'single-phase':
                        correct_line_cap_avail = line_cap_avail[lines] if line_cap_avail[lines] >= 0 else 0
                        add_on_current =    min(correct_line_cap_avail, \
                                            ((EVSE_proposed_fixed_3P[cp_id][0] / total_weighted_value) * unused_current))
                        line_cap_avail[lines] += EVSE_proposed_fixed_3P[cp_id][0]                       # Increase first available line capacity for installed line

                    # CONDITION:    If the add-on current is less than 6A, set EVSE proposed current to 0
                    # UPDATE:       Add small current to available line capacity for each installed Line
                    if EVSE_proposed_current_3P[cp_id][0] < 6 and EVSE_proposed_current_3P[cp_id][0] != 0:
                        if evse_data[cp_id]['phase'] == 'three-phase':
                            for line in lines:
                                line_cap_avail[line] += EVSE_proposed_current_3P[cp_id][0] / 3
                        elif evse_data[cp_id]['phase'] == 'single-phase':
                            line_cap_avail[lines] += EVSE_proposed_current_3P[cp_id][0]
                        if len(EVSE_to_adjust) > 1:
                            EVSE_proposed_current_3P[cp_id] = [0]                                       # Set Charging Profile to 0

                    # CALCULATE:    Add calculated add-on current to initial Proposed Current for each EVSE in list
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        EVSE_proposed_current_3P[cp_id][0] += add_on_current
                        if EVSE_proposed_current_3P[cp_id][0] > self.EVSE_n_max[cp_id]:
                            EVSE_proposed_current_3P[cp_id] = [self.EVSE_n_max[cp_id]]
                        for line in lines:
                            line_cap_avail[line] -= EVSE_proposed_current_3P[cp_id][0]/3                # Remove updated proposed current from available line capacity
                    elif evse_data[cp_id]['phase'] == 'single-phase': 
                        EVSE_proposed_current_3P[cp_id][0] += add_on_current
                        if EVSE_proposed_current_3P[cp_id][0] > self.EVSE_n_max[cp_id]:
                            EVSE_proposed_current_3P[cp_id] = [self.EVSE_n_max[cp_id]]
                        line_cap_avail[evse_data[cp_id]['line']] -= EVSE_proposed_current_3P[cp_id][0]  # Remove updated proposed current from available line capacity

                # NO:   It means that EVSE is either not in use, or has too low of a current proposed to be used
                else:
                    pass

            # CONDITION:    After calculating new Proposed Current in above, check if it fits criteria
            #               If it doesn't, remove cp_id from EVSE_to_adjust, and While-loop again
            #               Update unused current value as well
            if any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()):

                for cp_id in EVSE_to_adjust:
                    lines = evse_data[cp_id]['line']
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        min_line = min(lines, key=line_cap_avail.get)                                   # Get the line with the minimum capacity
                        if line_cap_avail[min_line] == 0:                                               # If any of the lines is fully used
                            EVSE_to_adjust.remove(cp_id)                                                # Remove EVSE unique ID
                        else:
                            for line in lines:                                                          # If EVSE remains in list
                                line_cap_avail[line] += EVSE_proposed_current_3P[cp_id][0]/3            # Add EVSE proposed current available line capacity as it will reset
                    elif evse_data[cp_id]['phase'] == 'single-phase':
                        if line_cap_avail[lines] == 0:                                                                  # If any of the lines is fully used
                            EVSE_to_adjust.remove(cp_id)                                                                # Remove EVSE unique ID
                        else:                                                                                           # If EVSE remains in list
                            line_cap_avail[lines] += EVSE_proposed_current_3P[cp_id][0]                                 # Add EVSE proposed current available line capacity as it will reset
                
                # Identifies cp_id with the smallest evse current in adjutable EVSE list for removal
                min_cp_id = None                                                                # Initialise min. cp_id with None
                min_evse = float('inf')                                                         # Initialise min. evse current with a very large number
                for cp_id in EVSE_to_adjust:
                    if EVSE_proposed_current_3P[cp_id][0] < min_evse:                           # Update variables until smallest current is identified
                        min_cp_id = cp_id                                                       # Identify smallest cp_id
                        min_evse = EVSE_proposed_current_3P[cp_id][0]                           # Identify smallest evse current

                if min_cp_id is not None:                                                       # If there is a min. EVSE
                    EVSE_proposed_current_3P[min_cp_id] = [0]                                   # EVSE proposed current shall reset to 0
                    EVSE_to_adjust.remove(min_cp_id)                                            # Remove smallest cp_id from adjustable EVSE list

                for cp_id in EVSE_to_adjust:                                                    # If EVSE is still in list
                    EVSE_proposed_current_3P[cp_id] = deepcopy(EVSE_proposed_fixed_3P[cp_id])   # Newly proposed EVSE current shall reset to initial proposed current

                total_weighted_value = sum([EVSE_proposed_fixed_3P[cp_id][0] for cp_id in EVSE_to_adjust])
                EVSE_proposed_current_3P_total = sum(EVSE_proposed_current_3P[cp_id][0] for cp_id in evse_data)
                unused_current = C_CP_t - EVSE_proposed_current_3P_total
                
            else:
                unused_current_exist = False

        # Correct the values to 1 decimal place
        for cp_id, evse in EVSE_proposed_current_3P.items():
            if evse_data[cp_id]["phase"] == "three-phase":
                EVSE_proposed_current[cp_id] = [math.floor((EVSE_proposed_current_3P[cp_id][0]/3)* 10) / 10]
            elif evse_data[cp_id]["phase"] == "single-phase":
                EVSE_proposed_current[cp_id] = EVSE_proposed_current_3P[cp_id]

        for cp_id in EVSE_proposed_current:
            EVSE_proposed_current[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 10) / 10]

        # CONVERT: From current to power
        for evse in EVSE_proposed_current_3P:
            if evse_data[evse]['type'] == 'DC':
                EVSEpower_AC = 1.732 * self.site_voltage * EVSE_proposed_current_3P[evse][0]
                EVSEpower_DC = evse_data[evse]['efficiency']/100 * EVSEpower_AC
                EVSE_proposed_power[evse] = [(math.floor(EVSEpower_DC) * 10)/10]
            elif evse_data[evse]['type'] == 'AC':
                if evse_data[evse]['phase'] == 'three-phase':
                    EVSEpower_AC = 1.732 * self.site_voltage * EVSE_proposed_current_3P[evse][0]
                elif evse_data[evse]['phase'] == 'single-phase':
                    EVSEpower_AC = self.phase_voltage * EVSE_proposed_current_3P[evse][0]
                EVSE_proposed_power[evse] = [(math.floor(EVSEpower_AC) * 10)/10]

        # print(f"Distributed Charging Capacities to each EVSE: ", EVSE_proposed_current)
        # print("*****************************************************")
        # print("EVSE Proposed Current (3P): ", EVSE_proposed_current_3P)
        # # print("EVSE Proposed Current (submitted): ", EVSE_proposed_current)
        # print("EVSE Proposed Power: ", EVSE_proposed_power)

        return EVSE_proposed_power

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

    # (10/11) INSERT new PROPOSED data (i.e., PROPOSED CURRENT values for EVSE)
    def evse_proposed_current_cp(self, EVSE_proposed_current):

        # Connect to Proposed Charging Profile Database
        try:
            conn, c = connect_db_fromDLM_current()

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

    # (END/11) INSERT new PROPOSED data (i.e., PROPOSED POWER values for EVSE)
    def evse_proposed_power_cp(self, EVSE_proposed_power):

        # Connect to Proposed Charging Profile Database
        try:
            conn, c = connect_db_fromDLM_power()

            # Replace DLM VALUES in each TIMESLOT (triggers when Charging Profile is updated)
            for cp_id, values in EVSE_proposed_power.items():

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
            all_cp_ids = list(EVSE_proposed_power.keys())
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
        conn, c = connect_db_fromDLM_current()

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