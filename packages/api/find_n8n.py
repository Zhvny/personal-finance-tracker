import os

config_path = r"C:\Users\Zhvn\.n8n\config"
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        print("Config content:")
        print(f.read())
else:
    print("Config file not found")
