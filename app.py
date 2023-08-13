from flask import Flask, render_template, jsonify, session, request
import requests
import urllib3
import pandas as pd
import numpy as np

app = Flask(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app.secret_key = '12345'

def request_access_token(client_id, client_secret, refresh_token):
    auth_url = "https://www.strava.com/oauth/token"
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
        'f': 'json'
    }
    print("\nRequesting Access Token...")
    res = requests.post(auth_url, data=payload, verify=False)
    access_token = res.json()['access_token']
    print(f"\nAccess Token = {access_token}")
    return access_token

def get_activity_data(access_token):
    print("\nGetting Activity Data...")
    activities_url = "https://www.strava.com/api/v3/athlete/activities"
    header = {'Authorization': 'Bearer ' + access_token}
    request_page_num = 1
    all_activities_list = []
    while True:
        param = {'per_page': 200, 'page': request_page_num}
        get_activities = requests.get(activities_url, headers=header,params=param).json()
        if len(get_activities) == 0:
            break
        all_activities_list.extend(get_activities)
        request_page_num += 1
        all_activities_df = pd.DataFrame(all_activities_list)
    return all_activities_df, all_activities_list

def get_segments_list(bounds, access_token):
    print("\nGetting Segment Data...")
    segments_url = "https://www.strava.com/api/v3/segments/explore"
    header = {'Authorization': 'Bearer ' + access_token}
    param = {'bounds': ','.join(str(coord) for coord in bounds)}
    get_segments = requests.get(segments_url, headers=header, params=param).json()
    all_segments = pd.DataFrame(get_segments)
    normalized_data = pd.json_normalize(all_segments['segments'])
    all_segments_df = pd.concat([all_segments, normalized_data], axis=1)
    all_segments_df.drop(columns=['segments'], inplace=True)
    return all_segments_df

def get_start_end_dates(data_frame):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    if start_date != None:
        start_date = pd.to_datetime(start_date).tz_localize('UTC')
    else:
        start_date = data_frame['start_date_formatted'].min()

    if end_date != None:
        end_date = pd.to_datetime(end_date).tz_localize('UTC')
    else:
        end_date = data_frame['start_date_formatted'].max()

    return start_date, end_date

def calculate_recent_activity_stats(data_frame):
    date = data_frame.loc[0, 'start_date']
    name = data_frame.loc[0, 'name']
    type = data_frame.loc[0, 'type']
    distance = round(data_frame.loc[0, 'distance'] / 1000, 1)

    return(
        date,
        name,
        type,
        distance,
    )

def calculate_lifetime_stats(data_frame, start_date, end_date):
    data_frame['heart_beats'] = data_frame['average_heartrate'] * data_frame['moving_time']
    filtered_activities = data_frame.loc[(data_frame['start_date_formatted'] >= start_date) & (data_frame['start_date_formatted'] <= end_date)]
    kudos_received = filtered_activities['kudos_count'].sum()
    heart_beats = filtered_activities['heart_beats'].sum()
    distance_travelled = filtered_activities['distance'].sum() / 1000
    elevation_gained = filtered_activities['total_elevation_gain'].sum()

    times_around_earth = distance_travelled / 40075 # circumference of earth
    blood_pumped = heart_beats * 0.07 # average volume of blood pumped per beat
    times_up_everest = elevation_gained / 8848 # height of Mt Everest

    return(
        kudos_received,
        '{:,}'.format(round(heart_beats)),
        '{:,}'.format(round(distance_travelled)),
        '{:,}'.format(round(elevation_gained)),
        '{:,}'.format(round(blood_pumped)),
        round(times_around_earth, 2),
        round(times_up_everest, 1)
    )

def format_speed(avg_speed):
    integer_part = int(avg_speed)
    decimal_part = avg_speed - integer_part
    seconds = int(decimal_part * 60)
    avg_speed_formatted = f"{integer_part}:{seconds}"
    return avg_speed_formatted

def calculate_activity_stats(data_frame, start_date, end_date, type, sport_type=None, commute=False):
    if sport_type is None:
        sport_type = type

    filtered_activities_date = data_frame.loc[(data_frame['start_date_formatted'] >= start_date) & (data_frame['start_date_formatted'] <= end_date)]
    filtered_activities = filtered_activities_date[(filtered_activities_date['sport_type'] == sport_type) & (filtered_activities_date['commute'] == commute)]

    total_count = len(filtered_activities)
    total_distance = filtered_activities['distance'].sum() / 1000 # conversion to km
    total_elevation = filtered_activities['total_elevation_gain'].sum()
    max_speed_kmh = filtered_activities['max_speed'].max() * 3.6 # conversion to km/h
    avg_speed_kmh = filtered_activities['average_speed'].mean() * 3.6 # conversion to km/h
    avg_speed_minkm = (1 / 0.06) / filtered_activities['average_speed'].mean() # conversion to min/km
    avg_speed_min100m = (1 / 0.6) / filtered_activities['average_speed'].mean() # conversion to min/100m
    avg_power = filtered_activities['average_watts'].mean()
    avg_distance = filtered_activities['distance'].mean() / 1000 # conversion to km
    avg_elevation = filtered_activities['total_elevation_gain'].mean()
    avg_hr = filtered_activities['average_heartrate'].mean()

    total_count = np.nan_to_num(total_count)
    total_distance = np.nan_to_num(total_distance)
    total_elevation = np.nan_to_num(total_elevation)
    max_speed_kmh = np.nan_to_num(max_speed_kmh)
    avg_speed_kmh = np.nan_to_num(avg_speed_kmh)
    avg_speed_minkm = np.nan_to_num(avg_speed_minkm)
    avg_speed_min100m = np.nan_to_num(avg_speed_min100m)
    avg_power = np.nan_to_num(avg_power)
    avg_distance = np.nan_to_num(avg_distance)
    avg_elevation = np.nan_to_num(avg_elevation)
    avg_hr = np.nan_to_num(avg_hr)

    avg_speed_minkm_formatted = format_speed(avg_speed_minkm)
    avg_speed_min100m_formatted = format_speed(avg_speed_min100m)

    if (type == 'Ride') or (type == 'VirtualRide'):
        return(
        total_count, 
        round(total_distance, 1), 
        round(total_elevation, 1),
        round(max_speed_kmh, 1), 
        round(avg_speed_kmh, 1), 
        round(avg_power, 1), 
        round(avg_distance, 1), 
        round(avg_elevation, 1),
        round(avg_hr, 1)
    )
    elif (type == 'Run') or (type == 'VirtualRun'):
         return(
        total_count, 
        round(total_distance, 1), 
        round(total_elevation, 1), 
        avg_speed_minkm_formatted, 
        round(avg_power, 1), 
        round(avg_distance, 1), 
        round(avg_elevation, 1),
        round(avg_hr, 1)
    )
    elif type == 'Hike':
        return(
        total_count, 
        round(total_distance, 1), 
        round(total_elevation, 1), 
        avg_speed_minkm_formatted, 
        round(avg_distance, 1), 
        round(avg_elevation, 1),
        round(avg_hr, 1)
    )
    elif type == 'Swim':
        return(
        total_count,
        round(total_distance, 1), 
        avg_speed_min100m_formatted, 
        round(avg_distance, 1), 
        round(avg_hr, 1)
    )
    elif (type == 'AlpineSki') or (type == 'NordicSki'):
        return(
        total_count, 
        round(total_distance, 1), 
        round(total_elevation, 1), 
        round(max_speed_kmh, 1),
        round(avg_speed_kmh, 1), 
        round(avg_distance, 1), 
        round(avg_elevation, 1),
        round(avg_hr, 1)
    )

def count_other_sport_types(data_frame):
    standard_sport_types = ['Ride', 'MountainBikeRide', 'VirtualRide', 'Run', 'VirtualRun', 'Hike', 'Swim', 'AlpineSki', 'NordicSki']
    filtered_activities = data_frame[~data_frame['sport_type'].isin(standard_sport_types)]
    sport_type_counts = filtered_activities['sport_type'].value_counts().to_dict()
    formatted_other_sport_types = '<br><br>'.join([f"{key}: {value}" for key, value in sport_type_counts.items()])
    return formatted_other_sport_types

# Introduction
print("\nWelcome to the Strava API Test App")
client_id = '111595'
client_secret = '8e8f246270159ece4b0eb3c75e494241bad86027'
refresh_token = '8285947a1614c22ebf0a7308cafb267ed4d9426f'

bounds = [51.036047, -114.150184, 51.054738, -114.111313]

access_token = request_access_token(client_id, client_secret, refresh_token)
all_activities, all_activities_list = get_activity_data(access_token)
all_segments = get_segments_list(bounds, access_token)

all_activities['start_date_formatted'] = pd.to_datetime(all_activities['start_date'], format='%Y-%m-%d')

@app.route('/')
def index():

    # Getting start end end date from web page
    start_date, end_date = get_start_end_dates(all_activities)
    session['start_date'] = start_date
    session['end_date'] = end_date

    # Lifetime Stats
    l1, l2, l3, l4, l5, l6, l7 = calculate_lifetime_stats(all_activities, start_date, end_date)

    # Most recent activity stats
    ra1, ra2, ra3, ra4 = calculate_recent_activity_stats(all_activities)

    # Ride stats
    r1, r2, r3, r4, r5, r6, r7, r8, r9 = calculate_activity_stats(all_activities, start_date, end_date, 'Ride')
    c1, c2, c3, c4, c5, c6, c7, c8, c9 = calculate_activity_stats(all_activities, start_date, end_date, 'Ride', 'Ride', True)
    m1, m2, m3, m4, m5, m6, m7, m8, m9 = calculate_activity_stats(all_activities, start_date, end_date, 'Ride', 'MountainBikeRide')
    v1, v2, v3, v4, v5, v6, v7, v8, v9 = calculate_activity_stats(all_activities, start_date, end_date, 'VirtualRide')

    # Run/Hike stats
    or1, or2, or3, or4, or5, or6, or7, or8 = calculate_activity_stats(all_activities, start_date, end_date, 'Run')
    vr1, vr2, vr3, vr4, vr5, vr6, vr7, vr8 = calculate_activity_stats(all_activities, start_date, end_date, 'VirtualRun')
    h1, h2, h3, h4, h5, h6, h7 = calculate_activity_stats(all_activities, start_date, end_date, 'Hike')

    # Other Stats
    s1, s2, s3, s4, s5 = calculate_activity_stats(all_activities, start_date, end_date, 'Swim')
    as1, as2, as3, as4, as5, as6, as7, as8 = calculate_activity_stats(all_activities, start_date, end_date, 'AlpineSki')
    ns1, ns2, ns3, ns4, ns5, ns6, ns7, ns8 = calculate_activity_stats(all_activities, start_date, end_date, 'NordicSki')
    other_sport_types = count_other_sport_types(all_activities)

    return render_template('index.html',
        start_date=start_date, end_date=end_date,
        kudos_received=l1, heart_beats=l2, distance_travelled=l3, elevation_gained=l4, blood_pumped=l5, times_around_earth=l6, times_up_everest=l7,
        date=ra1, name=ra2, type=ra3, distance=ra4, 
        total_rides=r1, total_ride_distance=r2, total_ride_elevation=r3, max_ride_speed=r4, avg_ride_speed=r5, avg_ride_power=r6, avg_ride_distance=r7, avg_ride_elevation=r8, avg_ride_hr=r9, 
        total_commutes=c1, total_commute_distance=c2,total_commute_elevation=c3, max_commute_speed=c4, avg_commute_speed=c5, avg_commute_power=c6, avg_commute_distance=c7, avg_commute_elevation=c8, avg_commute_hr=c9,
        total_mtb=m1, total_mtb_distance=m2, total_mtb_elevation=m3, max_mtb_speed=m4, avg_mtb_speed=m5, avg_mtb_power=m6, avg_mtb_distance=m7, avg_mtb_elevation=m8, avg_mtb_hr=m9,
        total_virtual_rides=v1, total_virtual_ride_distance=v2, total_virtual_ride_elevation=v3, max_virtual_ride_speed=v4, avg_virtual_ride_speed=v5, avg_virtual_ride_power=v6, avg_virtual_ride_distance=v7, avg_virtual_ride_elevation=v8, avg_virtual_ride_hr=v9,
        total_outdoor_runs=or1, total_outdoor_run_distance=or2, total_outdoor_run_elevation=or3, avg_outdoor_run_speed=or4, avg_outdoor_run_power=or5, avg_outdoor_distance=or6, avg_outdoor_run_elevation=or7, avg_outdoor_run_hr=or8,
        total_virtual_runs=vr1, total_virtual_run_distance=vr2, total_virtual_run_elevation=vr3, avg_virtual_run_speed=vr4, avg_virtual_run_power=vr5, avg_virtual_run_distance=vr6, avg_virtual_run_elevation=vr7, avg_virtual_run_hr=vr8,
        total_hikes=h1, total_hike_distance=h2, total_hike_elevation=h3, avg_hike_speed=h4, avg_hike_distance=h5, avg_hike_elevation=h6, avg_hike_hr=h7,
        total_swims=s1, total_swim_distance=s2, avg_swim_speed=s3, avg_swim_distance=s4, avg_swim_hr=s5,
        total_alpine_skis=as1, total_alpine_ski_distance=as2, total_alpine_ski_elevation=as3, max_alpine_ski_speed=as4, avg_alpine_ski_speed=as5, avg_alpine_ski_distance=as6, avg_alpine_ski_elevation=as7, avg_alpine_ski_hr=as8,
        total_nordic_skis=ns1, total_nordic_ski_distance=ns2, total_nordic_ski_elevation=ns3, max_nordic_ski_speed=ns4, avg_nordic_ski_speed=ns5, avg_nordic_ski_distance=ns6, avg_nordic_ski_elevation=ns7, avg_nordic_ski_hr=ns8,
        other_sport_types=other_sport_types)

@app.route('/api/all_activities')
def get_all_activities():
    #start_date, end_date = get_start_end_dates(all_activities)
    start_date = session.get('start_date')
    end_date = session.get('end_date')
    print(start_date, end_date)
    filtered_activities = []

    for activity in all_activities_list:
        activity_date = pd.to_datetime(activity['start_date'], format='%Y-%m-%d')
        if start_date <= activity_date <= end_date:
            filtered_activities.append(activity)

    return jsonify(filtered_activities)

if __name__ == '__main__':
    app.run()

