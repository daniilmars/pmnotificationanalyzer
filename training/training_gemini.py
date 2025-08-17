import os
import subprocess

def generate_training_data(project_root_dir, output_path):
    """
    Generates a single file containing the project structure (tree -L 3)
    and the content of key files for Gemini chat training.

    Args:
        project_root_dir (str): The absolute path to the project's root directory.
        output_path (str): The absolute path where the output file will be saved.
    """

    # --- Comprehensive list of all relevant project files ---
    important_files = [
        # Root Configuration
        "mta.yaml",
        "README.md",

        # Backend Application
        "backend/manifest.yml",
        "backend/requirements.txt",
        "backend/app/main.py",
        "backend/app/services/analysis_service.py",
        "backend/app/models.py",
        "backend/app/auth.py",

        # Frontend Approuter
        "approuter/package.json",
        "approuter/xs-app.json",

        # Frontend Fiori Application
        "pm-analyzer-fiori/package.json",
        "pm-analyzer-fiori/ui5.yaml",
        "pm-analyzer-fiori/ui5-local.yaml",
        "pm-analyzer-fiori/ui5-deploy.yaml",
        "pm-analyzer-fiori/webapp/manifest.json",
        "pm-analyzer-fiori/webapp/index.html",
        "pm-analyzer-fiori/webapp/Component.js",
        "pm-analyzer-fiori/webapp/model/formatter.js",
        "pm-analyzer-fiori/webapp/controller/App.controller.js",
        "pm-analyzer-fiori/webapp/controller/BaseController.js",
        "pm-analyzer-fiori/webapp/controller/Worklist.controller.js",
        "pm-analyzer-fiori/webapp/controller/Object.controller.js",
        "pm-analyzer-fiori/webapp/view/App.view.xml",
        "pm-analyzer-fiori/webapp/view/Worklist.view.xml",
        "pm-analyzer-fiori/webapp/view/Object.view.xml",

        # Frontend Supporting Files (i18n & Mock Data)
        "pm-analyzer-fiori/webapp/i18n/i18n.properties",
        "pm-analyzer-fiori/webapp/i18n/i18n_de.properties",
        "pm-analyzer-fiori/webapp/mock_data_en.json",
        "pm-analyzer-fiori/webapp/mock_data_de.json",


        # CI/CD Workflow
        ".github/workflows/deploy.yml"
    ]

    # --- Remove existing output file if it exists ---
    if os.path.exists(output_path):
        os.remove(output_path)
        print(f"Removed existing output file: {output_path}")

    # --- Generate and save project structure ---
    tree_output = ""
    try:
        print(f"Generating project structure using 'tree -L 3' from {project_root_dir}...")
        # Use --noreport to exclude the "X directories, Y files" summary line
        tree_output = subprocess.check_output(
            ["tree", "-L", "3", "--noreport"],
            text=True, stderr=subprocess.PIPE, cwd=project_root_dir
        )
        print(f"Project structure generated.")
    except FileNotFoundError:
        print("Warning: 'tree' command not found. Falling back to 'git ls-files' for project structure.")
        try:
            tree_output = subprocess.check_output(
                ["git", "ls-files", "--full-name", "--cached", "--others", "--exclude-standard", "."],
                text=True, stderr=subprocess.PIPE, cwd=project_root_dir
            )
        except FileNotFoundError:
            print("Error: 'git' command not found. Falling back to 'ls -R'.")
            try:
                tree_output = subprocess.check_output(
                    ["ls", "-R", "."],
                    text=True, stderr=subprocess.PIPE, cwd=project_root_dir
                )
            except FileNotFoundError:
                print("Critical Error: 'ls' command not found. Cannot generate project structure.")
        except subprocess.CalledProcessError as e:
            print(f"Error generating project structure with git: {e.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating project structure with tree: {e.stderr}")

    # --- Export content to a single file ---
    with open(output_path, "w", encoding="utf-8") as outfile:
        outfile.write("========================================\n")
        outfile.write("PROJECT STRUCTURE (tree -L 3)\n")
        outfile.write("========================================\n")
        outfile.write(tree_output)
        outfile.write("\n\n")

        outfile.write("========================================\n")
        outfile.write("RELEVANT FILE CONTENTS\n")
        outfile.write("========================================\n")

        for file_path_relative in important_files:
            full_file_path = os.path.join(project_root_dir, file_path_relative)

            try:
                with open(full_file_path, "r", encoding="utf-8") as infile:
                    content = infile.read()
                
                outfile.write(f"\n--- File: {file_path_relative} ---\n\n")
                outfile.write(content)
                outfile.write("\n\n") # Add extra newlines for separation
                print(f"Exported content of {file_path_relative}")
            except FileNotFoundError:
                print(f"Warning: File not found - {full_file_path}. Skipping.")
            except Exception as e:
                print(f"Error reading or writing file {full_file_path}: {e}")

    print("\nTraining data export complete!")
    print(f"All project data has been exported to: {output_path}")

if __name__ == "__main__":
    # Determine the project root and script directories.
    # The project root is one level up from this script's directory.
    # This makes the script runnable from any location, as long as it resides in the 'training' folder.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Define the output file path to be in the same directory as the script.
    output_file_path = os.path.join(script_dir, "gemini_project_export.txt")

    generate_training_data(project_root_dir=project_root, output_path=output_file_path)