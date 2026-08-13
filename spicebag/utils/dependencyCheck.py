######## LIBRARIES ########

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys



######## CONSTANTS ########

REQUIREMENTS_PATH = Path(__file__).resolve().parent.parent.parent / "requirements.txt"



######## DEPENDENCY CHECKER ########

def checkDependencies():
    """Check if all requirements are installed. A no-op when running from an installed
    package, where requirements.txt is not shipped and pip already resolved the deps."""
    if not REQUIREMENTS_PATH.is_file():
        return True

    with open(REQUIREMENTS_PATH, "r") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    missing = []

    for req in requirements:
        try:
            version(req)

        except PackageNotFoundError:
            missing.append(req)

    if missing:
        print("\nMissing or outdated dependencies found:")

        for m in missing:
            print(f"  - {m}")

        choice = input("\nWould you like to install them now? (Y/n): ").strip().lower()

        if choice == 'y' or choice == '':
            print("\nInstalling dependencies...\n")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)])
            print("\nInstallation complete.\n")

        else:
            print("\nWarning: Missing dependencies may cause the application to crash.\n")
            return False

    return True


if __name__ == "__main__":
    try:
        if not checkDependencies():
            sys.exit(1)

    except Exception as e:
        print(f"Error checking dependencies: {e}")
        sys.exit(1)