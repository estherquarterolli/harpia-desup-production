import os
import re

directory = r"c:\Users\esther.santos\Documents\AllocGest-DESUP\AllocGest-DESUP\project_root\templates"
red_classes = "flex-1 text-center bg-red-600 hover:bg-red-700 text-white font-black py-2.5 px-4 rounded-xl shadow-md transition-all transform hover:scale-105"
red_icon_classes = "text-white hover:text-red-100 hover:bg-red-700 p-2 rounded-lg transition-colors bg-red-600 font-bold shadow-md transform hover:scale-105"
red_swal_classes = "bg-red-600 text-white font-bold px-4 py-2 rounded-lg shadow-md hover:bg-red-700"

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # Simple strategy: find <button ... > Cancelar </button> or <a ...> Cancelar </a>
    # We will use regex to find tags that contain Limpar, Cancelar or Excluir
    
    # We don't want to break the whole HTML, so we will use multi_replace_file_content in antigravity if regex is too risky.
    # But since we have full control over the regex, let's just do it.
    
    # Regex for <a> or <button> tag content
    # Find <a ... class="..." ...>...Cancelar...</a>
    pattern = re.compile(r'(<(a|button)[^>]*?class=")([^"]*)("[^>]*?>\s*.*?)(limpar|cancelar|excluir)(.*?</\2>)', re.IGNORECASE | re.DOTALL)
    
    def replacer(match):
        pre_class = match.group(1)
        tag = match.group(2)
        old_class = match.group(3)
        post_class_to_text = match.group(4)
        keyword = match.group(5)
        post_text = match.group(6)
        
        # If it's an icon-only button like "Limpar Filtros" with an <i> tag, or a small icon button
        if 'p-2' in old_class and 'text-slate-400' in old_class:
             new_class = red_icon_classes
        else:
             # Retain some layout classes if needed, but the user wants them striking red
             # let's try to keep w-full or flex-1 if they exist
             added = "flex-1 text-center bg-red-600 hover:bg-red-700 text-white font-black py-2.5 px-4 rounded-xl shadow-md transition-all transform hover:-translate-y-0.5"
             if 'w-full' in old_class: added += " w-full"
             new_class = added
             
        return f"{pre_class}{new_class}{post_class_to_text}{keyword}{post_text}"

    new_content = pattern.sub(replacer, content)
    
    # Also replace SweetAlert classes
    # cancelButtonClass: '...' -> cancelButtonClass: 'bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded'
    new_content = re.sub(r"cancelButtonClass:\s*'[^']*'", f"cancelButtonClass: '{red_swal_classes}'", new_content)
    # also add it if not present but sweetalert is? 
    # Actually, SweetAlert might use customClass: { cancelButton: '...' }
    new_content = re.sub(r"cancelButton:\s*'[^']*'", f"cancelButton: '{red_swal_classes}'", new_content)

    if new_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, dirs, files in os.walk(directory):
    for file in files:
        if file.endswith('.html'):
            process_file(os.path.join(root, file))
