from cryptography.fernet import Fernet
from django.conf import settings

def generate_key():
    return Fernet.generate_key()

def get_cipher():
    key = settings.SECRET_KEY.encode()
    return Fernet(key)

def encrypt_device_id(device_id):
    # Convert the device ID to a string before encoding
    device_id_str = str(device_id)
    cipher = get_cipher()
    encrypted_id = cipher.encrypt(device_id_str.encode())
    return encrypted_id

def decrypt_device_id(encrypted_device_id, key):
    cipher = get_cipher()
    device_id_str = cipher.decrypt(encrypted_device_id).decode()
    
    # Convert the decrypted string back to an integer if needed
    device_id = int(device_id_str)
    return device_id