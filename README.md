PokéAbilityRando
A lightweight, high-performance desktop application built to streamline Pokémon ability randomization, testing, and drafting. It pulls data dynamically from the PokéAPI to ensure up-to-date ability pools across generations while providing granular local control via blacklists and wildcards.

Features:
Dynamic PokéAPI Integration: Automatically fetches ability lists and generation boundaries directly from the API, supporting future generations natively with an intelligent 30-day local cache (cache.json).

Advanced Filters: 
Filter rolls by specific generations (Gen 3 onwards) or choose "All Gens", with an optional toggle to dynamically strip out abilities that only function in double or multi-battles (DOUBLES_ONLY_ABILITIES).

Interactive Result Cards: Every rolled ability displays its modern flavor text description alongside quick-action buttons to instantly append items to your local blacklist.txt or wildcards.txt configurations.

Wildcard Support: 
Seamlessly flags designated wildcard tokens during generation for custom rando rulesets.

Smart Auto-Updater: 
Automatically checks for GitHub releases in the background, validating binary payloads and using platform-native update routines (update.bat for Windows and update.sh for Unix/macOS) to handle file locking safely.

Installation & Setup:
Download the latest executable or release package for your operating system from the Releases Page.

Place the executable in your preferred directory. Upon first launch, it will automatically generate local blacklist.txt and wildcards.txt configuration files in the application directory.

Run PokéAbilityRando.exe (or launch via terminal on Linux/macOS).

Configuration Files:
The app relies on two plain-text files located in the installation directory for custom rules:

blacklist.txt: Add ability names line-by-line to exclude them permanently from random generation pools.

wildcards.txt: Add ability names line-by-line that should trigger wildcard replacement behaviors when rolled.

Building from Source
To run or build the project directly from Python:

Bash
# Clone the repository
git clone https://github.com/Zenshu/PokeAbilityRando.git
cd PokeAbilityRando

# Install dependencies
pip install customtkinter requests pillow

# Run the application
python main.py
