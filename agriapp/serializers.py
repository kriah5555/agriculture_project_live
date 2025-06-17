from rest_framework import serializers
from .models import APICountThreshold

def api_thresholds_validation(data):
    red, orange, blue, green = data['red'], data['orange'], data['blue'], data['green']
    if (green >= blue) or (blue <= green or blue >= orange) or (orange >= red or orange <= blue) or (red <= orange):
        return False
    else:
        return True

class APICountThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = APICountThreshold
        fields = '__all__'
    
    def validate(self, data):
        # Applying the validation condition
        if not api_thresholds_validation(data):
            raise serializers.ValidationError("Thresholds must follow: Red > Orange > Blue > Green")
        return data