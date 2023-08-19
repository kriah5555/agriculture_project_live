Step 1: Clone the Project

Clone the project repository using the following command:

git clone -b krish_19_08_2023 https://github.com/kriah5555/agriculture_project_backend.git
Step 2: Install Requirements

Once the project is cloned, navigate to the project directory:

cd agriculture_project_backend
Install all the required packages using the requirements.txt file located in the root of the repository:

pip install -r requirements.txt
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