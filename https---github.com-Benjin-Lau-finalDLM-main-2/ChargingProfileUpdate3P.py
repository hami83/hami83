import math
from copy import deepcopy
# from DLM_test_run import EVSEManager # Import EVSEManager class from DLM_test_run.py

# evse_manager = EVSEManager()
# C_CP_t = EVSEManager.available_charging_capacity()

class ChargingProfileUpdate3P:
    
    def __init__(self):
        # Initialize variables
        self.CP_t = 130                                # Available charging capacity
        self.site_cap = 390                             # Total site capacity
        self.line_cap = self.site_cap / 3                     # Assume equal capacity for each line
        EVSE_n_max = {}                             # Maximum rated current for each EVSE
        EV_state_t = {}                             # State of charge for each EVSE
        for cp_id, evse in evse_data.items():
            self.EVSE_n_max[cp_id] = float(evse['evse_max_a'])
            self.EV_state_t[cp_id] = int(evse['evse_status'])
        EVSE_Max_Total_t = 0                        # Total available capacity for all EVSEs
        EVSE_proposed_rates = {}                    # Proposed charging rates for each EVSE
        EVSE_proposed_current = {}                  # Proposed charging current for each EVSE
        EVSE_proposed_current_3P = {}               # Proposed charging current for each EVSE (three-phase)
        EVSE_to_adjust = []                         # List of EVSEs to be adjusted
        unused_current = 0                          # Unused current available for redistribution
        unused_current_exist = unused_current > 0   # Flag to indicate if unused current exists
        # unused_current_exist = unused_current > 1   # Flag to indicate if unused current exists
        total_allocated_current = 0                 # Total current allocated to EVSEs (to be used to determine unused_current)

    def calculate_charging_profile(self, evse_data, line_loads, site_cap=390):
        # Calculate available capacity for each line
        line_cap_avail = {line: line_cap - load for line, load in line_loads.items()}               # Store available line capacity
        total_cap_avail = sum(line_cap_avail.values())                                              # Total available capacity       
        print("line_cap_avail: ", line_cap_avail)
        
        # Calculate total current imbalance
        total_imbalance = sum(max(0, line_cap_avail[line] - line_loads[line]) for line in line_cap_avail)
        EVSE_Max_t = {key: EVSE_n_max[key] * (1 - EV_state_t[key]) for key in EVSE_n_max if key in EV_state_t}  # Calculate maximum permissible current for each EVSE
        EVSE_Max_Total_t = sum(EVSE_Max_t.values())                                                             # TIP: Value of EVSE_Max_Total_t changes as EVSE_n changes

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
                
                # Calculate proposed rates based on EVSE_max_t and EV_state_t
                EVSE_proposed_rates[cp_id] = ((EVSE_Max_t[cp_id] * (1 - EV_state_t[cp_id]) / EVSE_Max_Total_t))        
                
                # CONDITION:    If EVSE is three-phase, distribute evenly across all lines
                if evse['phase'] == 'three-phase':  
                                    
                    min_line_cap_avail = min(line_cap_avail[line] for line in evse['line']) # Get minimum line capacity available
                    
                    ''' 
                    CALCULATE:  Adjust proposed current based on (FOR THREE-PHASE EVSEs)
                                1) Available line capacity, or 
                                2) Weighted proposed rates, or
                                3) EVSE_max_t for each EVSE
                    '''                
                    EVSE_proposed_current[cp_id] = [min((math.floor(min_line_cap_avail * 10) / 10), (math.floor((EVSE_proposed_rates[cp_id] * C_CP_t / 3) * 10) / 10))]
                    EVSE_proposed_current_3P[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 3 * 10) / 10]

                    # WHEN: Proposed current is greater than the maximum EVSE rated current
                    if EVSE_proposed_current_3P[cp_id][0] > math.floor(EVSE_n_max[cp_id] * 10)/10:
                        EVSE_proposed_current[cp_id] = [math.floor(EVSE_n_max[cp_id]/3 * 10) / 10]
                        EVSE_proposed_current_3P[cp_id] = [EVSE_n_max[cp_id]]
                    # Remove proposed current from line capacity available
                    for line in evse['line']:
                        line_cap_avail[line] -= EVSE_proposed_current[cp_id][0]

                    total_allocated_current += EVSE_proposed_current_3P[cp_id][0]   # Add proposed current to total allocated current
                # OTHERWISE:    If EVSE is single-phase, distribute across the installed line
                elif evse['phase'] == 'single-phase':
                    
                    line = evse['line'] # Get line type (i.e., L1, L2, L3) for each EVSE

                    ''' 
                    CALCULATE:  Adjust proposed current based on (FOR THREE-PHASE EVSEs)
                                1) Available line capacity, or 
                                2) Weighted proposed rates, or
                                3) EVSE_max_t for each EVSE
                    '''
                    EVSE_proposed_current[cp_id] = [min((math.floor(line_cap_avail[line] * 10) / 10), (math.floor((EVSE_proposed_rates[cp_id] * C_CP_t) * 10) / 10))]
                    EVSE_proposed_current_3P[cp_id] = EVSE_proposed_current[cp_id]
    
                    # WHEN: Proposed current is greater than the maximum EVSE rated current
                    if EVSE_proposed_current[cp_id][0] > EVSE_n_max[cp_id]:
                        EVSE_proposed_current[cp_id] = [EVSE_n_max[cp_id]]
                        EVSE_proposed_current_3P[cp_id] = [EVSE_n_max[cp_id]]
                    line_cap_avail[line] -= EVSE_proposed_current[cp_id][0]   # Remove proposed current from line capacity available
                                    
                    total_allocated_current += EVSE_proposed_current_3P[cp_id][0]   # Add proposed current to total allocated current
            else:
                print(f"NOTICE: No EVSE in use or all EVSEs fully charged @ time t")

        print("---")
        print("******************* INITIAL START *******************")
        print("Updated line capacity available: ", line_cap_avail)
        print("This is actual EVSE currents: ", EVSE_proposed_current_3P)
        print("total allocated current so far is: ",total_allocated_current) 
        print("unused based off C_CP_t: ", C_CP_t - total_allocated_current)
        unused_current = math.floor((C_CP_t - total_allocated_current) * 10) / 10   # Calculate unused current
        unused_current_exist = unused_current > 0   # Flag to indicate if unused current exists
        print("******************* INITIAL DONE *******************")
        print("---")

        # CALCULATE:    Updated total allocated current & sort out to adjustable EVSE list while balancing loads
        if any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()) or unused_current_exist:
            self.evse_adjustable_list(evse_data, line_loads, site_cap)

        line_cap_fixed = {deepcopy(line): deepcopy(load) for line, load in line_cap_avail.items()}  # Store initial line capacity
        print("line_cap_fixed: ", line_cap_fixed)
        print("To adjust: ",EVSE_to_adjust)
        print("Available line capacity after adjustment: ", line_cap_avail)
        print("*-*-*-*-*-*")

        unused_current = math.floor((C_CP_t - total_allocated_current) * 10) / 10   # Calculate unused current
        fixed_unused_current = deepcopy(unused_current)                             # Store reference of unused current
        print("unused current: ", unused_current)

        # CONDITION:    As long as there is Unused Current leftover
        #               OR any of EVSE Proposed Current in each EVSE (cp_id) is between 0 and 6
        while unused_current_exist or any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()):
            self.recalculate_charging_profile(evse_data, line_loads, site_cap)

        for cp_id, evse in EVSE_proposed_current_3P.items():
            if evse_data[cp_id]["phase"] == "three-phase":
                EVSE_proposed_current[cp_id] = [math.floor((EVSE_proposed_current_3P[cp_id][0]/3)* 10) / 10]
            elif evse_data[cp_id]["phase"] == "single-phase":
                EVSE_proposed_current[cp_id] = EVSE_proposed_current_3P[cp_id]

        for cp_id in EVSE_proposed_current:
            EVSE_proposed_current[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 10) / 10]

        print(f"Distributed Charging Capacities to each EVSE: ", EVSE_proposed_current)
        print("*****************************************************")

    #############################################
        print("EVSE Proposed Current (3P): ", EVSE_proposed_current_3P)
        print("EVSE Proposed Current (submitted): ", EVSE_proposed_current)

        new_line_ev = {'L1': 0, 'L2': 0, 'L3': 0}
        new_line_total = {'L1': 0, 'L2': 0, 'L3': 0}
        # Check new load on each line
        for cp_id, evse in evse_data.items():
            line = evse['line']
            if isinstance(line, list):  # If 'line' is a list
                for key in new_line_ev:
                    new_line_ev[key] += math.floor(EVSE_proposed_current_3P[cp_id][0]/3 * 10) / 10
            elif line in new_line_ev:  # If 'line' is a string
                new_line_ev[line] += EVSE_proposed_current_3P[cp_id][0]
        for key in new_line_ev:
            new_line_ev[key] = math.floor(new_line_ev[key] * 10) / 10
        for line in line_loads.keys():
            if line in new_line_total:
                new_line_total[line] = new_line_ev[line] + line_loads[line]
                print("line", line)
                print("new " + line + ": ", new_line_total[line])

        total_ev = math.floor(sum(new_line_ev.values()) * 10) / 10
        print(total_ev)

        return EVSE_proposed_current


    def evse_adjustable_list(self, evse_data, line_loads, site_cap=390):
        # RESET:    FIXED vesions of Proposed EVSE Current (3P) and Proposed EVSE Current for future use
        EVSE_proposed_fixed = {cp_id: deepcopy(evse) for cp_id, evse in EVSE_proposed_current.items()}
        EVSE_proposed_fixed_3P = {cp_id: deepcopy(evse) for cp_id, evse in EVSE_proposed_current_3P.items()}

        # CALCULATE:    Total weighted value for EVSE proposed current
        total_weighted_value = sum([EVSE_proposed_fixed_3P[cp_id][0] for cp_id in EVSE_proposed_fixed_3P])

        # SORT: To determine a list of EVSEs to be adjusted
        for cp_id, evse in EVSE_proposed_current_3P.items():

            '''
            ---------------------------------------------------------------------------------------------------------------------------
            EVSE ADJUSTABLE LIST shall >> NOT << include:
            - EVSEs with proposed current = 0
            - EVSEs connected to lines with 0 available capacity after initial distribution
            - EVSEs with proposed current == max. rated current

            What happens to EVSEs which are >> NOT IN << the Adjustable List?
            1) Total weighted value is reduced by the proposed current of EVSEs not in the adjustable list
            2) Proposed current remains the same / untouched as the initial proposed current

            What happens to EVSEs which are >> IN << the Adjustable List?
            1) EVSE cp_id is added to the adjustable list
            2) Available line capacity is added by the proposed current of EVSEs in the adjustable list
            3) Total allocated current is reduced by the proposed current of EVSEs in the adjustable list
            ---------------------------------------------------------------------------------------------------------------------------
            '''

            # DETERMINE:    Only cp_ids with proposed current < max. rated current is added to adjustable list
            if EVSE_proposed_current_3P[cp_id][0] < EVSE_n_max[cp_id]: #!! self.EVSE_n_max[cp_id]    
                if 0 < evse[0] < 6 or evse[0] >= 6:
                    lines = evse_data[cp_id]['line']
                    # CONDITION:    If EVSE is three-phase
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        # min_line_cap_avail = min(line_cap_avail[line] for line in evse['line']) # Get minimum line capacity available
                        min_line = min(lines, key=line_cap_avail.get)  # Get the line with the minimum capacity
                        if line_cap_avail[min_line] == 0:
                            total_weighted_value -= EVSE_proposed_current_3P[cp_id][0]
                        else:
                            EVSE_to_adjust.append(cp_id)
                            line_cap_avail[min_line] += EVSE_proposed_current_3P[cp_id][0]
                            # total_allocated_current -= EVSE_proposed_current_3P[cp_id][0]
                    # CONDITION:    If EVSE is single-phase
                    elif evse_data[cp_id]['phase'] == 'single-phase':
                        if line_cap_avail[lines] == 0:
                            total_weighted_value -= EVSE_proposed_current_3P[cp_id][0]
                        else:
                            EVSE_to_adjust.append(cp_id)
                            line_cap_avail[evse_data[cp_id]['line']] += EVSE_proposed_current_3P[cp_id][0]
                            # total_allocated_current -= EVSE_proposed_current_3P[cp_id][0]
                else:
                    pass
            # OTHERWISE:    Ignore cp_ids (not to be adjusted at all)
            else:
                total_weighted_value -= EVSE_proposed_current_3P[cp_id][0]



        
            
    def recalculate_charging_profile(self, evse_data, line_loads, site_cap=390):
            print("*************************************************")
            print("Start of WHILE LOOP")
            print("Unused Current status is: ", unused_current_exist)
            print("EVSEs to adjust: ", EVSE_to_adjust)
            print("Unused current: ", unused_current)
            print("FIXED UNUSED CURRENT: ", fixed_unused_current)
            print("*************************************************")

            # # CONDITION:    If there is no EVSE to adjust, break out of While-loop (protection against infinite loop)
            if not EVSE_to_adjust:
                break
            fixed_unused_current = deepcopy(unused_current)
            # line_cap_avail = deepcopy(line_cap_fixed)  # Reset line capacity to initial values

            for cp_id, evse in EVSE_proposed_current_3P.items():

                # CONDITION:    Only applied to EVSEs which are to be adjusted (ignore EVSEs which are 0A)
                #               EVSEs to be adjusted shall pop one at a time until While condition is False
                if cp_id in EVSE_to_adjust:

                    # CALCULATE:    Add potentially Unused Current to Proposed Current
                    #               Add-on current for each EVSE in EVSE_to_adjust list
                    add_on_current = 0                              # Initialised add-on current to 0
                    lines = evse_data[cp_id]['line']                # Get line for EVSE
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        min_line_cap_avail = min(line_cap_avail[line] for line in lines)  # Get minimum line capacity available
                        add_on_current = min(min_line_cap_avail, ((EVSE_proposed_fixed_3P[cp_id][0] / total_weighted_value) * fixed_unused_current))
                    elif evse_data[cp_id]['phase'] == 'single-phase':
                        line = evse_data[cp_id]['line']     # Get line for EVSE
                        add_on_current = min(line_cap_avail[line], ((EVSE_proposed_fixed_3P[cp_id][0] / total_weighted_value) * fixed_unused_current))         
                    print(f"add on current for {cp_id} is: ", add_on_current)

                    # CONDITION:    If the add-on current is less than 6A, set EVSE proposed current to 0
                    if EVSE_proposed_current_3P[cp_id][0] < 6 and EVSE_proposed_current_3P[cp_id][0] != 0:
                        # EVSE_proposed_current[cp_id] = [0]   
                        unused_current += EVSE_proposed_current_3P[cp_id][0]    # Add proposed current to unused current pool
                        EVSE_proposed_current_3P[cp_id] = [0]

                    # CALCULATE:    Add-on current to Proposed Current for each EVSE in EVSE_to_adjust list
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        # EVSE_proposed_current_3P[cp_id] = [0]
                        EVSE_proposed_current_3P[cp_id][0] += add_on_current
                        for line in lines:
                            line_cap_avail[line] -= EVSE_proposed_current_3P[cp_id][0]/3
                        print(f"add on current for {cp_id} is still: ", add_on_current)
                        print("EVSE proposed current is: ", EVSE_proposed_current_3P[cp_id][0])
                        print("EVSE original proposed current is: ", EVSE_proposed_fixed_3P[cp_id][0])
                    elif evse_data[cp_id]['phase'] == 'single-phase': 
                        # EVSE_proposed_current_3P[cp_id] = [0]
                        EVSE_proposed_current_3P[cp_id][0] += add_on_current
                        line_cap_avail[evse_data[cp_id]['line']] -= EVSE_proposed_current_3P[cp_id][0]
                        print(f"add on current for {cp_id} is still: ", add_on_current)
                        print("EVSE proposed current is: ", EVSE_proposed_current_3P[cp_id][0])
                        print("EVSE original proposed current is: ", EVSE_proposed_fixed_3P[cp_id][0])
                    # unused_current -= EVSE_proposed_current_3P[cp_id][0]    # Removed added-on current from unused_current pool
                            
                    print("add on current shall be still: ", add_on_current)
                    print("-----------------")
                # NO:   It means that EVSE is either not in use, or has too low of a current proposed to be used
                else:
                    EVSE_proposed_current[cp_id][0] = 0
                    # pass
            print("Unused Current is now: ", unused_current)
            print("Updated Proposed EVSE Current (3P): ", EVSE_proposed_current_3P)
            print("Fixed proposed current: ", EVSE_proposed_fixed_3P)
            print("Unused current exist status is: ", unused_current_exist)
            print("-----------------------")
            # CONDITION:    After calculating new Proposed Current in above, check if it fits criteria
            #               If it doesn't, remove cp_id from EVSE_to_adjust, and While-loop again
            if any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()):
                # EVSE_proposed_current = deepcopy(EVSE_proposed_fixed)       # EVSE proposed current shall reset to initial proposed values
                # EVSE_proposed_current_3P = deepcopy(EVSE_proposed_fixed_3P) # EVSE proposed current shall reset to initial proposed values
                print("testtesttesttest")
                for cp_id in EVSE_to_adjust:
                    lines = evse_data[cp_id]['line']
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        min_line = min(lines, key=line_cap_avail.get)  # Get the line with the minimum capacity
                        if line_cap_avail[min_line] == 0:
                            # unused_current -= EVSE_proposed_current_3P[cp_id][0]
                            EVSE_to_adjust.remove(cp_id)
                        else:
                            for line in lines:
                                line_cap_avail[line] += EVSE_proposed_current_3P[cp_id][0]/3
                    elif evse_data[cp_id]['phase'] == 'single-phase':
                        if line_cap_avail[lines] == 0:
                            # unused_current -= EVSE_proposed_current_3P[cp_id][0]
                            EVSE_to_adjust.remove(cp_id)
                        else:
                            line_cap_avail[evse_data[cp_id]['line']] += EVSE_proposed_current_3P[cp_id][0]
                
                # Identifies cp_id with the smallest evse current in adjutable EVSE list for removal
                min_cp_id = None                                    # Initialised min. cp_id with None
                min_evse = float('inf')                             # Initialise min. evse current with a very large number

                for cp_id in EVSE_to_adjust:
                    # Check cp_id in EVSE_proposed_current, and smallest number shall be identified
                    if EVSE_proposed_current_3P[cp_id][0] < min_evse:
                        min_cp_id = cp_id                               # Identify smallest cp_id
                        min_evse = EVSE_proposed_current_3P[cp_id][0]   # Identify smallest evse current

                if min_cp_id is not None:
                    unused_current += EVSE_proposed_current_3P[min_cp_id][0]    # Add proposed current to unused current pool
                    EVSE_proposed_current_3P[min_cp_id] = [0]                   # EVSE proposed current shall reset to 0
                    EVSE_to_adjust.remove(min_cp_id)                            # Remove smallest cp_id from adjustable EVSE list
                
                ###!!!!
                for cp_id in EVSE_to_adjust:
                    EVSE_proposed_current_3P[cp_id] = deepcopy(EVSE_proposed_fixed_3P[cp_id])

                total_weighted_value = sum([EVSE_proposed_fixed_3P[cp_id][0] for cp_id in EVSE_to_adjust])
                print("testtesttest")
                # total_weighted_value = sum([temp_proposed_current_3P[cp_id][0] for cp_id in EVSE_to_adjust])
            else:
                unused_current_exist = False

            # print("Is there any unused current?: ", unused_current)
            # print("new total weight: ", total_weighted_value)
            # print("To adjust: ",EVSE_to_adjust)
            print("--------------------------------------------------------")
            print("Unused Current is: ", unused_current)
            print("Unused current exist status is: ", unused_current_exist)
            print("EVSEs to adjust: ", EVSE_to_adjust)
            print("--------------------------------------------------------")



# Example usage
line_loads = {'L1': 95, 'L2': 80, 'L3': 95}
evse_data = {
    'LOSa': {'evse_max_a': 16, 'evse_meter': 10, 'evse_status' : 0, 'phase': 'single-phase', 'line': 'L1'}, 
    'LOSb': {'evse_max_a': 16, 'evse_meter': 10, 'evse_status' : 0, 'phase': 'single-phase', 'line': 'L2'},
    'LOSc': {'evse_max_a': 16, 'evse_meter': 10, 'evse_status' : 0, 'phase': 'single-phase', 'line': 'L3'},
    'LOSd': {'evse_max_a': 8, 'evse_meter': 5, 'evse_status' : 0, 'phase': 'single-phase', 'line': 'L1'},
    'LOSe': {'evse_max_a': 32, 'evse_meter': 20, 'evse_status' : 0, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSf': {'evse_max_a': 32, 'evse_meter': 20, 'evse_status' : 0, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSg': {'evse_max_a': 32, 'evse_meter': 20, 'evse_status' : 0, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']}
}

redistributed_evse_data = redistribute_charging_capacity(evse_data, line_loads)
print("Submitted Charging Profile: ",redistributed_evse_data)
