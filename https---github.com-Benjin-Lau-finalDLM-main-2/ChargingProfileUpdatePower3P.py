import math
from copy import deepcopy
import logging

"""
Issue from MHA - 2024-05-02

"""

####################################################################################################################################
def redistribute_charging_capacity(evse_data, line_loads, site_cap=500):


    # INITIALISE VARIABLES
    C_CP_t = {'L1': 0, 'L2': 0, 'L3': 0}        # Available charging capacity at time t
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
    total_allocated_current = {'L1': 0, 'L2': 0, 'L3': 0}                 # Total current allocated to EVSEs (to be used to determine unused_current)

    # Calculate Used EVSE Charging Capacity at time t-1 (per line)
    print("existing line load: ", line_loads)
    
    C_CP_t_minus_1 = {'L1': 0, 'L2': 0, 'L3': 0}
    for cp_id, data in evse_data.items():
        lines = data["line"]
        evse_meter = data["evse_meter"]
        if isinstance(lines, list):
            for line in lines:
                C_CP_t_minus_1[line] += evse_meter
        else:
            C_CP_t_minus_1[lines] += evse_meter
    print("C_CP_t_minus_1", C_CP_t_minus_1)

    ##############################################
    building_load = {'L1': 0, 'L2': 0, 'L3': 0}
    for line in building_load:
        building_load[line] = line_loads[line] - C_CP_t_minus_1[line]
    print("Building Load: ", building_load)
    ##############################################

    error_correction = 0.07 # to be a variable
    # error_correction = 0 # to be a variable
    
    # Calculate Available Charging Capacity at time t
    for line in C_CP_t_minus_1:
        C_CP_t[line] = max((min(C_CP_t_minus_1[line], line_loads[line]) + (line_cap - line_loads[line]))*(1-error_correction),0)
    print("Available Charging Current per Phase: ",C_CP_t)
    line_cap_avail = {'L1': 0, 'L2': 0, 'L3': 0}
    line_cap_avail = deepcopy(C_CP_t)
    print("line cap avail: ", line_cap_avail)

    if any(C_CP_t[line] > 0 for line in C_CP_t):
        print("Start redistributing charging capacity")
        print("--------------------------------------------------------------------")

    # TO GET MAX. CURRENT RATING FOR EACH EVSE
    for cp_id, evse in evse_data.items():
        EVSE_n_max[cp_id] = float(evse['evse_max_a'])
        EV_state_t[cp_id] = int(evse['evse_status'])
    
    # SUM: Calculate POTENTIAL Total Max EVSE Capacity in use (n) @ time t
    EVSE_Max_t = {key: EVSE_n_max[key] * (1 - EV_state_t[key]) for key in EVSE_n_max if key in EV_state_t}  # Calculate maximum permissible current for each EVSE
    print("EVSE_Max_t: ", EVSE_Max_t)
    print("EVSE_n_max: ", EVSE_n_max)

    ##### added
    seen_keys = set()
    for cp_id, evse in evse_data.items():
        evse_name = cp_id.split("-")[0]
        if evse_name not in seen_keys:
            EVSE_Max_Total_t += EVSE_Max_t[cp_id]
            seen_keys.add(evse_name)
    seen_keys.clear()
    print("EVSE_Max_Total_t: ", EVSE_Max_Total_t)

    #########
    EVSE_Max_Phase_t = {'L1': 0, 'L2': 0, 'L3': 0}
    for cp_id, evse in evse_data.items():
        lines = evse['line']
        evse_name = cp_id.split("-")[0]
        if evse_name not in seen_keys:
            if isinstance(lines, list):
                for line in lines:
                    EVSE_Max_Phase_t[line] += EVSE_Max_t[cp_id]
            else:
                EVSE_Max_Phase_t[lines] += EVSE_Max_t[cp_id]
            seen_keys.add(evse_name)
    seen_keys.clear()
    print("EVSE_Max_Phase_t: ", EVSE_Max_Phase_t)


    # (1/3) INITIAL (BASE) CALCULATION FOR PROPOSED CHARGING RATES & CURRENT:
    '''
    ---------------------------------------------------------------------------------------------------------------------------
    INITIAL (BASE) CALCULATION FOR PROPOSED CHARGING RATES & CURRENT:
    REPLACE:    EVSE values at time t-1 with new values at time t
    CALCULATE:  Proposed Charging Rates for EACH EVSE in use at time t
                Proposed Charging Current for EACH EVSE in use at time t
    ---------------------------------------------------------------------------------------------------------------------------
    '''
    connector_max_a_total = {}
    for cp_id, evse in evse_data.items():
        if 'connector_max_a' not in evse:
            continue
        evse_name = cp_id.split("-")[0]
        connector_max_a = evse['connector_max_a']
        if evse_name not in connector_max_a_total:
            connector_max_a_total[evse_name] = connector_max_a
        else:
            connector_max_a_total[evse_name] += connector_max_a
    print('connector_max_a_total: ', connector_max_a_total)

    current_percentage = {}
    for cp_id, evse in evse_data.items():
        if 'connector_max_a' not in evse:
            current_percentage[cp_id] = 1.0
            continue
        evse_name = cp_id.split("-")[0]
        percentage = (evse['connector_max_a'] / connector_max_a_total[evse_name])
        current_percentage[cp_id] = percentage
    print("current_percentage: ", current_percentage)

    # To updated EVSE_n_max based on evse_max_a & connector_max_a
    corrected_EVSE_n_max = {}
    for cp_id, evse in evse_data.items():
        corrected_EVSE_n_max[cp_id] = evse['evse_max_a'] * current_percentage[cp_id]
    print("new_EVSE_n_max: ", corrected_EVSE_n_max)

    for cp_id, evse in evse_data.items():
        if EVSE_Max_Total_t != 0 and evse['evse_status'] == 0:
                 
            # GET:  Line type installed/assigned (i.e., L1, L2, L3) for each EVSE
            lines = evse['line']

            # CONDITION:    If EVSE is THREE-PHASE, distribute EVENLY across ALL lines
            if evse['phase'] == 'three-phase':  
                #################!!!!!!!!!!!!!!!
                # CALCULATE:    Proposed EVSE charging rates (%) based on EVSE_Max_t, EV_state_t & EVSE_Max_Total_t
                min_EVSE_Max_Phase_t = min(max(EVSE_Max_Phase_t[line], 0) for line in lines)
                EVSE_proposed_rates[cp_id] = ((corrected_EVSE_n_max[cp_id] * (1 - EV_state_t[cp_id]) / min_EVSE_Max_Phase_t))
                print(f"for {cp_id}, the corrected_EVSE_n_max is: {corrected_EVSE_n_max[cp_id]}")
                print(f"for {cp_id}, the EV_state_t is: {EV_state_t[cp_id]}")
                print(f"for {cp_id}, the min_EVSE_Max_Phase_t is: {min_EVSE_Max_Phase_t}")
                print(f"for {cp_id}, the proposed rate is: {EVSE_proposed_rates[cp_id]}")

                # GET:  Numerical value of the line capacity with the least amount of current capacity available               
                min_line_cap_avail = min(max(line_cap_avail[line], 0) for line in lines)
                min_C_CP_t = min(C_CP_t[line] for line in lines) ################!!!!!!!!
                
                # CALCULATE:    Proposed EVSE charging profile (A) for THREE-PHASE EVSE
                ''' 
                CALCULATE:  Adjust proposed current based on (FOR THREE-PHASE EVSEs)
                            1) Any available (minimum) line capacity (i.e., L1 / L2 / L3), or 
                            2) Weighted proposed rates * Available charging capacity at time t, or
                            3) EVSE_max_t for each EVSE
                            Of the SMALLEST value
                '''
                ################!!!!!!!!
                EVSE_proposed_current[cp_id] =  [min((math.floor(min_line_cap_avail * 10) / 10), \
                                                math.floor((EVSE_proposed_rates[cp_id] * min_C_CP_t) * 10) / 10, \
                                                (math.floor(corrected_EVSE_n_max[cp_id] * 10) / 10))]
                # if 'connector_max_a' in evse:
                #     EVSE_proposed_current[cp_id] = [min(EVSE_proposed_current[cp_id][0], 
                #                                     EVSE_proposed_rates[cp_id] * min_EVSE_Max_Phase_t)]
                EVSE_proposed_current_3P[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 10) / 10]

                ################!!!!!!!!
                # print(f"for {cp_id}, answer is either {(math.floor(min_line_cap_avail * 10) / 10)}")
                # print(f"or this {math.floor((EVSE_proposed_rates[cp_id] * min_C_CP_t) * 10) / 10}")
                # print(f"or this {math.floor(EVSE_n_max[cp_id] * 10) / 10}")
                print(f"for {cp_id}, the proposed current is: {EVSE_proposed_current[cp_id]}")
                print("=================")
                ################!!!!!!!!

                # UPDATE:   Remove assigned Proposed Current from EACH line (3P Balanced Load)
                for line in lines:
                    line_cap_avail[line] -= EVSE_proposed_current[cp_id][0]
                    total_allocated_current[line] += EVSE_proposed_current[cp_id][0]

            # OTHERWISE:    If EVSE is SINGLE-PHASE, distribute SOLELY across INSTALLED line
            elif evse['phase'] == 'single-phase':

                # CALCULATE:    Proposed EVSE charging rates (%) based on EVSE_Max_t, EV_state_t & EVSE_Max_Total_t
                EVSE_proposed_rates[cp_id] = ((corrected_EVSE_n_max[cp_id] * (1 - EV_state_t[cp_id]) / EVSE_Max_Phase_t[lines])) 

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
                                                (math.floor((EVSE_proposed_rates[cp_id] * C_CP_t[lines]) * 10) / 10), \
                                                (corrected_EVSE_n_max[cp_id]))]
                EVSE_proposed_current_3P[cp_id] = EVSE_proposed_current[cp_id]

                ############
                # print(f"for {cp_id}, answer is either {correct_line_cap_avail}")
                # print(f"or this {math.floor((EVSE_proposed_rates[cp_id] * C_CP_t[lines]) * 10) / 10}")
                # print(f"or this {math.floor(EVSE_n_max[cp_id] * 10) / 10}")
                print(f"for {cp_id}, the proposed current is: {EVSE_proposed_current[cp_id]}")
                print("=================")
                ###########

                # UPDATE:   Remove assigned Proposed Current from INSTALLED line
                line_cap_avail[lines] -= EVSE_proposed_current[cp_id][0]
                
                # UPDATE:   Add initial proposed current to total allocated current
                total_allocated_current[lines] += EVSE_proposed_current[cp_id][0]

            # CONVERT: From current to power
            if evse['evse_type'] == 'DC':
                EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[cp_id][0]
                EVSEpower_DC = EVSEpower_AC * evse['efficiency']/100
                EVSE_proposed_power[cp_id] = [(math.floor(EVSEpower_DC) * 10)/10]
            elif evse['evse_type'] == 'AC':
                if evse['phase'] == 'three-phase':
                    EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[cp_id][0]
                elif evse['phase'] == 'single-phase':
                    EVSEpower_AC = phase_voltage * EVSE_proposed_current_3P[cp_id][0]
                EVSE_proposed_power[cp_id] = [(math.floor(EVSEpower_AC) * 10)/10]
        else:
            logging.warning(f"NOTICE: EVSE {cp_id} is not in use or all EVSEs fully charged @ time t")

    ############################################################
    logging.warning(f"Initial Proposed Charging Current (1P): {EVSE_proposed_current}")
    logging.warning(f"Initial Proposed Charging Current (3P): {EVSE_proposed_current_3P}")
    ############################################################

    unused_current = {'L1': 0, 'L2': 0, 'L3': 0}
    for line in unused_current:
        unused_current[line] = math.floor((C_CP_t[line] - total_allocated_current[line]) * 10) / 10   # Calculate unused current
    unused_current_exist = any(value > 0 for value in unused_current.values())                                 # Flag to indicate if unused current exists

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
        total_weighted_value = {'L1': 0, 'L2': 0, 'L3': 0}
        for cp_id, evse in evse_data.items():
            lines = evse['line']
            if evse['evse_status'] == 0:
                if evse['phase'] == 'three-phase':
                    for line in lines:
                        total_weighted_value[line] += EVSE_proposed_current_3P[cp_id][0]
                elif evse['phase'] == 'single-phase':
                    total_weighted_value[lines] += EVSE_proposed_current_3P[cp_id][0]
            
            # if evse['phase'] == 'three-phase':
            #     for line in lines:
            #         total_weighted_value[line] += evse['evse_max_a']
            # elif evse['phase'] == 'single-phase':
            #     total_weighted_value[lines] += evse['evse_max_a']

        # SORT:     Determine list of EVSEs in Use in which the Charging Profile shall be adjusted/updated
        for cp_id, evse in EVSE_proposed_current_3P.items():
            lines = evse_data[cp_id]['line'] 
            # DETERMINE:    If EVSE proposed CP is less than rated value
            #               Add to list
            if EVSE_proposed_current_3P[cp_id][0] < corrected_EVSE_n_max[cp_id]: 
                    if 0 < evse[0] < 6 or evse[0] >= 6:
                        # CONDITION:    If EVSE is three-phase
                        if evse_data[cp_id]['phase'] == 'three-phase':
                            min_line = min(lines, key=line_cap_avail.get)                       # Get current value of line with smallest capacity
                            if line_cap_avail[min_line] <= 0:                                   # IF: Smallest line capacity == 0
                                for line in lines:
                                    total_weighted_value[line] -= EVSE_proposed_current_3P[cp_id][0]      # Exclude from list & Remove from total weighted rated value
                            else:                                                               # IF: Smallest line capacity > 0
                                EVSE_to_adjust.append(cp_id)                                    # Add EVSE to list
                        # OTHERWISE:    If EVSE is single-phase
                        elif evse_data[cp_id]['phase'] == 'single-phase':
                            if line_cap_avail[lines] <= 0:
                                total_weighted_value[lines] -= EVSE_proposed_current_3P[cp_id][0]
                            else:
                                EVSE_to_adjust.append(cp_id)
                    else:
                        pass
            # OTHERWISE:    Exclude from Adjustable List
            else:
                if isinstance(lines, list):
                    for line in lines:
                        total_weighted_value[line] -= EVSE_proposed_current_3P[cp_id][0]                  # Remove from total weighted rated value
                else:
                    total_weighted_value[lines] -= EVSE_proposed_current_3P[cp_id][0]                  # Remove from total weighted rated value


    # (3/3) UNUSED CURRENT REDISTRIBUTION, INCLUDING CHARGING PROFILE UNDER MIN. CHARGING CURRENT:
    '''
    ---------------------------------------------------------------------------------------------------------------------------
    UNUSED CURRENT REDISTRIBUTION CRITERIA:
    1) Any Unused Current Exist (i.e., unused current is more than 0), or
    2) Any of EVSE Charging Profile is a value between 0 and 6
    3) Adjustable EVSE List is EMPTY (force stop)
    ---------------------------------------------------------------------------------------------------------------------------
    '''
    print(f'unused current: {unused_current}')
    while unused_current_exist or any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()):

        print("***************")
        logging.warning("UNUSED CURRENT EXIST OR EVSE PROPOSED CURRENT IS BETWEEN 0 AND 6")
        # CONDITION:    If there is no EVSE to adjust, break out of While-loop (protection against infinite loop)
        if not EVSE_to_adjust:
            break

        # CONDITION:    Only applied to EVSEs which are to be adjusted (ignore EVSEs which are 0A)
        #               EVSEs to be adjusted shall pop one at a time until While condition is False
        for cp_id, evse in EVSE_proposed_current_3P.items():
            
            # reset
            total_allocated_current = {'L1': 0, 'L2': 0, 'L3': 0}                 # Total current allocated to EVSEs (to be used to determine unused_current)

            if cp_id in EVSE_to_adjust:

                logging.warning(f"EVSE to adjust is: {EVSE_to_adjust}")
                ###############
                add_on_current = 0                  # Initialise add-on current to 0
                lines = evse_data[cp_id]['line']    # Get line type (i.e., L1 / L2 / L3) for each EVSE

                # CALCULATE:    (Updated) Add-on Current based off Unused Current to initial Proposed Current
                if evse_data[cp_id]['phase'] == 'three-phase':
                    # Get minimum line capacity available (positive value only)              
                    min_line_cap_avail = min(max(line_cap_avail[line], 0) for line in lines)
                    min_weighted_value = min(max(total_weighted_value[line], 0) for line in lines)
                    min_unused_current = min(max(unused_current[line], 0) for line in lines)
                    add_on_current =    min(min_line_cap_avail,
                                        ((EVSE_proposed_fixed_3P[cp_id][0] / min_weighted_value) * min_unused_current))
                    for line in lines:
                        line_cap_avail[line] += EVSE_proposed_fixed_3P[cp_id][0]                # Increase first available line capacity for all lines
                elif evse_data[cp_id]['phase'] == 'single-phase':
                    correct_line_cap_avail = line_cap_avail[lines] if line_cap_avail[lines] >= 0 else 0
                    add_on_current =    min(correct_line_cap_avail, \
                                        ((EVSE_proposed_fixed_3P[cp_id][0] / total_weighted_value[lines]) * unused_current[lines]))
                    line_cap_avail[lines] += EVSE_proposed_fixed_3P[cp_id][0]                       # Increase first available line capacity for installed line

                ###############
                logging.warning(f"Add-on current for {cp_id} is: {add_on_current}")
                ###############

                # CONDITION:    If the add-on current is less than 6A, set EVSE proposed current to 0
                # UPDATE:       Add small current to available line capacity for each installed Line
                if EVSE_proposed_current_3P[cp_id][0] < 6 and EVSE_proposed_current_3P[cp_id][0] != 0:
                    if evse_data[cp_id]['phase'] == 'three-phase':
                        for line in lines:
                            line_cap_avail[line] += EVSE_proposed_current_3P[cp_id][0]
                    elif evse_data[cp_id]['phase'] == 'single-phase':
                        line_cap_avail[lines] += EVSE_proposed_current_3P[cp_id][0]
                    if len(EVSE_to_adjust) > 1:
                        EVSE_proposed_current_3P[cp_id] = [0]                                       # Set Charging Profile to 0
                    ################
                    logging.warning(f"EVSE proposed current is less than 6A for {cp_id}")
                    ################

                # CALCULATE:    Add calculated add-on current to initial Proposed Current for each EVSE in list
                if evse_data[cp_id]['phase'] == 'three-phase':
                    EVSE_proposed_current_3P[cp_id][0] += add_on_current
                    if EVSE_proposed_current_3P[cp_id][0] > EVSE_n_max[cp_id]:
                        EVSE_proposed_current_3P[cp_id] = [EVSE_n_max[cp_id]]
                    for line in lines:
                        line_cap_avail[line] -= EVSE_proposed_current_3P[cp_id][0]                  # Remove updated proposed current from available line capacity
                        ####
                        total_allocated_current[line] += EVSE_proposed_current_3P[cp_id][0]
                elif evse_data[cp_id]['phase'] == 'single-phase': 
                    EVSE_proposed_current_3P[cp_id][0] += add_on_current
                    if EVSE_proposed_current_3P[cp_id][0] > EVSE_n_max[cp_id]:
                        EVSE_proposed_current_3P[cp_id] = [EVSE_n_max[cp_id]]
                    line_cap_avail[evse_data[cp_id]['line']] -= EVSE_proposed_current_3P[cp_id][0]  # Remove updated proposed current from available line capacity
                    ####
                    total_allocated_current[lines] += EVSE_proposed_current[cp_id][0]

                #########################
                print(f"for {cp_id}, the UPDATED proposed current (1P) is: {EVSE_proposed_current[cp_id]}")
                print(f"for {cp_id}, the UPDATED proposed current (3P) is: {EVSE_proposed_current_3P[cp_id]}")
                print("++++++++++++++++++")
                #########################

            # NO:   It means that EVSE is either not in use, or has too low of a current proposed to be used
            else:
                pass
       
        # recalculate unused current
        unused_current = {'L1': 0, 'L2': 0, 'L3': 0}
        for line in unused_current:
            unused_current[line] = math.floor((C_CP_t[line] - total_allocated_current[line]) * 10) / 10

        # CONDITION:    After calculating new Proposed Current in above, check if it fits criteria
        #               If it doesn't, remove cp_id from EVSE_to_adjust, and While-loop again
        #               Update unused current value as well
        if any(0 < current[0] < 6 for current in EVSE_proposed_current_3P.values()) or all(current[0] == 0 for current in EVSE_proposed_current_3P.values()):
            print("&&&&&&&&&&&&&&&&&")
            logging.warning("EVSE PROPOSED CURRENT IS BETWEEN 0 AND 6 exists")
            for cp_id in EVSE_to_adjust:
                lines = evse_data[cp_id]['line']
                if evse_data[cp_id]['phase'] == 'three-phase':
                    min_line = min(lines, key=line_cap_avail.get)                                   # Get the line with the minimum capacity
                    if line_cap_avail[min_line] == 0:                                               # If any of the lines is fully used
                        EVSE_to_adjust.remove(cp_id)                                                # Remove EVSE unique ID
                    else:
                        for line in lines:                                                          # If EVSE remains in list
                            line_cap_avail[line] += EVSE_proposed_current_3P[cp_id][0]              # Add EVSE proposed current available line capacity as it will reset
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

            # Update the total weighted value according to the updated adjustable EVSE list
            total_weighted_value = {'L1': 0, 'L2': 0, 'L3': 0}
            for cp_id, evse in evse_data.items():
                if cp_id in EVSE_to_adjust:
                    lines = evse['line']
                    if isinstance(lines, list):
                        for line in lines:
                            total_weighted_value[line] += EVSE_proposed_fixed_3P[cp_id][0]
                    else:
                        total_weighted_value[lines] += EVSE_proposed_fixed_3P[cp_id][0]
                    
            EVSE_proposed_current_3P_total = {'L1': 0, 'L2': 0, 'L3': 0}
            for cp_id, evse in evse_data.items():
                lines = evse['line']
                if isinstance(lines, list):
                    for line in lines:
                        EVSE_proposed_current_3P_total[line] += EVSE_proposed_current_3P[cp_id][0]
                else:
                    EVSE_proposed_current_3P_total[lines] += EVSE_proposed_current_3P[cp_id][0]
            
            for line in unused_current:
                unused_current[line] = C_CP_t[line] - EVSE_proposed_current_3P_total[line]
            
        else:
            print("@@@@ unused current is now FALSE!")
            unused_current_exist = False

        logging.warning(f"END OF WHILE LOOP!!!!")

    # Correct the values to 1 decimal place
    for cp_id, evse in EVSE_proposed_current_3P.items():
        if evse_data[cp_id]["phase"] == "three-phase":
            EVSE_proposed_current[cp_id] = [math.floor((EVSE_proposed_current_3P[cp_id][0])* 10) / 10]
        elif evse_data[cp_id]["phase"] == "single-phase":
            EVSE_proposed_current[cp_id] = [math.floor((EVSE_proposed_current_3P[cp_id][0])* 10) / 10]

    for cp_id in EVSE_proposed_current:
        EVSE_proposed_current[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 10) / 10]

    # CONVERT: From current to power
    for evse in EVSE_proposed_current_3P:
        if evse_data[evse]['evse_type'] == 'DC':
            EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[evse][0]
            EVSEpower_DC = evse_data[evse]['efficiency']/100 * EVSEpower_AC
            EVSE_proposed_power[evse] = [(math.floor(EVSEpower_DC) * 10)/10]
        elif evse_data[evse]['evse_type'] == 'AC':
            if evse_data[evse]['phase'] == 'three-phase':
                EVSEpower_AC = 1.732 * site_voltage * EVSE_proposed_current_3P[evse][0]
            elif evse_data[evse]['phase'] == 'single-phase':
                EVSEpower_AC = phase_voltage * EVSE_proposed_current_3P[evse][0]
            EVSE_proposed_power[evse] = [(math.floor(EVSEpower_AC) * 10)/10]

    logging.warning(f"Distributed Charging Capacities to each EVSE: {EVSE_proposed_current}")
    print("*****************************************************")
    logging.warning(f"EVSE Proposed Current (3P): {EVSE_proposed_current_3P}")
    # print("EVSE Proposed Current (submitted): ", EVSE_proposed_current)
    logging.warning(f"EVSE Proposed Power: {EVSE_proposed_power}")

    new_line_ev = {'L1': 0, 'L2': 0, 'L3': 0}
    new_line_total = {'L1': 0, 'L2': 0, 'L3': 0}
    # Check new load on each line
    for cp_id, evse in evse_data.items():
        line = evse['line']
        if evse['evse_status'] == 0:
            if isinstance(line, list):  # If 'line' is a list
                for key in new_line_ev:
                    new_line_ev[key] += math.floor(EVSE_proposed_current_3P[cp_id][0] * 10) / 10
            elif line in new_line_ev:  # If 'line' is a string
                new_line_ev[line] += EVSE_proposed_current_3P[cp_id][0]
    for key in new_line_ev:
        new_line_ev[key] = math.floor(new_line_ev[key] * 10) / 10
    for line in building_load.keys():
        if line in new_line_total:
            new_line_total[line] = new_line_ev[line] + building_load[line]
            print("new " + line + ": ", new_line_total[line])

    total_ev = math.floor(sum(new_line_ev.values()) * 10) / 10
    logging.warning(f"New EV Charging Current: {total_ev}")

    return EVSE_proposed_power


#########################################################################################################################################
# Example usage
# line_loads = {'L1': 100, 'L2': 120, 'L3': 150}
line_loads = {'L1': 300, 'L2': 300, 'L3': 300}
evse_data = {
    'LOSa': {'evse_max_a': 16, 'evse_meter': 8, 'evse_status' : 1, 'evse_type': 'AC', 'phase': 'single-phase', 'line': 'L1'}, 
    'LOSb': {'evse_max_a': 16, 'evse_meter': 8, 'evse_status' : 1, 'evse_type': 'AC', 'phase': 'single-phase', 'line': 'L2'},
    'LOSc': {'evse_max_a': 16, 'evse_meter': 8, 'evse_status' : 0, 'evse_type': 'AC', 'phase': 'single-phase', 'line': 'L3'},
    'LOSd': {'evse_max_a': 32, 'evse_meter': 16, 'evse_status' : 0, 'evse_type': 'AC', 'phase': 'single-phase', 'line': 'L1'},
    'LOSe-1':   {'evse_max_a': 50, 'connector_max_a': 30, 'evse_meter': 10, 'evse_status' : 0, 'evse_type': 'DC', \
                'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSe-2':   {'evse_max_a': 50, 'connector_max_a': 30, 'evse_meter': 10, 'evse_status' : 0, 'evse_type': 'DC', \
                'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSf-1':   {'evse_max_a': 100, 'connector_max_a': 60, 'evse_meter': 10, 'evse_status' : 0, 'evse_type': 'DC',  \
                'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSf-2':   {'evse_max_a': 100, 'connector_max_a': 60, 'evse_meter': 10, 'evse_status' : 0, 'evse_type': 'DC',  \
                'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSf-3':   {'evse_max_a': 100, 'connector_max_a': 30, 'evse_meter': 5, 'evse_status' : 0, 'evse_type': 'AC',  \
                'efficiency': 94, 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']},
    'LOSg': {'evse_max_a': 34, 'evse_meter': 12, 'evse_status' : 0, 'evse_type': 'AC', 'phase': 'three-phase', 'line': ['L1', 'L2', 'L3']}
}

# evse_data = {
#     'blockd-1': {'evse_max_a': 92, 'evse_meter': 8.7, 'evse_status' : 0, 'evse_type': 'AC', 'phase': 'single-phase', 'line': 'L1'}, 
#     'sm_test2-1': {'evse_max_a': 92, 'evse_meter': 0, 'evse_status' : 0, 'evse_type': 'AC', 'phase': 'single-phase', 'line': 'L1'}, 

# }

redistributed_evse_data = redistribute_charging_capacity(evse_data, line_loads)
print(redistributed_evse_data)
