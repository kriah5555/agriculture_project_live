from django.db import models

# Create your models here.


# Not a django database model, no migrations needed
class Crop:
    def __init__(self, name, image_name):
        self.name = name
        self.image_name = image_name
