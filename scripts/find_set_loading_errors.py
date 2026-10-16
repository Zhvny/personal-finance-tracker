import os


def find_set_loading_errors():
    root = r"../finance-tracker-gui/src"
    for dirpath, dirs, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith(('.js', '.jsx')):
                path = os.path.join(dirpath, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'setLoading(' in content and 'useState(' not in content:
                        print(f"Potential error in {path}")
                        # Find the context of setLoading(
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if 'setLoading(' in line:
                                print(f"  L{i+1}: {line.strip()}")

if __name__ == "__main__":
    find_set_loading_errors()
