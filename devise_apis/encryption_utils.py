from cryptography.fernet import Fernet
from django.conf import settings

def generate_key():
    return Fernet.generate_key()

def get_cipher():
    key = settings.SECRET_KEY.encode()
    return Fernet(key)

def encrypt_device_id(device_id):
    cipher = get_cipher()
    encrypted_id = cipher.encrypt(device_id.encode())
    return encrypted_id

def decrypt_device_id(encrypted_device_id):
    cipher = get_cipher()
    device_id = cipher.decrypt(encrypted_device_id).decode()
    return device_id