EVSE_proposed_current = {'LOSa' : [10],
                         'LOSb' : [10],
                         'LOSc' : [0],
                         'LOSd' : [2],
                         'LOSe' : [5],
                         'LOSf' : [3],
                        }

# 1: Calculate total current required
total_req_current = sum(max(0,6 - value[0]) for value in EVSE_proposed_current.values())
print(total_req_current)