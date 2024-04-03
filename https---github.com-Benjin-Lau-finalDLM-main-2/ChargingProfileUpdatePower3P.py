import math
from copy import deepcopy

####################################################################################################################################
def redistribute_charging_capacity(evse_data, line_loads, site_cap=400):
    
    # INITIALISE VARIABLES
    C_CP_t = 100                                 # Available charging capacity at time t
    site_voltage = 400
    phase_voltage = 230
    # line_cap = site_cap/3
    line_cap = site_cap                         # Line capacity
    EVSE_n_max = {}                             # Maximum rated current for each EVSE
    EV_state_t = {}                             # State of charge for each EVSE
    EVSE_Max_Total_t = 0                        # Total available capacity for all EVSEs
    EVSE_proposed_rates = {}                    # Proposed charging rates for each EVSE
    EVSE_proposed_current = {}                  # Proposed charging current for each EVSE
    EVSE_proposed_current_3P = {}               # Proposed charging current for each EVSE (three-phase)
    EVSE_proposed_power = {}
    EVSE_to_adjust = []                         # List of EVSEs to be adjusted
    unused_current = 0                          # Unused current available for redistribution
    unused_current_exist = unused_current > 0   # Flag to indicate if unused current exists
    total_allocated_current = 0                 # Total current allocated to EVSEs (to be used to determine unused_current)

    # TO GET MAX. CURRENT RATING FOR EACH EVSE
    for cp_id, evse in evse_data.items():
        EVSE_n_max[cp_id] = float(evse['evse_max_a'])
        EV_state_t[cp_id] = int(evse['evse_status'])
    
    # Calculate available capacity for each line
    line_cap_avail = {line: line_cap - load for line, load in line_loads.items()}                           # Store available line capacity

    # SUM: Calculate POTENTIAL Total Max EVSE Capacity in use (n) @ time t
    EVSE_Max_t = {key: EVSE_n_max[key] * (1 - EV_state_t[key]) for key in EVSE_n_max if key in EV_state_t}  # Calculate maximum permissible current for each EVSE
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
                                                (math.floor(EVSE_n_max[cp_id]/3 * 10) / 10))]
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
                                                (EVSE_n_max[cp_id]))]
                EVSE_proposed_current_3P[cp_id] = EVSE_proposed_current[cp_id]
                
                # UPDATE:   Remove assigned Proposed Current from INSTALLED line
                line_cap_avail[lines] -= EVSE_proposed_current[cp_id][0]
                
            # UPDATE:   Add initial proposed current to total allocated current
            total_allocated_current += EVSE_proposed_current_3P[cp_id][0]

            # CONVERT: From current to power
            if evse['type'] == 'DC':
                EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[cp_id][0]
                EVSEpower_DC = EVSEpower_AC * evse['efficiency']/100
                EVSE_proposed_power[cp_id] = [(math.floor(EVSEpower_DC) * 10)/10]
            elif evse['type'] == 'AC':
                if evse['phase'] == 'three-phase':
                    EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[cp_id][0]
                elif evse['phase'] == 'single-phase':
                    EVSEpower_AC = phase_voltage * EVSE_proposed_current_3P[cp_id][0]
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
            if EVSE_proposed_current_3P[cp_id][0] < EVSE_n_max[cp_id]: 
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
                    if EVSE_proposed_current_3P[cp_id][0] > EVSE_n_max[cp_id]:
                        EVSE_proposed_current_3P[cp_id] = [EVSE_n_max[cp_id]]
                    for line in lines:
                        line_cap_avail[line] -= EVSE_proposed_current_3P[cp_id][0]/3                # Remove updated proposed current from available line capacity
                elif evse_data[cp_id]['phase'] == 'single-phase': 
                    EVSE_proposed_current_3P[cp_id][0] += add_on_current
                    if EVSE_proposed_current_3P[cp_id][0] > EVSE_n_max[cp_id]:
                        EVSE_proposed_current_3P[cp_id] = [EVSE_n_max[cp_id]]
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
            EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[evse][0]
            EVSEpower_DC = evse_data[evse]['efficiency']/100 * EVSEpower_AC
            EVSE_proposed_power[evse] = [(math.floor(EVSEpower_DC) * 10)/10]
        elif evse_data[evse]['type'] == 'AC':
            if evse_data[evse]['phase'] == 'three-phase':
                EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[evse][0]
            elif evse_data[evse]['phase'] == 'single-phase':
                EVSEpower_AC = phase_voltage * EVSE_proposed_current_3P[evse][0]
            EVSE_proposed_power[evse] = [(math.floor(EVSEpower_AC) * 10)/10]

    print(f"Distributed Charging Capacities to each EVSE: ", EVSE_proposed_current)
    print("*****************************************************")
    print("EVSE Proposed Current (3P): ", EVSE_proposed_current_3P)
    # print("EVSE Proposed Current (submitted): ", EVSE_proposed_current)
    print("EVSE Proposed Power: ", EVSE_proposed_power)

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
            print("new " + line + ": ", new_line_total[line])

    total_ev = math.floor(sum(new_line_ev.values()) * 10) / 10
    print("New EV Charging Current: ", total_ev)

    return EVSE_proposed_power
#########################################################################################################################################

# Example usage
line_loads = {'L1': 290, 'L2': 10, 'L3': 0}
evse_data = {
    'LOSa': {'evse_max_a': 16, 'evse_meter': 10, 'evse_status' : 0, 'type': 'AC', 'phase': 'single-phase', 'line': 'L1'}, 
    'LOSb': {'evse_max_a': 16, 'evse_meter': 10, 'evse_status' : 0, 'type': 'AC', 'phase': 'single-phase', 'line': 'L2'},
    'LOSc': {'evse_max_a': 16, 'evse_meter': 10, 'evse_status' : 0, 'type': 'AC', 'phase': 'single-phase', 'line': 'L3'},
    'LOSd': {'evse_max_a': 8, 'evse_meter': 5, 'evse_status' : 0, 'type': 'AC', 'phase': 'single-phase', 'line': 'L1'},
    'LOSe': {'evse_max_a': 32, 'evse_meter': 20, 'evse_status' : 0, 'type': 'DC', \
            'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSf': {'evse_max_a': 32, 'evse_meter': 20, 'evse_status' : 0, 'type': 'DC',  \
            'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSg': {'evse_max_a': 32, 'evse_meter': 20, 'evse_status' : 0, 'type': 'AC', 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']}
}

redistributed_evse_data = redistribute_charging_capacity(evse_data, line_loads)
print(redistributed_evse_data)
