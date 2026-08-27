import os

def replace_in_files(directory):
    for root, dirs, files in os.walk(directory):
        # Skip .git, .venv, __pycache__, node_modules
        if any(skip in root for skip in ['.git', '.venv', '__pycache__', 'node_modules', '.gemini']):
            continue
            
        for file in files:
            if not file.endswith(('.py', '.html', '.css', '.js', '.md', '.txt')):
                continue
                
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(filepath, 'r', encoding='latin-1') as f:
                        content = f.read()
                except:
                    continue
                    
            if 'Prisma' in content:
                # Substituições na ordem decrescente de tamanho para não quebrar strings
                new_content = content.replace('Prisma', 'Prisma')
                new_content = new_content.replace('Prisma', 'Prisma') # Com hífen non-breaking
                new_content = new_content.replace('Prisma', 'Prisma')
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Renomeado em: {filepath}")

if __name__ == '__main__':
    project_dir = r"c:\Users\esther.santos\Documents\Prisma\Prisma\project_root"
    replace_in_files(project_dir)
