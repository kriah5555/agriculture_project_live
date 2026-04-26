
from .models import DeviseApis, Devise, DeviseLocation
def get_all_states():
    # Import the required library
    from geopy.geocoders import Nominatim
    return_states = []
    # Initialize Nominatim API
    geolocator = Nominatim(user_agent="MyApp")
    locations = DeviseLocation.objects.all()
    for location in locations:
        location = geolocator.reverse(f"{location.latitude},{location.longitude}")
        return_states.append(location.raw['address']['state'])
    return_states = list(set(return_states))
    return_states.sort()
    return return_states


def is_coordinates_of_the_state(latitude, longitude, state):
    # Import the required library
    from geopy.geocoders import Nominatim
    # Initialize Nominatim API
    geolocator = Nominatim(user_agent="MyApp")
    location = geolocator.reverse(f"{latitude},{longitude}")
    return True if location.raw['address']['state'] == state else False

def get_devises_for_state(state):
    locations = DeviseLocation.objects.all()
    return_devise_list = [location.devise for location in locations if is_coordinates_of_the_state(location.latitude, location.longitude, state)]
    return return_devise_list

def get_dashboard_chart_data(id, year, state):
    return_array = []
    name = 'ALL'
    apis = DeviseApis.objects.all()
    if id or year or state:
        apis = DeviseApis.objects.all()
        if id:
            name = Devise.objects.get(pk = id)
            apis = DeviseApis.objects.filter(device__pk=id)
        if year:
            apis = apis.filter(created_at__year=year)
        if state:
            devises_list = get_devises_for_state(state)
            if devises_list:
                apis = apis.filter(device__in=devises_list)

    if (apis):
        apis =apis.order_by('created_at').values()
        date_list = []
        for api in apis:
            date1 = api['created_at']
            date_list.append(date1.date())
        if date_list:
            date_list = [*set(date_list)]
            date_list.sort(reverse=True)
            for i in date_list:
                return_array.append((f'{str(i.year)},{str(int(i.month) -1)},{str(i.day)}',len(apis.filter(created_at__date=i))))
    return return_array, name

def get_years_for_filter():
    return_year= list()
    apis = DeviseApis.objects.all()
    for api in apis:
        return_year.append(str(api.created_at.year))
    return return_year
