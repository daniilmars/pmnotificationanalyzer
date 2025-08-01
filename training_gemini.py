import os
import subprocess
import shutil

def generate_training_data(project_root_dir="."):
    """
    Generates a folder containing the project structure and content of key files
    for Gemini chat training. This version includes a 'tree -L 3' output.

    Args:
        project_root_dir (str): The root directory of your project.
                                Defaults to the current directory.
    """
    output_dir_name = "gemini_training_export"
    output_path = os.path.join(project_root_dir, output_dir_name)

    # List of important files to include, relative to project_root_dir
    # Add/remove files as needed for your training purposes
    important_files = [
        "backend/app/main.py",
        "backend/app/services/analysis_service.py",
        "backend/app/models.py",
        "backend/app/auth.py",
        "backend/Dockerfile",
        "backend/requirements.txt",
        "pm-analyzer-fiori/webapp/controller/App.controller.js",
        "pm-analyzer-fiori/webapp/controller/BaseController.js",
        "pm-analyzer-fiori/webapp/controller/Login.controller.js",
        "pm-analyzer-fiori/webapp/controller/Object.controller.js",
        "pm-analyzer-fiori/webapp/controller/View1.controller.js",
        "pm-analyzer-fiori/webapp/controller/Worklist.controller.js",
        "pm-analyzer-fiori/webapp/view/App.view.xml",
        "pm-analyzer-fiori/webapp/view/Login.view.xml",
        "pm-analyzer-fiori/webapp/view/Object.view.xml",
        "pm-analyzer-fiori/webapp/view/View1.view.xml",
        "pm-analyzer-fiori/webapp/view/Worklist.view.xml",
        "mta.yaml", # The new root mta.yaml
        "approuter/package.json",
        "approuter/xs-app.json",
        "pm-analyzer-fiori/webapp/manifest.json",
        "pm-analyzer-fiori/webapp/Component.js",
        ".github/workflows/deploy.yml",
        "pm-analyzer-fiori/xs-app.json",
        "pm-analyzer-fiori/xs-security.json"
        # If you have a specific manifest.json you'd like to include, add its path:
        # "pm-analyzer-fiori/webapp/manifest.json",
    ]

    # --- Create output directory ---
    if os.path.exists(output_path):
        shutil.rmtree(output_path) # Remove existing directory to ensure fresh export
        print(f"Removed existing directory: {output_path}")
    os.makedirs(output_path)
    print(f"Created output directory: {output_path}")

    # --- Export project structure using 'tree -L 3' ---
    structure_file_path = os.path.join(output_path, "project_structure.txt")
    original_cwd = os.getcwd() # Store original working directory

    try:
        # Change to project_root_dir to ensure tree command runs correctly
        os.chdir(project_root_dir)
        print(f"Generating project structure using 'tree -L 3' from {os.getcwd()}...")
        with open(structure_file_path, "w") as f:
            # Execute the tree command and capture its output
            subprocess.run(["tree", "-L", "3"], stdout=f, text=True, check=True)
        print(f"Project structure (tree -L 3) saved to: {structure_file_path}")
    except FileNotFoundError:
        print("Warning: 'tree' command not found. Please install it (e.g., 'sudo apt-get install tree' on Ubuntu, 'brew install tree' on macOS).")
        print("Falling back to 'git ls-files' for project structure.")
        try:
            # Fallback to git ls-files
            print(f"Generating project structure using 'git ls-files' from {os.getcwd()}...")
            with open(structure_file_path, "w") as f:
                subprocess.run(["git", "ls-files", "--full-name", "--cached", "--others", "--exclude-standard", "."], stdout=f, text=True, check=True)
            print(f"Project structure (git ls-files) saved to: {structure_file_path}")
        except FileNotFoundError:
            print("Error: 'git' command not found. Falling back to 'ls -R'.")
            try:
                # Fallback to ls -R
                print(f"Generating project structure using 'ls -R' from {os.getcwd()}...")
                with open(structure_file_path, "w") as f:
                    subprocess.run(["ls", "-R", "."], stdout=f, text=True, check=True)
                print(f"Project structure (ls -R) saved to: {structure_file_path}")
            except FileNotFoundError:
                print("Critical Error: 'ls' command not found. Cannot generate project structure.")
        except subprocess.CalledProcessError as e:
            print(f"Error generating project structure with git: {e}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating project structure with tree: {e}")
    finally:
        os.chdir(original_cwd) # Always change back to original directory

    # --- Export content of important files ---
    for file_path_relative in important_files:
        full_file_path = os.path.join(project_root_dir, file_path_relative)
        # Create a sanitized filename for the output .txt file
        output_filename = file_path_relative.replace(os.sep, "_").replace(".", "_") + ".txt"
        output_file_path = os.path.join(output_path, output_filename)

        try:
            with open(full_file_path, "r", encoding="utf-8") as infile:
                content = infile.read()
            with open(output_file_path, "w", encoding="utf-8") as outfile:
                outfile.write(f"File: {file_path_relative}\n\n")
                outfile.write(content)
            print(f"Exported content of {file_path_relative} to {output_file_path}")
        except FileNotFoundError:
            print(f"Warning: File not found - {full_file_path}. Skipping.")
        except Exception as e:
            print(f"Error reading or writing file {full_file_path}: {e}")

    print("\nTraining data export complete!")
    print(f"All files are located in the '{output_dir_name}' directory within your project root.")

if __name__ == "__main__":
    # Ensure you run this script from your project's root directory
    # or specify the correct path to your project root.
    generate_training_data(os.getcwd()) # Assumes script is run from project root
