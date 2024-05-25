import os
import re
from flask import Flask, request, render_template, jsonify, send_file
from io import BytesIO
import fnmatch 

app = Flask(__name__)

def find_ignore_file(folder_path, ignore_file):
    current_dir = folder_path
    while True:
        ignore_file_path = os.path.join(current_dir, ignore_file)
        if os.path.exists(ignore_file_path):
            return ignore_file_path
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:  # reached the root directory
            return None
        current_dir = parent_dir

def get_folder_choices(root_dir):
    folder_choices = []
    for item in os.listdir(root_dir):
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path):
            folder_choices.append((item_path, []))
            for subitem in os.listdir(item_path):
                subitem_path = os.path.join(item_path, subitem)
                if os.path.isdir(subitem_path):
                    folder_choices[-1][1].append(subitem_path)
    return folder_choices

def get_files_in_folder(folder_path, gitignore_patterns, gptignore_patterns):
    files = []
    ignore_patterns = gitignore_patterns + gptignore_patterns
    print(f'ignore_patterns: {ignore_patterns}')
    for root, dirs, filenames in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(os.path.join(root, d), "*" + pattern + "*") for pattern in ignore_patterns)]
        
        for filename in filenames:
            file_path = os.path.relpath(os.path.join(root, filename), folder_path)
            if not any(fnmatch.fnmatch(file_path, "*" + pattern + "*" ) for pattern in ignore_patterns):
                files.append(file_path)
                print(f"adding file {file_path}")
            else:
                pass
    return files

def is_match(pattern, file_path):
    try:
        return fnmatch.fnmatch(file_path, pattern)    
    except Exception as e:
        print(f"Invalid pattern: {pattern}, excpetion: {e}")
        return False

def process_files(folder_path, file_paths):
    files_data = []
    for file_path in file_paths:
        full_path = os.path.join(folder_path, file_path)
        print(f"Processing file {full_path}")
        file_content = ""
        line_count = 0
        try:
            with open(full_path, 'rb') as f:
                content = f.read()
            try:
                content_decoded = content.decode('utf-8')
                line_count = len(content_decoded.splitlines())
            except UnicodeDecodeError:
                content_decoded = content.decode('utf-8', errors='replace')
            file_content += content_decoded
        except Exception as e:
            print(f"Error reading file {full_path}: {e}")
            continue
 
        file_content = f"\n'''--- {file_path} ---\n" + \
            f"\n(Line count: {line_count})\n" + \
            file_content +  "\n'''"
        
        files_data.append((file_content, line_count))

        print(f"Processed file {full_path}: size {os.path.getsize(full_path)} bytes, lines {line_count}")
    return files_data

def generate_directory_structure(file_paths, folder_path):
    structure = {}
    try:
        for file_path in file_paths:
            parts = file_path.split(os.path.sep)
            current = structure
            for part in parts:
                if part not in current:
                    full_path = os.path.join(folder_path, os.path.join(*parts[:parts.index(part)+1]))
                    if os.path.isfile(full_path):
                        with open(full_path, 'r', encoding='utf-8') as f:
                            line_count = len(f.readlines())
                        current[f"{part} ({line_count} lines)"] = {}
                    else:
                        current[part] = {}
                current = current.get(f"{part} ({line_count} lines)", current.get(part))
    except Exception as e:
        print(f"While processing {file_path}, an error occurred: {e}")
    return structure

def format_directory_structure(structure, level=0):
    output = ""
    for key in structure:
        output += "  " * level + "- " + key + "\n" 
        if structure[key]:
            output += format_directory_structure(structure[key], level + 1)
    return output

@app.route('/', methods=['GET', 'POST'])
def index():
    folder_choices = get_folder_choices('/home')
    processed_files = []
    directory_structure = ""

    if request.method == 'POST':
        folder_path = request.form['folder_path']
        gitignore_path = find_ignore_file(folder_path, '.gitignore')
        gptignore_path = find_ignore_file(folder_path, '.gptignore')
        gitignore_patterns = []
        gptignore_patterns = []

        if gitignore_path:
            with open(gitignore_path, 'r') as f:
                gitignore_patterns = [line.strip() for line in f if line.strip() != '']
        if gptignore_path:
            with open(gptignore_path, 'r') as f:
                gptignore_patterns = [line.strip() for line in f if line.strip() != '']
        gitignore_patterns += ['.git']
        file_paths = get_files_in_folder(folder_path, gitignore_patterns, gptignore_patterns)
        processed_files = process_files(folder_path, file_paths)
        directory_structure = format_directory_structure(generate_directory_structure(file_paths, folder_path))

    output_text = "Files in repository:\n\n" + directory_structure + "\n\n" + "\n".join(file[0] for file in processed_files)
    
    return render_template('index.html', folder_choices=folder_choices, processed_files=processed_files, directory_structure=directory_structure, output_text=output_text)

@app.route('/download', methods=['POST'])
def download():
    output_text = request.form['output_text']

    buffer = BytesIO()
    buffer.write(output_text.encode('utf-8'))
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='processed_files.txt', mimetype='text/plain')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3001, debug=True)