from flask import request,jsonify
from database import connect_db_fromCSMS, connect_db_toCSMS, close_db
import requests
import logging

def receive_evse_data():
    data = request.json['data']
    logging.info(f"evse data recieved from CSMS is {data}")
    conn, c = connect_db_fromCSMS()
    c.execute('CREATE TEMPORARY TABLE temp_evse_data (cp_id TEXT, evse_max_a TEXT, evse_meter TEXT, evse_status TEXT)') # Create temporary table

    for item in data:
        cp_id = item['cp_id']
        evse_max_a = item['value']
        print(f'cp_id: {cp_id}, rated A: {evse_max_a} A')
        c.execute('REPLACE INTO temp_evse_data (cp_id, evse_max_a) VALUES (?, ?)', (cp_id, evse_max_a)) # Insert data into table

    c.execute('DELETE FROM evse_data WHERE cp_id NOT IN (SELECT cp_id FROM temp_evse_data)') # Delete rows in original table that do not exist in temporary table
    c.execute('INSERT OR REPLACE INTO evse_data SELECT * FROM temp_evse_data') # Insert or replace rows in original table from temporary table
    c.execute('DROP TABLE temp_evse_data') # Drop temporary table
    c.execute('UPDATE evse_data SET evse_status = 1') # First, set all evse_status values to 1
    close_db(conn)
   
    return jsonify(command="evse data received",category="success",status=200)

def receive_evse_meter():
    data = request.json['data']
    logging.info(f"evse meter value recieved from CSMS is {data}")
    conn, c = connect_db_fromCSMS()
    c.execute('UPDATE evse_data SET evse_meter = NULL') # First, set all evse_meter values to null
    c.execute('UPDATE evse_data SET evse_status = 1') # First, set all evse_status values to 1

    for item in data:
        cp_id = item['cp_id']
        evse_meter = item['value']
        print(f'cp_id: {cp_id}, meter value: {evse_meter} A')
        c.execute('UPDATE evse_data SET evse_meter = ?, evse_status = 0 WHERE cp_id = ?', (evse_meter, cp_id)) # Update evse_meter and evse_status in table for the given cp_id

    close_db(conn)

    return jsonify(command="meter value received",category="success",status=200)

def print_table_values():
    conn, c = connect_db_toCSMS()

    # Execute SELECT query
    c.execute('SELECT EVSE, TIME_10 FROM evse_actual')
    rows = c.fetchall()

    # Iterate over the result and print in the desired format
    for row in rows:
        print(f'{row[0]} {row[1]}')

    close_db(conn)

    return jsonify(command="meter value received",category="success",status=200)
   
def hard_code(): # This function is used to set the charging profile manually
    headers = {'Authorization': 'eyJraWQiOiJhWHJRMzkrNk05NVlnNnY2aWdWMjBcL21BbDJwaW53SldpNk5GTzFhYXRkdz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI0NDc5ZTYyMS0wYmMyLTRjN2EtYjE5Ny0zZGJkM2E1YzNmNGEiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLmFwLXNvdXRoZWFzdC0xLmFtYXpvbmF3cy5jb21cL2FwLXNvdXRoZWFzdC0xX2EwbFBja3NNViIsImNvZ25pdG86dXNlcm5hbWUiOiI0NDc5ZTYyMS0wYmMyLTRjN2EtYjE5Ny0zZGJkM2E1YzNmNGEiLCJjdXN0b206dGVuYW50X2lkIjoidGVzdGIiLCJvcmlnaW5fanRpIjoiMzU3MDNiNzQtY2Q4My00YTgwLTlmMDctOGU0NTllMDFiNDUyIiwiYXVkIjoiN2FvOW9mM2k3am1zZmtkMDN1YXI1YnVwbGsiLCJldmVudF9pZCI6ImVhMzBjZWM0LTRkYzQtNDkyMy04OTQzLWRlOTU4YTVlMTBhNCIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzA1Mzk2NTc1LCJuYW1lIjoiVEVTVEItU3VwZXJBZG1pbiIsImV4cCI6MTcwNTQzNDk3NSwiY3VzdG9tOnJvbGUiOiJTdXBlckFkbWluIiwiaWF0IjoxNzA1Mzk2NTc1LCJqdGkiOiI1NzU4NzJiMy05OGJkLTQ3ZDctYTU4OS03NzM5Y2VmNmQ0MDAiLCJlbWFpbCI6ImNzbXMwMkBzbmFwbWFpbC5jYyJ9.eHvA40XCvuMs8xxppkrIpGNS1NHPEEuHowRqgOQtHOVP5IGb7pL5E8NpsT_ZziyTJOmjbPIZ1704WhWR0A7xRFLnKRXr2TcHQhPk0zeGuPEZGh5h6efOFwmAZKySoa3Gfb1N6IwbXsqOtBfsWwPgXY3RmE8-wc-PM5HMWcDFcWkKBJM1GAglx_qutzPnymxSqDnJzuLEHoVR9zZgZVeLfu7_NC1zSRtTKRAxJiJlF09xFFyl6EbmysVpGkgtoH0qDF1nM0ECauEPZYDHLrVy9KRk0Loq-bF6nbhiiJujcQWzuLVQnL6ol7Db8poRgWNu-l3NFiHVKzpOzdKDKOFxfQ'}  # Replace 'your_token' with your actual token
    body = {
        "charge_point_id":"LOSc",
        "connector_id":1,
        "cs_charging_profiles":{
            "charging_profile_id": 1,
            "charging_profile_purpose":"TxProfile",
            "charging_profile_kind":"Absolute",
            "stack_level":1,
            "charging_schedule":{
                "charging_rate_unit":"A",
                "charging_schedule_period":[{
                    "start_period":1,
                    "limit":16.0
                }]
            }
        }
    }
    print(body)
    response = requests.post('https://iuwml0f5l1.execute-api.ap-southeast-1.amazonaws.com/dev/ocpp/set_charging_profile',headers=headers, json=body)  # Replace with your API URL
    data = response.json()
    
    return data

def dlm_mock_data():
    conn, c = connect_db_toCSMS()

    # Clear all current data
    c.execute('DELETE FROM evse_actual')

    # Data to be inserted
    data = [('LOSc', 8), ('LOSb', 10)]

    # Execute INSERT query
    c.executemany('INSERT INTO evse_actual (EVSE, TIME_10) VALUES (?, ?)', data)
    
    close_db(conn)

# def post_api():
#     conn, c = connect_db_toCSMS()

#     # Execute SELECT query
#     c.execute('SELECT CP_ID, TIME_10 FROM DLM_CURRENT')
#     rows = c.fetchall()

#     counter = 1

#     responses = [] # Initialize a list to store the responses

#     # Iterate over the result and print in the desired format
#     for row in rows:
#         headers = {'Authorization': 'eyJraWQiOiJhWHJRMzkrNk05NVlnNnY2aWdWMjBcL21BbDJwaW53SldpNk5GTzFhYXRkdz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxOTdhNTVkYy04MGYxLTcwYzEtZGYyMC03NDJkMWY3NzFkZDIiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLmFwLXNvdXRoZWFzdC0xLmFtYXpvbmF3cy5jb21cL2FwLXNvdXRoZWFzdC0xX2EwbFBja3NNViIsImNvZ25pdG86dXNlcm5hbWUiOiIxOTdhNTVkYy04MGYxLTcwYzEtZGYyMC03NDJkMWY3NzFkZDIiLCJjdXN0b206dGVuYW50X2lkIjoiY3NtcyIsIm9yaWdpbl9qdGkiOiI4NTdjNDlmMy0wMzBmLTRkZjgtODhkOC0xMzFjMTkyMzdlNTMiLCJhdWQiOiI3YW85b2YzaTdqbXNma2QwM3VhcjVidXBsayIsImV2ZW50X2lkIjoiZjYyOTU0NDAtYzA1Ni00ZDI1LThmZTMtZGNjNmNlYjJlMTRmIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE3MDcwOTcyNTEsIm5hbWUiOiJiYTMzNjMyMy05ZjU2LTRhNGUtYTBkYy1mODkyZDU0NTZlYjIiLCJleHAiOjE3MDcxMzU2NTEsImN1c3RvbTpyb2xlIjoiU3VwZXJBZG1pbiIsImlhdCI6MTcwNzA5NzI1MSwianRpIjoiOGFiZTY2NjktNmE2Ni00MzA4LTliNmEtNmY0YjFjMWI5NzIwIiwiZW1haWwiOiJiZW5qaW4ubGF1QGxpdGVvbi5jb20ifQ.SKq3vwS3IJVHBBoaen-2A2zjrUKfCeFLAwHGGF7eTkpZ_o9CB3jGIzTCjBGAvoECM8uLsaDawetlAVkYhwIkZZV0z2DaY2vKZgpzVRNyAGBgyFafBvWycLzDWsEx_nPLbJKMNNcnlDMsnQnoUNRNZwtMov3w26eggOmabzTLDhsCPW1Yz_HIF9vyETTXsfBGM9A4MbVkT4Qci1Snz9ylvMATnWbh70RpM4dXJjNOn-oGUkpZCt_oNUVHyV_wJT4belUm-6Dolr5-cM7kUK5sq3jucpbbhwoA5mEnHODPqAgJcfGHvoekYEZ8tP4cicAzyB1wLl8CwFsBUC846VF49Q'
# }  # Replace 'your_token' with your actual token
#         body = {
#             "charge_point_id": row[0],
#             "connector_id":1,
#             "cs_charging_profiles":{
#                 "charging_profile_id": counter,
#                 "charging_profile_purpose":"TxProfile",
#                 "charging_profile_kind":"Absolute",
#                 "stack_level":1,
#                 "charging_schedule":{
#                     "charging_rate_unit":"A",
#                     "charging_schedule_period":[{
#                         "start_period":1,
#                         "limit":row[1]
#                     }]
#                 }
#             }
#         }
#         counter += 1
#         print(body)
#         response = requests.post('https://iuwml0f5l1.execute-api.ap-southeast-1.amazonaws.com/dev/ocpp/set_charging_profile',headers=headers, json=body)  # Replace with your API URL
#         data = response.json()

#         responses.append(data) # Add the response to the list

#     close_db(conn)
    
#     # body2 = [{"cp_id": row[0], "value": row[1]}]

#     # manual_evse_meter(body2)
    
    # return data

# def post_api(): # This function is used to set the charging profile manually
#     headers = {'Authorization': 'eyJraWQiOiJhWHJRMzkrNk05NVlnNnY2aWdWMjBcL21BbDJwaW53SldpNk5GTzFhYXRkdz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiI0NDc5ZTYyMS0wYmMyLTRjN2EtYjE5Ny0zZGJkM2E1YzNmNGEiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLmFwLXNvdXRoZWFzdC0xLmFtYXpvbmF3cy5jb21cL2FwLXNvdXRoZWFzdC0xX2EwbFBja3NNViIsImNvZ25pdG86dXNlcm5hbWUiOiI0NDc5ZTYyMS0wYmMyLTRjN2EtYjE5Ny0zZGJkM2E1YzNmNGEiLCJjdXN0b206dGVuYW50X2lkIjoidGVzdGIiLCJvcmlnaW5fanRpIjoiNGFlYWZlZWQtOTJjZC00YWVkLWIzNjUtZWI0NjNkMTAwMWU4IiwiYXVkIjoiN2FvOW9mM2k3am1zZmtkMDN1YXI1YnVwbGsiLCJldmVudF9pZCI6IjYyZDBiYmFmLWY0MjAtNGI4Yy04NWM5LTQwMGM5M2FkZjcxZiIsInRva2VuX3VzZSI6ImlkIiwiYXV0aF90aW1lIjoxNzA1Mjg4Mjc0LCJuYW1lIjoiVEVTVEItU3VwZXJBZG1pbiIsImV4cCI6MTcwNTMyNjY3NCwiY3VzdG9tOnJvbGUiOiJTdXBlckFkbWluIiwiaWF0IjoxNzA1Mjg4Mjc0LCJqdGkiOiIwNGJhMTViYi0xNzgxLTRjYzgtYjRmZi1kYzhmMmM4MDVkYmYiLCJlbWFpbCI6ImNzbXMwMkBzbmFwbWFpbC5jYyJ9.VuavmqF8vjHZwTkKSSymByPf3yK1lupIGImJs4d8S3r8CNjjDWZFDezRO1pldN1WpfQZNMgWmpmPaSOeTP2uztKQU14xO5KRhd2m5zUKViq8LZaQmX9v6ktboKPMJLW9CjyELk-ZtmB-vWv3-n5_LgnrbchbBYfrBEmQm_6SmYi1zXqsI-lBu1Zl7DuOwhQy0v1PpKR1BS9koBsUxqi0Pe6hkvFfS2WCfMZ2WlL75x8DL7nw1nNmJK71sLQYXPsVBl_KpJocZG7aamJxYk0zCcUO76gqXhguvJp_ciNa6JWZQsji3YgZTCYZDfVksESGiNMPIU3O2skJtyMVZV-f0A'}  # Replace 'your_token' with your actual token
#     body = {
#         "charge_point_id":"LOSc",
#         "connector_id":1,
#         "cs_charging_profiles":{
#             "charging_profile_id": 1,
#             "charging_profile_purpose":"TxProfile",
#             "charging_profile_kind":"Absolute",
#             "stack_level":1,
#             "charging_schedule":{
#                 "charging_rate_unit":"A",
#                 "charging_schedule_period":[{
#                     "start_period":1,
#                     "limit":10.0
#                 }]
#             }
#         }
#     }
#     print(body)
#     response = requests.post('https://iuwml0f5l1.execute-api.ap-southeast-1.amazonaws.com/dev/ocpp/set_charging_profile',headers=headers, json=body)  # Replace with your API URL
#     data = response.json()
    
#     return data
    
def post_api(EVSE_proposed_current):

    counter = 1

    responses = [] # Initialize a list to store the responses

    # Iterate over the EVSE_proposed_current dictionary
    for charge_point_id, limit in EVSE_proposed_current.items():
        limit = limit[0]  # Get the first item from the list

        headers = {'Authorization': 'eyJraWQiOiJhWHJRMzkrNk05NVlnNnY2aWdWMjBcL21BbDJwaW53SldpNk5GTzFhYXRkdz0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxOTdhNTVkYy04MGYxLTcwYzEtZGYyMC03NDJkMWY3NzFkZDIiLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiaXNzIjoiaHR0cHM6XC9cL2NvZ25pdG8taWRwLmFwLXNvdXRoZWFzdC0xLmFtYXpvbmF3cy5jb21cL2FwLXNvdXRoZWFzdC0xX2EwbFBja3NNViIsImNvZ25pdG86dXNlcm5hbWUiOiIxOTdhNTVkYy04MGYxLTcwYzEtZGYyMC03NDJkMWY3NzFkZDIiLCJjdXN0b206dGVuYW50X2lkIjoiY3NtcyIsIm9yaWdpbl9qdGkiOiI4NTdjNDlmMy0wMzBmLTRkZjgtODhkOC0xMzFjMTkyMzdlNTMiLCJhdWQiOiI3YW85b2YzaTdqbXNma2QwM3VhcjVidXBsayIsImV2ZW50X2lkIjoiZjYyOTU0NDAtYzA1Ni00ZDI1LThmZTMtZGNjNmNlYjJlMTRmIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE3MDcwOTcyNTEsIm5hbWUiOiJiYTMzNjMyMy05ZjU2LTRhNGUtYTBkYy1mODkyZDU0NTZlYjIiLCJleHAiOjE3MDcxMzU2NTEsImN1c3RvbTpyb2xlIjoiU3VwZXJBZG1pbiIsImlhdCI6MTcwNzA5NzI1MSwianRpIjoiOGFiZTY2NjktNmE2Ni00MzA4LTliNmEtNmY0YjFjMWI5NzIwIiwiZW1haWwiOiJiZW5qaW4ubGF1QGxpdGVvbi5jb20ifQ.SKq3vwS3IJVHBBoaen-2A2zjrUKfCeFLAwHGGF7eTkpZ_o9CB3jGIzTCjBGAvoECM8uLsaDawetlAVkYhwIkZZV0z2DaY2vKZgpzVRNyAGBgyFafBvWycLzDWsEx_nPLbJKMNNcnlDMsnQnoUNRNZwtMov3w26eggOmabzTLDhsCPW1Yz_HIF9vyETTXsfBGM9A4MbVkT4Qci1Snz9ylvMATnWbh70RpM4dXJjNOn-oGUkpZCt_oNUVHyV_wJT4belUm-6Dolr5-cM7kUK5sq3jucpbbhwoA5mEnHODPqAgJcfGHvoekYEZ8tP4cicAzyB1wLl8CwFsBUC846VF49Q'}  # Replace 'your_token' with your actual token
        body = {
            "charge_point_id": charge_point_id,
            "connector_id":1,
            "cs_charging_profiles":{
                "charging_profile_id": counter,
                "charging_profile_purpose":"TxProfile",
                "charging_profile_kind":"Absolute",
                "stack_level":1,
                "charging_schedule":{
                    "charging_rate_unit":"A",
                    "charging_schedule_period":[{
                        "start_period":1,
                        "limit":limit
                    }]
                }
            }
        }
        counter += 1
        print(body)
        response = requests.post('https://iuwml0f5l1.execute-api.ap-southeast-1.amazonaws.com/dev/ocpp/set_charging_profile',headers=headers, json=body)  # Replace with your API URL
        data = response.json()

        responses.append(data) # Add the response to the list
    
    return responses

def manual_evse_meter(body2):
    conn, c = connect_db_fromCSMS()
    c.execute('UPDATE evse_data SET evse_meter = NULL') # First, set all evse_meter values to null
    c.execute('UPDATE evse_data SET evse_status = 1') # First, set all evse_status values to 1

    for item in body2:
        cp_id = item['cp_id']
        evse_meter = item['value']
        print(f'cp_id: {cp_id}, meter value: {evse_meter} A')
        c.execute('UPDATE evse_data SET evse_meter = ?, evse_status = 0 WHERE cp_id = ?', (evse_meter, cp_id)) # Update evse_meter and evse_status in table for the given cp_id

    close_db(conn)

    return {"command": "meter value received", "category": "success", "status": 200}