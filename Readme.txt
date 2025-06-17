Step 1: Clone the Project

Clone the project repository using the following command:

git clone -b production_11_10_2023 https://github.com/kriah5555/agriculture_project_backend.git
Step 2: Install Requirements

Once the project is cloned, navigate to the project directory:

cd agriculture_project_backend
Install all the required packages using the requirements.txt file located in the root of the repository:

pip install -r requirments.txt
Step 3: Set Up the Database

To set up the database, run the following commands:

python manage.py makemigrations agriapp
python manage.py migrate
python manage.py migrate agriapp
Step 4: Create Superuser/Admin

Navigate to the project directory if you're not already there:

cd agriculture_project_backend
Run the following command to create a superuser/admin:

python manage.py createsuperuser
Follow the prompts to provide a username, email, and password for the superuser/admin account.

By following these steps, you'll have the project cloned, required packages installed, the database set up for the agriapp application, and a superuser/admin account created.

Make sure to execute these commands in the terminal or command prompt, within the root directory of the cloned project. This sequence of steps will help you get the project up and running and create a superuser/admin for managing the Django admin panel.


commands to refresh server
1. sudo systemctl daemon-reload
2. sudo systemctl restart gunicorn
3. sudo systemctl restart nginx


open api for adding the soil database
https://www.arkashine-innovations.com/api/add_data/?area_name=gsf&devise_id=007&serial_no=007&electrical_conduction=6.0&nitrogen=21.0&phosphorous=50.0&potassium=27.9&calcium=24.68&magnesium=30.0&sulphur=24.98&zinc=20.99&manganese=33.12&iron=21.08&copper=21.08&boron=21.08&molybdenum=21.08&chlorine=21.08&nickel=18.0&organic_carboa=21.08&device=1&field_1=33&crop_type=arabica_coffee

for adding location
https://www.arkashine-innovations.com/api/add_location_data/?devise_id=007&latitude=19.91298&longitude=79.7400


create group called deviseowner
