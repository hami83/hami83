# import libraries
import math
import copy


def test():
            #############################################################################
            # Conduct EV Charging Control / Change in Charging Profile (CP)
            #############################################################################

            """
            FUNCTIONS & VARIABLES DEFINITION
            EV_state_t              Status of EVSEs (Fully Charged/Not Charging (fault) = 1, Otherwise = 0)
            EVSE_Max_t              Max. Charging Current for each EVSE
            EVSE_Max_Total_t        Total Max. Charging Current for all EVSEs in USE at time t
            EVSE_proposed_rates     Proposed Charging Rate (%) for each EVSE
            EVSE_proposed_current   Proposed Charging Current (A) for each EVSE

            """
            print(f"Charging Profile shall be Updated!")   

            evse_actual_cp =    {'LOSa' : {'evse_meter': [10]},
                                 'LOSb' : {'evse_meter': [10]},
                                 'LOSc' : {'evse_meter': [0]},
                                 'LOSd' : {'evse_meter': [2]},
                                 'LOSe' : {'evse_meter': [5]},
                                 'LOSf' : {'evse_meter': [3]},
                                }

            EVSE_proposed_current = {'LOSa' : [10],
                                     'LOSb' : [10],
                                     'LOSc' : [0],
                                     'LOSd' : [2],
                                     'LOSe' : [5],
                                     'LOSf' : [3],
                                    }
            print(f"Initial Distributed Charging Capacities to each EVSE: ", EVSE_proposed_current)

            ###################
            ### UPDATED: TO CONFIRM IF THIS WORKS
            # CHECK & RECALCULATE: If the proposed current is less than the minimal current for EVSE charging
            unused_current = 0                                          # Initialise unused current for redistribution
            EVSE_to_adjust = []                                         # Initialise list of EVSEs for current adjustment (if falls below min. current)
            EVSE_proposed_wo_0 = {cp_id: copy.deepcopy(evse) for cp_id, evse in EVSE_proposed_current.items()}   # Storage reference of previously calculated proposed current values
            # EVSE_proposed_wo_0 = {cp_id: evse[:] for cp_id, evse in EVSE_proposed_current.items()}
            print("======")
            print("Fixed EVSE proposed current is: ", EVSE_proposed_wo_0)
            print("======")
            
            # CALCULATE:    Total weighted value for EVSE proposed current
            total_weighted_value = sum([EVSE_proposed_wo_0[cp_id][0] for cp_id in EVSE_proposed_wo_0])
            print(f"Total weighted value is: {total_weighted_value}")
            
            # CALCULATE:    Potential unused current & sort out to adjustable EVSE list
            if any(0 < current[0] < 6 for current in EVSE_proposed_current.values()):
                for cp_id, evse in EVSE_proposed_current.items():
                    for current in evse:
                        if current < 6 and current != 0:
                            unused_current += current
                            EVSE_to_adjust.append(cp_id)
                        elif current >= 6:
                            EVSE_to_adjust.append(cp_id)
                fixed_unused_current = unused_current
                print("Unused Current: ", unused_current)
                print("EVSEs to adjust includes: ", EVSE_to_adjust)

            # ISSUE PRESENT
            # FLAG INITIALISATION:  Unused current availability (Boolean)
            if unused_current > 0:
                unused_current_exist = True
            else:
                unused_current_exist = False

            # CONDITION:    As long as there is Unused Current leftover
            #               OR any of EVSE Proposed Current in each EVSE (cp_id) is between 0 and 6
            while unused_current_exist == True or any(0 < current[0] < 6 for current in EVSE_proposed_current.values()):
                print("______________________")

                for cp_id, evse in EVSE_proposed_current.items():

                    # Only applied to EVSEs which are to be adjusted (ignore EVSEs which are 0A)
                    # EVSEs to be adjusted shall pop one at a time until While condition is False
                    if cp_id in EVSE_to_adjust:
                        
                        # CALCULATE:    Add potentially Unused Current to Proposed Current
                        add_on_current = (EVSE_proposed_wo_0[cp_id][0] / total_weighted_value) * fixed_unused_current
                        if EVSE_proposed_current[cp_id][0] < 6 and EVSE_proposed_current[cp_id][0] != 0:
                            EVSE_proposed_current[cp_id] = [0]              # EVSEs used in unused_current shall be 0 
                        EVSE_proposed_current[cp_id][0] += add_on_current   # Add weighted leftover current to proposed current for cp_id
                        unused_current -= add_on_current                    # Removed added-on current from unused_current pool
                        
                        print("++++++++++") 
                        print(EVSE_proposed_wo_0)
                        print("+++++++++++++")
                        
                        if unused_current == 0:
                            unused_current_exist = False
                    # NO:   It means that EVSE is either not in use, or has too low of a current proposed to be used
                    else:
                        EVSE_proposed_current[cp_id][0] = 0
                
                print("Updated Proposed EVSE Current: ", EVSE_proposed_current)
      
                # CONDITION:    After calculating new Proposed Current in above, check if it fits criteria
                #               If it doesn't, remove cp_id from EVSE_to_adjust, and While-loop again
                if any(0 < current[0] < 6 for current in EVSE_proposed_current.values()):
                    unused_current = fixed_unused_current               # Reset unused current to initial unused current value
                    unused_current_exist = True                         # Unused current now exists (While-loop remains True)
                    print("EVSE fixed value should be :", EVSE_proposed_wo_0)
                    EVSE_proposed_current = EVSE_proposed_wo_0.copy()   # EVSE proposed current shall reset to initial proposed values

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
                    total_weighted_value = sum([EVSE_proposed_wo_0[cp_id][0] for cp_id in EVSE_to_adjust])
                else:
                    unused_current_exist = False

                print("Is there any unused current?: ", unused_current)
                print("new total weight: ", total_weighted_value)
                print("To adjust: ",EVSE_to_adjust)

            #######

            for cp_id in EVSE_proposed_current:
                EVSE_proposed_current[cp_id] = [math.floor(EVSE_proposed_current[cp_id][0] * 10) / 10]

            print(f"Updated Distributed Charging Capacities to each EVSE: {EVSE_proposed_current}")

            return 
            # return EVSE_proposed_current


test()

# EVSE_proposed_current = {'LOSa' : [10],
#                             'LOSb' : [10],
#                             'LOSc' : [0],
#                             'LOSd' : [2],
#                             'LOSe' : [5],
#                             'LOSf' : [3],
#                         }

# min_cp_id = None
# min_evse = float('inf') # Initialise with a very large number

# unused_current = 0
# EVSE_to_adjust = []
# for cp_id, evse in EVSE_proposed_current.items():
#     for current in evse:
#         if current < 6 and current != 0:
#             unused_current += current
#             EVSE_to_adjust.append(cp_id)
#         elif current >= 6:
#             EVSE_to_adjust.append(cp_id)
# print(EVSE_to_adjust)

# if any(0 < current[0] < 6 for current in EVSE_proposed_current.values()):
                    
#     min_cp_id = None
#     min_evse = float('inf') # Initialise with a very large number

#     for evse in EVSE_to_adjust:
#         if evse in EVSE_proposed_current and EVSE_proposed_current[evse][0] < min_evse:
#             min_cp_id = evse
#             min_evse = EVSE_proposed_current[evse][0]

#     if min_cp_id is not None:
#         EVSE_to_adjust.remove(min_cp_id)
# print(EVSE_to_adjust)



# # min_cp_id_in_list = min(min_cp_id, cp_id=lambda x: EVSE_to_adjust.index(x))
# # print(min_cp_id_in_list)