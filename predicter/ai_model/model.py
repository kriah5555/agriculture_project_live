import pickle
import pandas as pd
import os

targets = {
    0: 'apple',
    1: 'banana',
    2: 'blackgram',
    3: 'chickpea',
    4: 'coconut',
    5: 'coffee',
    6: 'cotton',
    7: 'grapes',
    8: 'jute',
    9: 'kidneybeans',
    10: 'lentil',
    11: 'maize',
    12: 'mango',
    13: 'mothbeans',
    14: 'mungbean',
    15: 'muskmelon',
    16: 'orange',
    17: 'papaya',
    18: 'pigeonpeas',
    19: 'pomegranate',
    20: 'rice',
    21: 'watermelon'
}

def run_model(soil_data):

    base_dir = os.path.dirname(__file__)  # directory of model.py
    model_path = os.path.join(base_dir, 'classifier.pkl')

    with open(model_path, 'rb') as pickle_in:
        model = pickle.load(pickle_in)

    input_data = pd.DataFrame(soil_data)

    # Map the numeric prediction to the crop name
    prediction = model.predict(input_data)
    crop_name = targets[prediction[0]]  # Use the first prediction if it's a single value
    return crop_name
