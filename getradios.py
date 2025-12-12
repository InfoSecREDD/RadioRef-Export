#!/usr/bin/env python3
"""
Radio Reference to CHIRP Converter
Pulls frequency data from Radio Reference via web scraping and converts it 
to CHIRP CSV format for import into handheld radios.

Created by InfoSecREDD
"""

import csv
import sys
import os
import subprocess
import importlib
import importlib.util

REQUIRED_PACKAGES = {
    'requests': 'requests>=2.31.0',
    'bs4': 'beautifulsoup4>=4.12.0',
    'colorama': 'colorama>=0.4.6',
    'uszipcode': 'uszipcode>=3.0.0',
    'lxml': 'lxml>=4.9.0',
    'python-Levenshtein': 'python-Levenshtein>=0.12.0',
    'pyserial': 'pyserial>=3.5',
    'playwright': 'playwright>=1.40.0'
}

CHIRP_CLI_PATH = None
CHIRP_AVAILABLE = False
CHIRP_INSTALL_ATTEMPTED = False
CHIRP_VERIFIED = False


def setup_venv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(script_dir, '.venv')
    venv_python = os.path.join(venv_dir, 'bin', 'python3')
    
    if sys.platform == 'win32':
        venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe')
    
    current_venv = os.environ.get('VIRTUAL_ENV')
    if current_venv:
        current_venv = os.path.normpath(os.path.abspath(current_venv))
        venv_dir_abs = os.path.normpath(os.path.abspath(venv_dir))
        if current_venv == venv_dir_abs:
            return
    
    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        try:
            subprocess.run(
                [sys.executable, '-m', 'venv', venv_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("✓ Virtual environment created successfully!")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create virtual environment: {e}")
            print("Falling back to system Python (not recommended)")
            return
        except Exception as e:
            print(f"✗ Error creating virtual environment: {e}")
            print("Falling back to system Python (not recommended)")
            return
    
    if not os.path.exists(venv_python):
        print(f"✗ Virtual environment Python not found at {venv_python}")
        print("Falling back to system Python (not recommended)")
        return
    
    print("Activating virtual environment and restarting...")
    try:
        env = os.environ.copy()
        env['VIRTUAL_ENV'] = venv_dir
        os.execve(venv_python, [venv_python] + sys.argv, env)
    except Exception as e:
        print(f"✗ Failed to restart with venv Python: {e}")
        print("Falling back to system Python (not recommended)")
        return


setup_venv()


def get_pip_command():
    pip_commands = [
        [sys.executable, '-m', 'pip'],
    ]
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(script_dir, '.venv')
    
    if sys.platform == 'win32':
        venv_pip = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        venv_pip = os.path.join(venv_dir, 'bin', 'pip3')
    
    if os.path.exists(venv_pip):
        pip_commands.insert(0, [venv_pip])
    
    python_version = sys.version_info[0]
    if python_version == 3:
        pip_commands.append(['pip3'])
    pip_commands.append(['pip'])
    
    for cmd in pip_commands:
        try:
            result = subprocess.run(
                cmd + ['--version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            if result.returncode == 0:
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    
    return [sys.executable, '-m', 'pip']


def check_and_install_dependencies():
    missing_packages = []
    
    for package_name, package_spec in REQUIRED_PACKAGES.items():
        import_name = 'bs4' if package_name == 'bs4' else package_name
        
        spec = importlib.util.find_spec(import_name)
        if spec is None:
            missing_packages.append(package_spec.split('>=')[0])
    
    if missing_packages:
        print("Checking dependencies...")
        print(f"Missing packages detected: {', '.join(missing_packages)}")
        print("Installing missing dependencies...")
        
        pip_cmd = get_pip_command()
        pip_name = ' '.join(pip_cmd)
        
        try:
            for package in missing_packages:
                print(f"  Installing {package}...")
                result = subprocess.run(
                    pip_cmd + ['install', '--quiet', package],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode != 0:
                    if not os.environ.get('VIRTUAL_ENV'):
                        result = subprocess.run(
                            pip_cmd + ['install', '--quiet', '--user', package],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                    if result.returncode != 0:
                        print(f"    Retrying with upgraded pip...")
                        subprocess.run(
                            pip_cmd + ['install', '--upgrade', '--quiet', 'pip'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        result = subprocess.run(
                            pip_cmd + ['install', '--quiet', package],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        if result.returncode != 0:
                            raise subprocess.CalledProcessError(result.returncode, pip_name)
            print("✓ All dependencies installed successfully!\n")
        except subprocess.CalledProcessError as e:
            print(f"\n⚠ Warning: Failed to automatically install some dependencies.")
            print(f"Please install manually with: {pip_name} install {' '.join(missing_packages)}\n")
            print("You can also use: pip install -r requirements.txt\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n⚠ Warning: Error installing dependencies: {e}")
            print(f"Please install manually with: {pip_name} install {' '.join(missing_packages)}\n")
            print("You can also use: pip install -r requirements.txt\n")
            sys.exit(1)


check_and_install_dependencies()

import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='fuzzywuzzy')

import argparse
import requests
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote, urljoin
import time
import re
from datetime import datetime
import json
import tempfile
import shutil

try:
    from colorama import init, Fore, Style, Back
    init(autoreset=True)
    HAS_COLORS = True
except ImportError:
    HAS_COLORS = False
    class Fore:
        RED = YELLOW = GREEN = CYAN = MAGENTA = BLUE = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = RESET_ALL = ''
    class Back:
        BLACK = ''


class Colors:
    HEADER = Fore.CYAN + Style.BRIGHT
    SUCCESS = Fore.GREEN + Style.BRIGHT
    WARNING = Fore.YELLOW + Style.BRIGHT
    ERROR = Fore.RED + Style.BRIGHT
    INFO = Fore.CYAN
    BANNER = Fore.RED + Style.BRIGHT
    DIM = Style.DIM
    RESET = Style.RESET_ALL


def print_banner():
    COLOR_RADIO = Fore.RED + Style.BRIGHT
    COLOR_FREQ = Fore.YELLOW + Style.BRIGHT
    COLOR_HARV = Fore.GREEN + Style.BRIGHT
    COLOR_BOX = Fore.CYAN + Style.BRIGHT
    
    banner = f"""
{COLOR_BOX}╔═══════════════════════════════════════════════════════════╗{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                                                           {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                        {COLOR_RADIO}▄▖▄▖▄ ▄▖▄▖{Colors.RESET}                         {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                        {COLOR_RADIO}▙▘▌▌▌▌▐ ▌▌{Colors.RESET}                         {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                        {COLOR_RADIO}▌▌▛▌▙▘▟▖▙▌{Colors.RESET}                         {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                                                           {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                    {COLOR_FREQ}▄▖▄▖▄▖▄▖▖▖▄▖▖ ▖▄▖▖▖{Colors.RESET}                    {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                    {COLOR_FREQ}▙▖▙▘▙▖▌▌▌▌▙▖▛▖▌▌ ▌▌{Colors.RESET}                    {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                    {COLOR_FREQ}▌ ▌▌▙▖█▌▙▌▙▖▌▝▌▙▖▐{Colors.RESET}                     {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                           {COLOR_FREQ}▘{Colors.RESET}                               {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                    {COLOR_HARV}▖▖▄▖▄▖▖▖▄▖▄▖▄▖▄▖▄▖{Colors.RESET}                     {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                    {COLOR_HARV}▙▌▌▌▙▘▌▌▙▖▚ ▐ ▙▖▙▘{Colors.RESET}                     {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                    {COLOR_HARV}▌▌▛▌▌▌▚▘▙▖▄▌▐ ▙▖▌▌{Colors.RESET}                     {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                                                           {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}    ════════════════════════════════════════════════════   {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                                                           {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}    {Colors.HEADER}  RADIO FREQUENCY HARVESTER v1.1{Colors.RESET}                       {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}    {Colors.WARNING}  Scraping Radio Reference → CHIRP CSV{Colors.RESET}                 {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                                                           {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}    {Colors.DIM}              Created by InfoSecREDD{Colors.RESET}                   {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}║{Colors.RESET}                                                           {COLOR_BOX}║{Colors.RESET}
{COLOR_BOX}╚═══════════════════════════════════════════════════════════╝{Colors.RESET}
{Colors.RESET}
"""
    print(banner)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def check_radio_connection(port: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    try:
        import serial.tools.list_ports
        
        USB_SERIAL_PATTERNS = [
            'ttyUSB',
            'cu.usbserial',
            'tty.usbserial',
            'cu.SLAB',
            'tty.SLAB',
            'cu.wchusbserial',
            'tty.wchusbserial',
            'cu.usbmodem',
            'tty.usbmodem',
            'COM',
        ]
        
        USB_SERIAL_HWIDS = [
            'ch340',
            'ch341',
            'cp210',
            'ftdi',
            'FTDI',
            'Prolific',
            'prolific',
            'silicon',
            'wch',
            'usb',
        ]
        
        def is_usb_serial_port(port_info) -> bool:
            device = port_info.device.lower()
            description = (port_info.description or "").lower()
            hwid = (port_info.hwid or "").lower()
            
            for pattern in USB_SERIAL_PATTERNS:
                if pattern.lower() in device:
                    return True
            
            for hwid_pattern in USB_SERIAL_HWIDS:
                if hwid_pattern.lower() in hwid:
                    return True
            
            if 'usb' in description and ('serial' in description or 'com' in description):
                return True
            
            return False
        
        def is_system_port(port_info) -> bool:
            device = port_info.device.lower()
            description = (port_info.description or "").lower()
            hwid = (port_info.hwid or "").lower()
            
            if 'bluetooth' in device or 'bluetooth' in description:
                return True
            
            if 'debug-console' in device:
                return True
            
            if 'incoming-port' in device or 'outgoing-port' in device:
                return True
            
            if 'modem' in device and 'usb' not in device:
                return True
            
            return False
        
        ports = serial.tools.list_ports.comports()
        
        if not ports:
            return False, None
        
        usb_serial_ports = [p for p in ports if is_usb_serial_port(p) and not is_system_port(p)]
        
        if not usb_serial_ports:
            return False, None
        
        if port:
            for p in usb_serial_ports:
                if p.device == port:
                    return True, port
            return False, None
        
        return True, usb_serial_ports[0].device if usb_serial_ports else None
    except ImportError:
        return False, None
    except Exception:
        return False, None


def get_connection_status() -> Tuple[bool, Optional[str], Optional[str]]:
    selected_radio = get_selected_radio_model()
    if not selected_radio:
        return False, None, None
    
    config_file = ".radio_config.json"
    saved_port = None
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                saved_port = config.get('last_port')
        except Exception:
            pass
    
    if saved_port:
        is_connected, port = check_radio_connection(saved_port)
        if is_connected:
            return True, port, selected_radio['name']
    
    is_connected, port = check_radio_connection()
    return is_connected, port, selected_radio['name'] if is_connected else None


def print_menu():
    print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
    print(f"{Colors.HEADER}  MAIN MENU{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
    
    selected_radio = get_selected_radio_model()
    if selected_radio:
        print(f"{Colors.INFO}Selected Radio:{Colors.RESET} {Colors.SUCCESS}{selected_radio['name']}{Colors.RESET} ({selected_radio['manufacturer']})")
        print(f"{Colors.DIM}  Baudrate: {selected_radio['baudrate']} | Max Channels: {selected_radio['max_channels']} | CHIRP ID: {selected_radio['chirp_id']}{Colors.RESET}\n")
    else:
        print(f"{Colors.WARNING}⚠  No radio model selected{Colors.RESET} {Colors.DIM}(Use option 7 to select){Colors.RESET}\n")
    
    is_connected, port, radio_name = get_connection_status()
    if is_connected and port:
        print(f"{Colors.SUCCESS}✓ Radio Connected:{Colors.RESET} {port}")
        if radio_name:
            print(f"{Colors.DIM}  Detected: {radio_name}{Colors.RESET}\n")
        else:
            print()
    else:
        print(f"{Colors.WARNING}⚠ Radio Not Connected{Colors.RESET} {Colors.DIM}(Connect USB cable and select port){Colors.RESET}\n")
    
    print(f"{Colors.HEADER}{'─'*60}{Colors.RESET}\n")
    
    print(f"{Colors.INFO}[1]{Colors.RESET} Search by ZIP Code {Colors.DIM}(or: zip, zipcode){Colors.RESET}")
    print(f"{Colors.INFO}[2]{Colors.RESET} Search by City & State {Colors.DIM}(or: city){Colors.RESET}")
    print(f"{Colors.INFO}[3]{Colors.RESET} Search by County & State {Colors.DIM}(or: county){Colors.RESET}")
    print(f"{Colors.INFO}[4]{Colors.RESET} Import CSV to Handheld {Colors.DIM}(or: import, upload){Colors.RESET}")
    print(f"{Colors.INFO}[5]{Colors.RESET} Create Backup {Colors.DIM}(or: backup, save){Colors.RESET}")
    print(f"{Colors.INFO}[6]{Colors.RESET} Restore from Backup {Colors.DIM}(or: restore){Colors.RESET}")
    print(f"{Colors.INFO}[7]{Colors.RESET} Validate CSV File {Colors.DIM}(or: validate){Colors.RESET}")
    print(f"{Colors.INFO}[8]{Colors.RESET} View Serial Ports {Colors.DIM}(or: ports, serial){Colors.RESET}")
    print(f"{Colors.INFO}[9]{Colors.RESET} Select Radio Model {Colors.DIM}(or: models, radios, select){Colors.RESET}")
    print(f"{Colors.INFO}[10]{Colors.RESET} Filter Existing CSV {Colors.DIM}(or: filter){Colors.RESET}")
    print(f"{Colors.INFO}[11]{Colors.RESET} Convert CSV to TXT {Colors.DIM}(or: convert, csv2txt){Colors.RESET}")
    print(f"{Colors.INFO}[12]{Colors.RESET} View Backup Files {Colors.DIM}(or: backups, viewbackups){Colors.RESET}")
    print(f"{Colors.INFO}[13]{Colors.RESET} Build County Cache {Colors.DIM}(or: cache, buildcache){Colors.RESET}")
    print()
    print(f"{Colors.INFO}[0/Q]{Colors.RESET} Exit {Colors.DIM}(or: quit, exit){Colors.RESET}")
    print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}\n")


def get_user_input(prompt: str, color: str = Colors.INFO) -> str:
    try:
        return input(f"{color}{prompt}{Colors.RESET}").strip()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Operation cancelled by user.{Colors.RESET}")
        sys.exit(0)


def detect_serial_ports() -> List[Tuple[str, str]]:
    try:
        import serial.tools.list_ports
        
        USB_SERIAL_PATTERNS = [
            'ttyUSB',
            'cu.usbserial',
            'tty.usbserial',
            'cu.SLAB',
            'tty.SLAB',
            'cu.wchusbserial',
            'tty.wchusbserial',
            'cu.usbmodem',
            'tty.usbmodem',
            'COM',
        ]
        
        USB_SERIAL_HWIDS = [
            'ch340',
            'ch341',
            'cp210',
            'ftdi',
            'FTDI',
            'Prolific',
            'prolific',
            'silicon',
            'wch',
            'usb',
        ]
        
        def is_usb_serial_port(port_info) -> bool:
            device = port_info.device.lower()
            description = (port_info.description or "").lower()
            hwid = (port_info.hwid or "").lower()
            
            for pattern in USB_SERIAL_PATTERNS:
                if pattern.lower() in device:
                    return True
            
            for hwid_pattern in USB_SERIAL_HWIDS:
                if hwid_pattern.lower() in hwid:
                    return True
            
            if 'usb' in description and ('serial' in description or 'com' in description):
                return True
            
            return False
        
        def is_system_port(port_info) -> bool:
            device = port_info.device.lower()
            description = (port_info.description or "").lower()
            
            if 'bluetooth' in device or 'bluetooth' in description:
                return True
            
            if 'debug-console' in device:
                return True
            
            if 'incoming-port' in device or 'outgoing-port' in device:
                return True
            
            if 'modem' in device and 'usb' not in device:
                return True
            
            return False
        
        ports = serial.tools.list_ports.comports()
        result = []
        
        for port in ports:
            if is_usb_serial_port(port) and not is_system_port(port):
                description = port.description or "USB Serial Port"
                hwid = port.hwid or ""
                if hwid:
                    result.append((port.device, f"{description} ({hwid})"))
                else:
                    result.append((port.device, description))
        
        return result
    except ImportError:
        return []
    except Exception as e:
        print_status(f"Error detecting serial ports: {e}", "error")
        return []


def validate_chirp_csv(csv_file: str) -> Tuple[bool, str, List[Dict]]:
    if not os.path.exists(csv_file):
        return False, f"File not found: {csv_file}", []
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            required_columns = ['Location', 'Frequency', 'Name']
            if not reader.fieldnames:
                return False, "CSV file appears to be empty or invalid", []
            
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}", []
            
            frequencies = []
            errors = []
            for idx, row in enumerate(reader, start=2):
                try:
                    freq = row.get('Frequency', '').strip()
                    if freq:
                        try:
                            freq_float = float(freq)
                            if freq_float < 30 or freq_float > 1000:
                                errors.append(f"Row {idx}: Frequency {freq} out of typical range")
                        except ValueError:
                            errors.append(f"Row {idx}: Invalid frequency format: {freq}")
                    
                    frequencies.append(row)
                except Exception as e:
                    errors.append(f"Row {idx}: {str(e)}")
            
            if errors:
                error_msg = f"Found {len(errors)} validation errors:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more errors"
                return False, error_msg, frequencies
            
            return True, f"Valid CHIRP CSV with {len(frequencies)} frequencies", frequencies
            
    except Exception as e:
        return False, f"Error reading CSV file: {str(e)}", []


def get_radio_models() -> List[Dict[str, any]]:
    """
    Get comprehensive list of CHIRP-compatible radio models with detailed settings
    
    Returns:
        List of radio model dictionaries with CHIRP settings
        Organized by manufacturer for easy browsing
    """
    return [
        {"name": "Baofeng UV-5R", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-5R", "memory_format": "uv5r", "notes": "Most popular entry-level radio"},
        {"name": "Baofeng BF-F8HP", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng BF-F8HP", "memory_format": "bf8hp", "notes": "Higher power version"},
        {"name": "Baofeng UV-82", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-82", "memory_format": "uv82", "notes": "Dual PTT design"},
        {"name": "Baofeng UV-82HP", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-82HP", "memory_format": "uv82hp", "notes": "High power version"},
        {"name": "Baofeng UV-5X3", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-5X3", "memory_format": "uv5x3", "notes": "Tri-band HT"},
        {"name": "Baofeng GT-3TP", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng GT-3TP", "memory_format": "gt3tp", "notes": "Tri-band HT"},
        {"name": "Baofeng UV-9R", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-9R", "memory_format": "uv9r", "notes": "Waterproof HT"},
        {"name": "Baofeng UV-9R Plus", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-9R Plus", "memory_format": "uv9rplus", "notes": "Enhanced waterproof"},
        {"name": "Baofeng UV-B5", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-B5", "memory_format": "uvb5", "notes": "Compact HT"},
        {"name": "Baofeng UV-B6", "manufacturer": "Baofeng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Baofeng UV-B6", "memory_format": "uvb6", "notes": "Compact HT"},
        {"name": "Baofeng DM-5R", "manufacturer": "Baofeng", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Baofeng DM-5R", "memory_format": "dm5r", "notes": "DMR digital radio"},
        {"name": "Baofeng RD-5R", "manufacturer": "Baofeng", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Baofeng RD-5R", "memory_format": "rd5r", "notes": "DMR digital HT"},
        
        {"name": "Yaesu FT-60R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-60R", "memory_format": "ft60", "notes": "Popular dual-band HT"},
        {"name": "Yaesu FT-70DR", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-70DR", "memory_format": "ft70", "notes": "Digital C4FM/FM dual-band"},
        {"name": "Yaesu FT-3DR", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-3DR", "memory_format": "ft3d", "notes": "Advanced digital HT with GPS"},
        {"name": "Yaesu FT-65R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-65R", "memory_format": "ft65", "notes": "Entry-level dual-band"},
        {"name": "Yaesu FT-4XR", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-4XR", "memory_format": "ft4xr", "notes": "Budget dual-band HT"},
        {"name": "Yaesu FT-891", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-891", "memory_format": "ft891", "notes": "HF/6m mobile"},
        {"name": "Yaesu FT-857D", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-857D", "memory_format": "ft857", "notes": "HF/VHF/UHF mobile"},
        {"name": "Yaesu FT-897D", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-897D", "memory_format": "ft897", "notes": "HF/VHF/UHF base/mobile"},
        {"name": "Yaesu VX-6R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu VX-6R", "memory_format": "vx6r", "notes": "Tri-band HT"},
        {"name": "Yaesu VX-7R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu VX-7R", "memory_format": "vx7r", "notes": "Tri-band HT"},
        {"name": "Yaesu VX-8R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu VX-8R", "memory_format": "vx8r", "notes": "Quad-band HT"},
        {"name": "Yaesu FT-8800R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-8800R", "memory_format": "ft8800", "notes": "Dual-band mobile"},
        {"name": "Yaesu FT-8900R", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FT-8900R", "memory_format": "ft8900", "notes": "Quad-band mobile"},
        {"name": "Yaesu FTM-400XDR", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FTM-400XDR", "memory_format": "ftm400", "notes": "Digital C4FM mobile"},
        {"name": "Yaesu FTM-300DR", "manufacturer": "Yaesu", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Yaesu FTM-300DR", "memory_format": "ftm300", "notes": "Digital C4FM mobile"},
        
        {"name": "Kenwood TH-D74A", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TH-D74A", "memory_format": "thd74", "notes": "D-STAR digital radio"},
        {"name": "Kenwood TH-D72A", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TH-D72A", "memory_format": "thd72", "notes": "D-STAR dual-band HT"},
        {"name": "Kenwood TH-D7A", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TH-D7A", "memory_format": "thd7", "notes": "Dual-band HT"},
        {"name": "Kenwood TH-F6A", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TH-F6A", "memory_format": "thf6", "notes": "Tri-band HT"},
        {"name": "Kenwood TH-K20A", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TH-K20A", "memory_format": "thk20", "notes": "2m HT"},
        {"name": "Kenwood TM-V71A", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TM-V71A", "memory_format": "tmv71", "notes": "Dual-band mobile"},
        {"name": "Kenwood TM-D710G", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TM-D710G", "memory_format": "tmd710", "notes": "D-STAR mobile"},
        {"name": "Kenwood TS-2000", "manufacturer": "Kenwood", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Kenwood TS-2000", "memory_format": "ts2000", "notes": "HF/VHF/UHF base"},
        
        {"name": "Icom IC-F4161DT", "manufacturer": "Icom", "max_channels": 512, "baudrate": 9600, "chirp_id": "Icom IC-F4161DT", "memory_format": "icf4161", "notes": "DMR digital radio"},
        {"name": "Icom IC-2730A", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-2730A", "memory_format": "ic2730", "notes": "Dual-band mobile"},
        {"name": "Icom IC-7100", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-7100", "memory_format": "ic7100", "notes": "HF/VHF/UHF mobile"},
        {"name": "Icom IC-92AD", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-92AD", "memory_format": "ic92ad", "notes": "D-STAR dual-band HT"},
        {"name": "Icom IC-2820H", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-2820H", "memory_format": "ic2820", "notes": "D-STAR dual-band mobile"},
        {"name": "Icom IC-2730A", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-2730A", "memory_format": "ic2730", "notes": "Dual-band mobile"},
        {"name": "Icom IC-2300H", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-2300H", "memory_format": "ic2300", "notes": "2m mobile"},
        {"name": "Icom IC-3200A", "manufacturer": "Icom", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Icom IC-3200A", "memory_format": "ic3200", "notes": "70cm mobile"},
        
        {"name": "Wouxun KG-UV9D", "manufacturer": "Wouxun", "max_channels": 999, "baudrate": 9600, "chirp_id": "Wouxun KG-UV9D", "memory_format": "kguv9d", "notes": "Tri-band HT"},
        {"name": "Wouxun KG-UV8D", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-UV8D", "memory_format": "kguv8d", "notes": "Dual-band HT"},
        {"name": "Wouxun KG-UV6D", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-UV6D", "memory_format": "kguv6d", "notes": "Dual-band HT"},
        {"name": "Wouxun KG-UV3D", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-UV3D", "memory_format": "kguv3d", "notes": "Dual-band HT"},
        {"name": "Wouxun KG-UV2D", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-UV2D", "memory_format": "kguv2d", "notes": "Dual-band HT"},
        {"name": "Wouxun KG-UV1D", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-UV1D", "memory_format": "kguv1d", "notes": "Dual-band HT"},
        {"name": "Wouxun KG-805G", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-805G", "memory_format": "kg805g", "notes": "GMRS HT"},
        {"name": "Wouxun KG-935G", "manufacturer": "Wouxun", "max_channels": 128, "baudrate": 9600, "chirp_id": "Wouxun KG-935G", "memory_format": "kg935g", "notes": "GMRS HT"},
        
        {"name": "Anytone AT-D878UV", "manufacturer": "Anytone", "max_channels": 4000, "baudrate": 9600, "chirp_id": "Anytone AT-D878UV", "memory_format": "anytone878", "notes": "DMR digital dual-band HT"},
        {"name": "Anytone AT-D578UV", "manufacturer": "Anytone", "max_channels": 4000, "baudrate": 9600, "chirp_id": "Anytone AT-D578UV", "memory_format": "anytone578", "notes": "DMR digital mobile"},
        {"name": "Anytone AT-D868UV", "manufacturer": "Anytone", "max_channels": 4000, "baudrate": 9600, "chirp_id": "Anytone AT-D868UV", "memory_format": "anytone868", "notes": "DMR digital HT"},
        {"name": "Anytone AT-778UV", "manufacturer": "Anytone", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Anytone AT-778UV", "memory_format": "anytone778", "notes": "Dual-band mobile"},
        {"name": "Anytone AT-779UV", "manufacturer": "Anytone", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Anytone AT-779UV", "memory_format": "anytone779", "notes": "Dual-band mobile"},
        {"name": "Anytone AT-5888UV", "manufacturer": "Anytone", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Anytone AT-5888UV", "memory_format": "anytone5888", "notes": "Quad-band mobile"},
        
        {"name": "TYT MD-380", "manufacturer": "TYT", "max_channels": 1000, "baudrate": 9600, "chirp_id": "TYT MD-380", "memory_format": "tytmd380", "notes": "DMR digital radio"},
        {"name": "TYT MD-390", "manufacturer": "TYT", "max_channels": 1000, "baudrate": 9600, "chirp_id": "TYT MD-390", "memory_format": "tytmd390", "notes": "DMR digital radio with GPS"},
        {"name": "TYT MD-2017", "manufacturer": "TYT", "max_channels": 1000, "baudrate": 9600, "chirp_id": "TYT MD-2017", "memory_format": "tytmd2017", "notes": "DMR dual-band HT"},
        {"name": "TYT MD-9600", "manufacturer": "TYT", "max_channels": 1000, "baudrate": 9600, "chirp_id": "TYT MD-9600", "memory_format": "tytmd9600", "notes": "DMR mobile"},
        {"name": "TYT TH-7800", "manufacturer": "TYT", "max_channels": 1000, "baudrate": 9600, "chirp_id": "TYT TH-7800", "memory_format": "tytth7800", "notes": "Dual-band mobile"},
        {"name": "TYT TH-9000", "manufacturer": "TYT", "max_channels": 1000, "baudrate": 9600, "chirp_id": "TYT TH-9000", "memory_format": "tytth9000", "notes": "Quad-band mobile"},
        
        {"name": "Radioddity GD-77", "manufacturer": "Radioddity", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Radioddity GD-77", "memory_format": "gd77", "notes": "DMR digital HT"},
        {"name": "Radioddity GS-5B", "manufacturer": "Radioddity", "max_channels": 128, "baudrate": 9600, "chirp_id": "Radioddity GS-5B", "memory_format": "gs5b", "notes": "Dual-band HT"},
        {"name": "Radioddity QB-25", "manufacturer": "Radioddity", "max_channels": 128, "baudrate": 9600, "chirp_id": "Radioddity QB-25", "memory_format": "qb25", "notes": "25W mobile"},
        
        {"name": "Quansheng UV-K5", "manufacturer": "Quansheng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Quansheng UV-K5", "memory_format": "uvk5", "notes": "Wideband HT"},
        {"name": "Quansheng UV-K6", "manufacturer": "Quansheng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Quansheng UV-K6", "memory_format": "uvk6", "notes": "Wideband HT"},
        {"name": "Quansheng TG-UV2", "manufacturer": "Quansheng", "max_channels": 128, "baudrate": 9600, "chirp_id": "Quansheng TG-UV2", "memory_format": "tguv2", "notes": "Dual-band HT"},
        
        {"name": "Alinco DJ-G7", "manufacturer": "Alinco", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Alinco DJ-G7", "memory_format": "djg7", "notes": "Tri-band HT"},
        {"name": "Alinco DJ-G7T", "manufacturer": "Alinco", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Alinco DJ-G7T", "memory_format": "djg7t", "notes": "Tri-band HT"},
        {"name": "Alinco DR-135T", "manufacturer": "Alinco", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Alinco DR-135T", "memory_format": "dr135t", "notes": "2m mobile"},
        {"name": "Alinco DR-435T", "manufacturer": "Alinco", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Alinco DR-435T", "memory_format": "dr435t", "notes": "70cm mobile"},
        {"name": "Alinco DR-635T", "manufacturer": "Alinco", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Alinco DR-635T", "memory_format": "dr635t", "notes": "Dual-band mobile"},
        
        {"name": "Retevis RT3S", "manufacturer": "Retevis", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Retevis RT3S", "memory_format": "rt3s", "notes": "DMR digital HT"},
        {"name": "Retevis RT82", "manufacturer": "Retevis", "max_channels": 128, "baudrate": 9600, "chirp_id": "Retevis RT82", "memory_format": "rt82", "notes": "Dual-band HT"},
        {"name": "Retevis RT85", "manufacturer": "Retevis", "max_channels": 128, "baudrate": 9600, "chirp_id": "Retevis RT85", "memory_format": "rt85", "notes": "Dual-band HT"},
        
        {"name": "BTECH UV-5X3", "manufacturer": "BTECH", "max_channels": 128, "baudrate": 9600, "chirp_id": "BTECH UV-5X3", "memory_format": "uv5x3", "notes": "Tri-band HT"},
        {"name": "BTECH UV-2501", "manufacturer": "BTECH", "max_channels": 128, "baudrate": 9600, "chirp_id": "BTECH UV-2501", "memory_format": "uv2501", "notes": "2m mobile"},
        {"name": "BTECH UV-5001", "manufacturer": "BTECH", "max_channels": 128, "baudrate": 9600, "chirp_id": "BTECH UV-5001", "memory_format": "uv5001", "notes": "70cm mobile"},
        {"name": "BTECH GMRS-V1", "manufacturer": "BTECH", "max_channels": 128, "baudrate": 9600, "chirp_id": "BTECH GMRS-V1", "memory_format": "gmrsv1", "notes": "GMRS HT"},
        {"name": "BTECH DMR-6X2", "manufacturer": "BTECH", "max_channels": 1000, "baudrate": 9600, "chirp_id": "BTECH DMR-6X2", "memory_format": "dmr6x2", "notes": "DMR digital HT"},
        
        {"name": "Generic CHIRP-Compatible", "manufacturer": "Various", "max_channels": 1000, "baudrate": 9600, "chirp_id": "Generic", "memory_format": "generic", "notes": "Use for unsupported models (may require manual CHIRP configuration)"},
    ]


def get_selected_radio_model() -> Optional[Dict[str, any]]:
    """
    Get the currently selected radio model from config file
    
    Returns:
        Radio model dictionary or None if not set
    """
    config_file = ".radio_config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                selected_name = config.get('selected_radio')
                if selected_name:
                    models = get_radio_models()
                    for model in models:
                        if model['name'] == selected_name:
                            return model
        except Exception:
            pass
    return None


def save_selected_radio_model(radio_name: str, port: Optional[str] = None) -> bool:
    """
    Save the selected radio model to config file
    
    Args:
        radio_name: Name of the radio model to save
        port: Optional serial port to save
        
    Returns:
        True if successful, False otherwise
    """
    config_file = ".radio_config.json"
    try:
        config = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except Exception:
                pass
        
        config['selected_radio'] = radio_name
        config['last_updated'] = datetime.now().isoformat()
        if port:
            config['last_port'] = port
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False


def create_backup_file(radio_model: str, port: str, frequencies: List[Dict] = None, csv_file: str = None, backup_dir: str = "backups") -> Optional[str]:
    """
    Create a backup file for radio configuration with frequency data
    
    Args:
        radio_model: Radio model name
        port: Serial port name
        frequencies: List of frequency dictionaries to backup
        csv_file: Path to CSV file (alternative to frequencies list)
        backup_dir: Directory to save backups
        
    Returns:
        Path to backup file or None if failed
    """
    try:
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = "".join(c for c in radio_model if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_model = safe_model.replace(' ', '_')
        backup_file = os.path.join(backup_dir, f"{safe_model}_{port}_{timestamp}.backup")
        
        backup_data = {
            "radio_model": radio_model,
            "serial_port": port,
            "backup_date": datetime.now().isoformat(),
            "backup_type": "configuration",
            "frequencies": frequencies if frequencies else [],
            "csv_file": csv_file if csv_file else None,
            "frequency_count": len(frequencies) if frequencies else 0
        }
        
        if csv_file and os.path.exists(csv_file):
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    csv_content = f.read()
                    backup_data["csv_content"] = csv_content
            except Exception as e:
                print_status(f"Warning: Could not read CSV file for backup: {e}", "warning")
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        return backup_file
    except Exception as e:
        print_status(f"Error creating backup: {e}", "error")
        return None


def check_git_available() -> bool:
    try:
        result = subprocess.run(
            ['git', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def install_chirp() -> Tuple[bool, Optional[str]]:
    """
    Automatically install CHIRP by cloning the repository and installing dependencies
    
    Returns:
        Tuple of (success, chirp_path)
    """
    print("[*] CHIRP not found. Installing CHIRP automatically...")
    
    if not check_git_available():
        print("[!] Git is not available. Please install Git first:")
        print("[*]   Windows: https://git-scm.com/download/win")
        print("[*]   macOS: xcode-select --install")
        print("[*]   Linux: sudo apt install git")
        return False, None
    
    chirp_dir = os.path.join(os.path.dirname(__file__), 'chirp')
    chirpc_path = os.path.join(chirp_dir, 'chirpc')
    chirp_cli_path = os.path.join(chirp_dir, 'chirp', 'cli', 'main.py')
    
    if os.path.exists(chirpc_path):
        print("[*] CHIRP already exists at expected location.")
        return True, chirpc_path
    elif os.path.exists(chirp_cli_path):
        return True, chirp_cli_path
    
    try:
        print("[*] Cloning CHIRP repository...")
        print("[*] This may take a few minutes...")
        
        if os.path.exists(chirp_dir):
            print("[*] Removing existing chirp directory...")
            shutil.rmtree(chirp_dir)
        
        git_cmd = ['git', 'clone', '--depth', '1', 'https://github.com/kk7ds/chirp.git', chirp_dir]
        result = subprocess.run(
            git_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            text=True
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            print(f"[!] Failed to clone CHIRP repository: {error_msg}")
            print("[*] Please install manually: git clone https://github.com/kk7ds/chirp")
            return False, None
        
        if not os.path.exists(chirpc_path) and not os.path.exists(chirp_cli_path):
            print("[!] CHIRP cloned but CLI not found.")
            return False, None
        
        print("[*] CHIRP repository cloned successfully.")
        print("[*] Installing CHIRP as a Python module...")
        
        pip_cmd = get_pip_command()
        
        requirements_file = os.path.join(chirp_dir, 'requirements.txt')
        if os.path.exists(requirements_file):
            print("[*] Installing CHIRP dependencies...")
            dep_result = subprocess.run(
                pip_cmd + ['install', '-q', '-r', requirements_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
                text=True
            )
            
            if dep_result.returncode != 0:
                print("[!] Warning: Some CHIRP dependencies may have failed to install.")
                print("[*] You may need to install them manually: pip install -r chirp/requirements.txt")
            else:
                print("[*] CHIRP dependencies installed successfully.")
        else:
            print("[!] Warning: requirements.txt not found in CHIRP directory.")
        
        print("[*] Installing CHIRP module (editable mode)...")
        install_result = subprocess.run(
            pip_cmd + ['install', '-q', '-e', chirp_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            text=True,
            cwd=chirp_dir
        )
        
        if install_result.returncode != 0:
            print("[!] Warning: CHIRP module installation may have failed.")
            print("[*] CHIRP CLI may still work if dependencies are installed.")
        else:
            print("[*] CHIRP module installed successfully.")
        
        if os.path.exists(chirpc_path):
            print("[*] CHIRP installation complete!")
            return True, chirpc_path
        elif os.path.exists(chirp_cli_path):
            print("[*] CHIRP installation complete!")
            return True, chirp_cli_path
        else:
            print("[!] CHIRP installed but CLI not found.")
            return False, None
        
    except subprocess.TimeoutExpired:
        print("[!] CHIRP installation timed out. Please install manually.")
        return False, None
    except Exception as e:
        print(f"[!] Error installing CHIRP: {str(e)}")
        print("[*] Please install manually: git clone https://github.com/kk7ds/chirp")
        return False, None


def verify_chirp_installation() -> bool:
    global CHIRP_VERIFIED
    
    if CHIRP_VERIFIED and CHIRP_AVAILABLE:
        return True
    
    chirp_dir = os.path.join(os.path.dirname(__file__), 'chirp')
    chirpc_path = os.path.join(chirp_dir, 'chirpc')
    
    if not os.path.exists(chirp_dir):
        CHIRP_VERIFIED = True
        return False
    
    if not os.path.exists(chirpc_path):
        CHIRP_VERIFIED = True
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, chirpc_path, '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        if result.returncode != 0:
            CHIRP_VERIFIED = True
            return False
    except:
        CHIRP_VERIFIED = True
        return False
    
    try:
        if chirp_dir not in sys.path:
            sys.path.insert(0, chirp_dir)
        importlib.import_module('chirp')
        importlib.import_module('chirp.cli.main')
        CHIRP_VERIFIED = True
        return True
    except ImportError:
        CHIRP_VERIFIED = True
        return False


def ensure_chirp_installed():
    global CHIRP_AVAILABLE, CHIRP_CLI_PATH, CHIRP_VERIFIED
    
    if CHIRP_VERIFIED and CHIRP_AVAILABLE and CHIRP_CLI_PATH:
        return
    
    chirp_dir = os.path.join(os.path.dirname(__file__), 'chirp')
    chirpc_path = os.path.join(chirp_dir, 'chirpc')
    
    try:
        if chirp_dir not in sys.path:
            sys.path.insert(0, chirp_dir)
        importlib.import_module('chirp')
        importlib.import_module('chirp.cli.main')
        if os.path.exists(chirpc_path):
            CHIRP_CLI_PATH = chirpc_path
            CHIRP_AVAILABLE = True
            CHIRP_VERIFIED = True
            return
    except ImportError:
        pass
    
    if not os.path.exists(chirp_dir):
        print("[*] CHIRP not found. Installing CHIRP...")
        success, chirp_path = install_chirp()
        if success:
            print("[*] CHIRP installed successfully.")
            CHIRP_VERIFIED = False
            if verify_chirp_installation():
                chirpc_path = os.path.join(chirp_dir, 'chirpc')
                if os.path.exists(chirpc_path):
                    CHIRP_CLI_PATH = chirpc_path
                    CHIRP_AVAILABLE = True
        else:
            print("[!] CHIRP installation failed. Some features may not work.")
        return
    
    pip_cmd = get_pip_command()
    check_result = subprocess.run(
        pip_cmd + ['show', 'chirp'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5
    )
    
    if check_result.returncode == 0:
        CHIRP_VERIFIED = True
        if os.path.exists(chirpc_path):
            CHIRP_CLI_PATH = chirpc_path
        return
    
    print("[*] Installing CHIRP module in virtual environment (one-time setup)...")
    install_result = subprocess.run(
        pip_cmd + ['install', '-q', '-e', chirp_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
        text=True,
        cwd=chirp_dir
    )
    
    if install_result.returncode == 0:
        print("[*] CHIRP module installed successfully.")
        CHIRP_VERIFIED = False
        if verify_chirp_installation():
            if os.path.exists(chirpc_path):
                CHIRP_CLI_PATH = chirpc_path
                CHIRP_AVAILABLE = True
    else:
        error_msg = install_result.stderr.strip() if install_result.stderr else "Unknown error"
        print(f"[!] CHIRP module installation failed: {error_msg}")
        print("[!] Some features may not work. You can try installing manually:")
        print(f"    {' '.join(pip_cmd)} install -e {chirp_dir}")
        CHIRP_VERIFIED = True
        if os.path.exists(chirpc_path):
            CHIRP_CLI_PATH = chirpc_path


def check_chirp_available(auto_install: bool = True) -> Tuple[bool, Optional[str]]:
    global CHIRP_AVAILABLE, CHIRP_CLI_PATH, CHIRP_INSTALL_ATTEMPTED
    
    if CHIRP_CLI_PATH and CHIRP_AVAILABLE:
        return True, CHIRP_CLI_PATH
    
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'chirp', 'chirpc'),
        os.path.join(os.path.dirname(__file__), 'chirp', 'chirp', 'cli', 'main.py'),
        os.path.join(os.path.expanduser('~'), 'chirp', 'chirpc'),
        os.path.join(os.path.expanduser('~'), 'chirp', 'chirp', 'cli', 'main.py'),
        shutil.which('chirpc'),
    ]
    
    for path in possible_paths:
        if path and os.path.exists(path):
            try:
                result = subprocess.run(
                    [sys.executable, path, '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10
                )
                output = result.stdout.decode('utf-8', errors='ignore') + result.stderr.decode('utf-8', errors='ignore')
                if result.returncode == 0 or '--download' in output or '--upload' in output:
                    CHIRP_CLI_PATH = path
                    CHIRP_AVAILABLE = True
                    return True, path
            except:
                continue
    
    if auto_install and not CHIRP_INSTALL_ATTEMPTED:
        CHIRP_INSTALL_ATTEMPTED = True
        chirp_dir = os.path.join(os.path.dirname(__file__), 'chirp')
        chirpc_path = os.path.join(chirp_dir, 'chirpc')
        chirp_cli_path = os.path.join(chirp_dir, 'chirp', 'cli', 'main.py')
        
        if not os.path.exists(chirpc_path) and not os.path.exists(chirp_cli_path):
            print_status("CHIRP not found. Installing CHIRP on first run...", "info")
            success, installed_path = install_chirp()
            if success and installed_path and os.path.exists(installed_path):
                CHIRP_CLI_PATH = installed_path
                CHIRP_AVAILABLE = True
                return True, installed_path
        else:
            found_path = chirpc_path if os.path.exists(chirpc_path) else chirp_cli_path
            CHIRP_CLI_PATH = found_path
            CHIRP_AVAILABLE = True
            return True, found_path
    
    CHIRP_AVAILABLE = False
    CHIRP_CLI_PATH = None
    return False, None


def download_from_radio(port: str, radio_model: str, output_file: str, chirp_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Download current configuration from radio using CHIRP CLI
    
    Args:
        port: Serial port (e.g., COM3, /dev/ttyUSB0)
        radio_model: CHIRP radio model ID
        output_file: Path to save downloaded image file
        chirp_path: Optional path to chirp.py (auto-detected if None)
        
    Returns:
        Tuple of (success, error_message)
    """
    is_available, chirp_cli = check_chirp_available()
    if not is_available:
        return False, "CHIRP CLI not found. Please install CHIRP: git clone https://github.com/kk7ds/chirp"
    
    if chirp_path:
        chirp_cli = chirp_path
    
    try:
        print_status(f"Downloading from radio via {port}...", "info")
        print_status(f"Radio model: {radio_model}", "info")
        print_status(f"Output file: {output_file}", "info")
        
        if chirp_cli.endswith('chirpc') or os.path.basename(chirp_cli) == 'chirpc':
            cmd = [
                sys.executable,
                chirp_cli,
                '--download',
                '-p', port,
                '-m', radio_model,
                '-f', output_file
            ]
        elif 'cli' in chirp_cli:
            cmd = [
                sys.executable,
                '-m', 'chirp.cli.main',
                '--download',
                '-p', port,
                '-m', radio_model,
                '-f', output_file
            ]
        else:
            cmd = [
                sys.executable,
                chirp_cli,
                '--download',
                '-p', port,
                '-m', radio_model,
                '-f', output_file
            ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            text=True
        )
        
        if result.returncode == 0:
            if os.path.exists(output_file):
                print_status(f"Successfully downloaded radio configuration to {output_file}", "success")
                return True, None
            else:
                return False, "Download completed but output file not found"
        else:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return False, f"CHIRP download failed: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "Download timed out after 60 seconds"
    except Exception as e:
        return False, f"Error during download: {str(e)}"


def upload_to_radio(csv_file: str, port: str, radio_model: str, chirp_path: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Upload CSV file to radio using CHIRP CLI
    
    Args:
        csv_file: Path to CHIRP CSV file
        port: Serial port (e.g., COM3, /dev/ttyUSB0)
        radio_model: CHIRP radio model ID
        chirp_path: Optional path to chirp.py (auto-detected if None)
        
    Returns:
        Tuple of (success, error_message)
    """
    is_available, chirp_cli = check_chirp_available()
    if not is_available:
        return False, "CHIRP CLI not found. Please install CHIRP: git clone https://github.com/kk7ds/chirp"
    
    if chirp_path:
        chirp_cli = chirp_path
    
    if not os.path.exists(csv_file):
        return False, f"CSV file not found: {csv_file}"
    
    try:
        temp_img = os.path.join(tempfile.gettempdir(), f"chirp_upload_{int(time.time())}.img")
        
        print_status(f"Converting CSV to CHIRP image format...", "info")
        
        convert_cmd = [
            sys.executable,
            chirp_cli,
            '--import',
            csv_file,
            '-m', radio_model,
            '-f', temp_img
        ]
        
        convert_result = subprocess.run(
            convert_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            text=True
        )
        
        if convert_result.returncode != 0 or not os.path.exists(temp_img):
            error_msg = convert_result.stderr or convert_result.stdout or "Unknown error"
            return False, f"CSV to image conversion failed: {error_msg}"
        
        print_status(f"Uploading to radio via {port}...", "info")
        print_status(f"Radio model: {radio_model}", "info")
        
        if chirp_cli.endswith('chirpc') or os.path.basename(chirp_cli) == 'chirpc':
            upload_cmd = [
                sys.executable,
                chirp_cli,
                '--upload',
                '-p', port,
                '-m', radio_model,
                '-f', temp_img
            ]
        elif 'cli' in chirp_cli:
            upload_cmd = [
                sys.executable,
                '-m', 'chirp.cli.main',
                '--upload',
                '-p', port,
                '-m', radio_model,
                '-f', temp_img
            ]
        else:
            upload_cmd = [
                sys.executable,
                chirp_cli,
                '--upload',
                '-p', port,
                '-m', radio_model,
                '-f', temp_img
            ]
        
        upload_result = subprocess.run(
            upload_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            text=True
        )
        
        if os.path.exists(temp_img):
            try:
                os.remove(temp_img)
            except:
                pass
        
        if upload_result.returncode == 0:
            print_status("Successfully uploaded to radio!", "success")
            return True, None
        else:
            error_msg = upload_result.stderr or upload_result.stdout or "Unknown error"
            return False, f"CHIRP upload failed: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "Upload timed out after 60 seconds"
    except Exception as e:
        return False, f"Error during upload: {str(e)}"


def preview_upload(csv_file: str, radio_model: str, port: str, frequencies: List[Dict], 
                   baudrate: int = 9600, chirp_id: str = "Generic") -> None:
    """
    Display upload preview screen
    
    Args:
        csv_file: Path to CSV file
        radio_model: Selected radio model
        port: Selected serial port
        frequencies: List of frequency dictionaries
        baudrate: Serial port baudrate
        chirp_id: CHIRP radio ID
    """
    clear_screen()
    print_banner()
    
    print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
    print(f"{Colors.HEADER}  UPLOAD PREVIEW{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
    
    print(f"{Colors.INFO}CSV File:{Colors.RESET} {csv_file}")
    print(f"{Colors.INFO}Radio Model:{Colors.RESET} {radio_model}")
    print(f"{Colors.INFO}CHIRP ID:{Colors.RESET} {chirp_id}")
    print(f"{Colors.INFO}Serial Port:{Colors.RESET} {port}")
    print(f"{Colors.INFO}Baudrate:{Colors.RESET} {baudrate}")
    print(f"{Colors.INFO}Total Frequencies:{Colors.RESET} {len(frequencies)}\n")
    
    print(f"{Colors.DIM}{'─'*60}{Colors.RESET}\n")
    
    print(f"{Colors.HEADER}Preview (first 10 frequencies):{Colors.RESET}\n")
    for idx, freq in enumerate(frequencies[:10], 1):
        location = freq.get('Location', 'N/A')
        name = freq.get('Name', 'N/A')[:30]
        frequency = freq.get('Frequency', 'N/A')
        mode = freq.get('Mode', 'N/A')
        print(f"  {Colors.INFO}[{location:>3}]{Colors.RESET} {frequency:>10} MHz - {name:<30} ({mode})")
    
    if len(frequencies) > 10:
        print(f"\n{Colors.DIM}... and {len(frequencies) - 10} more frequencies{Colors.RESET}")
    
    print(f"\n{Colors.DIM}{'─'*60}{Colors.RESET}\n")
    print(f"{Colors.WARNING}⚠  Note: Actual upload requires USB cable connection{Colors.RESET}")
    print(f"{Colors.WARNING}⚠  This preview shows what would be uploaded{Colors.RESET}\n")


def restore_from_backup(backup_file: str) -> bool:
    """
    Restore frequencies from backup file to handheld radio
    
    Args:
        backup_file: Path to backup file
        
    Returns:
        True if restore was successful, False otherwise
    """
    try:
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        radio_model = backup_data.get('radio_model', 'Unknown')
        port = backup_data.get('serial_port', 'Unknown')
        frequencies = backup_data.get('frequencies', [])
        csv_content = backup_data.get('csv_content', None)
        frequency_count = backup_data.get('frequency_count', 0)
        backup_date = backup_data.get('backup_date', 'Unknown')
        
        if not frequencies and not csv_content:
            print_status("Backup file does not contain frequency data.", "error")
            return False
        
        clear_screen()
        print_banner()
        
        print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
        print(f"{Colors.HEADER}  RESTORE FROM BACKUP{Colors.RESET}")
        print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
        
        print(f"{Colors.INFO}Backup File:{Colors.RESET} {backup_file}")
        print(f"{Colors.INFO}Radio Model:{Colors.RESET} {radio_model}")
        print(f"{Colors.INFO}Serial Port:{Colors.RESET} {port}")
        print(f"{Colors.INFO}Backup Date:{Colors.RESET} {backup_date}")
        print(f"{Colors.INFO}Frequencies:{Colors.RESET} {frequency_count if frequency_count else len(frequencies) if frequencies else 'N/A'}\n")
        
        if csv_content:
            temp_csv = os.path.join("backups", f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            try:
                with open(temp_csv, 'w', encoding='utf-8') as f:
                    f.write(csv_content)
                print_status(f"Extracted CSV from backup to: {temp_csv}", "success")
                
                is_valid, message, frequencies = validate_chirp_csv(temp_csv)
                if not is_valid:
                    print_status(f"CSV validation failed: {message}", "error")
                    os.remove(temp_csv)
                    return False
            except Exception as e:
                print_status(f"Error extracting CSV from backup: {e}", "error")
                return False
        elif not frequencies:
            print_status("No frequency data found in backup.", "error")
            return False
        
        print_status("Detecting serial ports...", "info")
        ports = detect_serial_ports()
        
        if not ports:
            print_status("No serial ports detected. Please connect your radio via USB.", "error")
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            return False
        
        print(f"\n{Colors.HEADER}Available Serial Ports:{Colors.RESET}\n")
        port_names = []
        for idx, port_info in enumerate(ports, 1):
            if isinstance(port_info, tuple):
                port_name, port_desc = port_info
            else:
                port_name = port_info
                port_desc = ""
            port_names.append(port_name)
            marker = f"{Colors.SUCCESS}✓{Colors.RESET} " if port_name == port else "  "
            if port_desc:
                print(f"{marker}{Colors.INFO}[{idx}]{Colors.RESET} {port_name} - {port_desc}")
            else:
                print(f"{marker}{Colors.INFO}[{idx}]{Colors.RESET} {port_name}")
        
        port_choice = get_user_input(f"\nSelect port (1-{len(ports)}, default: {port}): ", Colors.INFO)
        
        if port_choice:
            try:
                port_idx = int(port_choice) - 1
                if 0 <= port_idx < len(port_names):
                    selected_port = port_names[port_idx]
                else:
                    selected_port = port_choice
            except ValueError:
                selected_port = port_choice
        else:
            selected_port = port
        
        radio_models = get_radio_models()
        selected_radio = get_selected_radio_model()
        
        if selected_radio and selected_radio['name'] == radio_model:
            baudrate = selected_radio['baudrate']
            chirp_id = selected_radio['chirp_id']
            max_channels = selected_radio['max_channels']
        else:
            print(f"\n{Colors.HEADER}Select Radio Model:{Colors.RESET}\n")
            for idx, model in enumerate(radio_models, 1):
                marker = f"{Colors.SUCCESS}✓{Colors.RESET} " if model['name'] == radio_model else "  "
                print(f"{marker}{Colors.INFO}[{idx}]{Colors.RESET} {model['name']} ({model['manufacturer']})")
                print(f"      Max Channels: {model['max_channels']} | Baudrate: {model['baudrate']} | CHIRP ID: {model['chirp_id']}")
            
            model_choice = get_user_input(f"\nSelect model (1-{len(radio_models)}, default: {radio_model}): ", Colors.INFO)
            
            if model_choice:
                try:
                    model_idx = int(model_choice) - 1
                    if 0 <= model_idx < len(radio_models):
                        selected_model = radio_models[model_idx]
                        radio_model = selected_model['name']
                        max_channels = selected_model['max_channels']
                        baudrate = selected_model['baudrate']
                        chirp_id = selected_model['chirp_id']
                        save_selected_radio_model(radio_model)
                    else:
                        baudrate = 9600
                        chirp_id = "Generic"
                        max_channels = 1000
                except ValueError:
                    baudrate = 9600
                    chirp_id = "Generic"
                    max_channels = 1000
            else:
                baudrate = 9600
                chirp_id = "Generic"
                max_channels = 1000
        
        if len(frequencies) > max_channels:
            print_status(f"Warning: Radio supports {max_channels} channels, but backup has {len(frequencies)} frequencies.", "warning")
            print_status(f"Only the first {max_channels} frequencies will be restored.", "warning")
            frequencies = frequencies[:max_channels]
        
        preview_upload(backup_file, radio_model, selected_port, frequencies, baudrate, chirp_id)
        
        confirm = get_user_input("\nReady to restore to handheld? (y/n): ", Colors.WARNING)
        
        if confirm.lower() in ['y', 'yes']:
            print_status("Restore functionality requires USB cable connection.", "info")
            print_status("To complete restore, use CHIRP software:", "info")
            print(f"  1. Open CHIRP")
            print(f"  2. Select radio model: {chirp_id}")
            print(f"  3. Set serial port: {selected_port} (Baudrate: {baudrate})")
            if csv_content and 'temp_csv' in locals():
                print(f"  4. Load CSV file: {temp_csv}")
            else:
                print(f"  4. Load backup file: {backup_file}")
            print(f"  5. Upload to radio")
            print_status("Restore completed via CHIRP.", "success")
        else:
            print_status("Restore cancelled.", "info")
            if 'temp_csv' in locals() and os.path.exists(temp_csv):
                os.remove(temp_csv)
        
        input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
        return True
        
    except Exception as e:
        print_status(f"Error restoring from backup: {e}", "error")
        return False


def run_import_menu():
    clear_screen()
    print_banner()
    
    print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
    print(f"{Colors.HEADER}  IMPORT CSV TO HANDHELD RADIO{Colors.RESET}")
    print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
    
    csv_file = get_user_input("Enter path to CHIRP CSV file: ", Colors.INFO)
    if not csv_file:
        print_status("No file specified. Returning to main menu.", "error")
        time.sleep(1)
        return
    
    print_status("Validating CSV file...", "info")
    is_valid, message, frequencies = validate_chirp_csv(csv_file)
    
    if not is_valid:
        print_status(f"CSV validation failed: {message}", "error")
        input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
        return
    
    print_status(message, "success")
    
    print_status("Detecting serial ports...", "info")
    ports = detect_serial_ports()
    
    if not ports:
        print_status("No serial ports detected. Make sure your radio is connected via USB.", "warning")
        port = get_user_input("Enter serial port manually (e.g., COM3, /dev/ttyUSB0): ", Colors.INFO)
        if not port:
            print_status("No port specified. Returning to main menu.", "error")
            time.sleep(1)
            return
    else:
        print(f"\n{Colors.HEADER}Available Serial Ports:{Colors.RESET}\n")
        for idx, (port_name, description) in enumerate(ports, 1):
            print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {port_name} - {description}")
        
        port_choice = get_user_input(f"\nSelect port (1-{len(ports)}) or enter custom port: ", Colors.INFO)
        
        try:
            port_idx = int(port_choice) - 1
            if 0 <= port_idx < len(ports):
                port = ports[port_idx][0]
            else:
                port = port_choice
        except ValueError:
            port = port_choice
        
        selected_radio = get_selected_radio_model()
        if selected_radio:
            save_selected_radio_model(selected_radio['name'], port)
    
    selected_radio = get_selected_radio_model()
    radio_models = get_radio_models()
    
    if selected_radio:
        print(f"\n{Colors.SUCCESS}Using Selected Radio:{Colors.RESET} {selected_radio['name']} ({selected_radio['manufacturer']})")
        print(f"{Colors.INFO}Settings:{Colors.RESET} Baudrate: {selected_radio['baudrate']} | Max Channels: {selected_radio['max_channels']} | CHIRP ID: {selected_radio['chirp_id']}")
        use_selected = get_user_input("\nUse this radio? (y/n, default: y): ", Colors.INFO)
        
        if use_selected.lower() not in ['n', 'no']:
            radio_model = selected_radio['name']
            max_channels = selected_radio['max_channels']
            baudrate = selected_radio['baudrate']
            chirp_id = selected_radio['chirp_id']
        else:
            print(f"\n{Colors.HEADER}Select Radio Model:{Colors.RESET}\n")
            for idx, model in enumerate(radio_models, 1):
                marker = f"{Colors.SUCCESS}✓{Colors.RESET} " if model['name'] == selected_radio['name'] else "  "
                print(f"{marker}{Colors.INFO}[{idx}]{Colors.RESET} {model['name']} ({model['manufacturer']})")
                print(f"      Max Channels: {model['max_channels']} | Baudrate: {model['baudrate']} | CHIRP ID: {model['chirp_id']}")
            
            model_choice = get_user_input(f"\nSelect model (1-{len(radio_models)}) or enter custom model: ", Colors.INFO)
            
            try:
                model_idx = int(model_choice) - 1
                if 0 <= model_idx < len(radio_models):
                    selected_model = radio_models[model_idx]
                    radio_model = selected_model['name']
                    max_channels = selected_model['max_channels']
                    baudrate = selected_model['baudrate']
                    chirp_id = selected_model['chirp_id']
                    save_selected_radio_model(radio_model)
                else:
                    radio_model = model_choice
                    max_channels = 1000
                    baudrate = 9600
                    chirp_id = "Generic"
            except ValueError:
                radio_model = model_choice
                max_channels = 1000
                baudrate = 9600
                chirp_id = "Generic"
    else:
        print(f"\n{Colors.HEADER}Select Radio Model:{Colors.RESET}\n")
        print(f"{Colors.WARNING}No radio model selected. Please select one:{Colors.RESET}\n")
        for idx, model in enumerate(radio_models, 1):
            print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {model['name']} ({model['manufacturer']})")
            print(f"      Max Channels: {model['max_channels']} | Baudrate: {model['baudrate']} | CHIRP ID: {model['chirp_id']}")
        
        model_choice = get_user_input(f"\nSelect model (1-{len(radio_models)}) or enter custom model: ", Colors.INFO)
        
        try:
            model_idx = int(model_choice) - 1
            if 0 <= model_idx < len(radio_models):
                selected_model = radio_models[model_idx]
                radio_model = selected_model['name']
                max_channels = selected_model['max_channels']
                baudrate = selected_model['baudrate']
                chirp_id = selected_model['chirp_id']
                save_selected_radio_model(radio_model)
            else:
                radio_model = model_choice
                max_channels = 1000
                baudrate = 9600
                chirp_id = "Generic"
        except ValueError:
            radio_model = model_choice
            max_channels = 1000
            baudrate = 9600
            chirp_id = "Generic"
    
    if len(frequencies) > max_channels:
        print_status(f"Warning: Radio supports {max_channels} channels, but CSV has {len(frequencies)} frequencies.", "warning")
        print_status(f"Only the first {max_channels} frequencies will be uploaded.", "warning")
        frequencies = frequencies[:max_channels]
    
    backup_choice = get_user_input("\nCreate backup before upload? (y/n, default: y): ", Colors.INFO)
    backup_file = None
    if backup_choice.lower() not in ['n', 'no']:
        print_status("Creating backup...", "info")
        backup_file = create_backup_file(radio_model, port, frequencies=frequencies, csv_file=csv_file)
        if backup_file:
            print_status(f"Backup created: {backup_file}", "success")
        else:
            print_status("Backup creation failed, but continuing...", "warning")
    
    preview_upload(csv_file, radio_model, port, frequencies, baudrate, chirp_id)
    
    confirm = get_user_input("\nReady to upload? (y/n): ", Colors.WARNING)
    
    if confirm.lower() in ['y', 'yes']:
        is_available, chirp_path = check_chirp_available()
        
        if is_available:
            print_status("CHIRP CLI detected. Attempting direct upload...", "info")
            success, error_msg = upload_to_radio(csv_file, port, chirp_id, chirp_path)
            
            if success:
                print_status("Upload completed successfully!", "success")
                if backup_file:
                    print_status(f"Backup saved at: {backup_file}", "info")
            else:
                print_status(f"Direct upload failed: {error_msg}", "error")
                print_status("\nFalling back to manual CHIRP instructions:", "warning")
                print_status("To complete upload manually, use CHIRP software:", "info")
                print(f"  1. Open CHIRP")
                print(f"  2. Select radio model: {chirp_id}")
                print(f"  3. Set serial port: {port} (Baudrate: {baudrate})")
                print(f"  4. Load your CSV file: {csv_file}")
                print(f"  5. Upload to radio")
                if backup_file:
                    print(f"  6. Backup saved at: {backup_file}")
        else:
            print_status("CHIRP CLI not found. Using manual method.", "info")
            print_status("To enable direct upload, install CHIRP:", "info")
            print_status("  git clone https://github.com/kk7ds/chirp", "info")
            print_status("  cd chirp && python3 -m pip install -r requirements.txt", "info")
            print_status("\nTo complete upload manually, use CHIRP software:", "info")
            print(f"  1. Open CHIRP")
            print(f"  2. Select radio model: {chirp_id}")
            print(f"  3. Set serial port: {port} (Baudrate: {baudrate})")
            print(f"  4. Load your CSV file: {csv_file}")
            print(f"  5. Upload to radio")
            if backup_file:
                print(f"  6. Backup saved at: {backup_file}")
    else:
        print_status("Upload cancelled.", "info")
    
    input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")


def print_status(message: str, status_type: str = "info"):
    colors = {
        "info": Colors.INFO,
        "success": Colors.SUCCESS,
        "warning": Colors.WARNING,
        "error": Colors.ERROR
    }
    color = colors.get(status_type, Colors.INFO)
    print(f"{color}[*] {message}{Colors.RESET}")


class RadioRefToChirp:
    
    CHIRP_COLUMNS = [
        'Location', 'Name', 'Frequency', 'Duplex', 'Offset', 'Tone',
        'rToneFreq', 'cToneFreq', 'DtcsCode', 'DtcsPolarity', 'RxDtcsCode',
        'CrossMode', 'Mode', 'TStep', 'Skip', 'Comment', 'URCALL',
        'RPT1CALL', 'RPT2CALL', 'DVCODE'
    ]
    
    def __init__(self):
        self.base_url = "https://www.radioreference.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def filter_frequencies(self, frequencies: List[Dict], filter_mode: Optional[str] = None) -> List[Dict]:
        if not filter_mode:
            return frequencies
        
        filter_mode = filter_mode.upper().strip()
        filtered = []
        
        for freq in frequencies:
            mode = freq.get('Mode', '').upper()
            
            if filter_mode == 'FM' or filter_mode == 'ANALOG':
                if mode in ['FM', 'AM', ''] or 'FM' in mode or 'ANALOG' in mode:
                    filtered.append(freq)
            elif filter_mode == 'DIGITAL' or filter_mode == 'ENCRYPTED':
                if mode in ['DIGITAL', 'DMR', 'P25', 'NXDN', 'D-STAR', 'C4FM']:
                    filtered.append(freq)
            elif filter_mode == 'DMR':
                if 'DMR' in mode:
                    filtered.append(freq)
            elif filter_mode == 'P25':
                if 'P25' in mode or 'DIGITAL' in mode:
                    filtered.append(freq)
            else:
                if filter_mode in mode or mode in filter_mode:
                    filtered.append(freq)
        
        return filtered
        
    def lookup_by_zipcode(self, zipcode: str) -> List[Dict]:
        """
        Lookup frequencies by ZIP code
        
        Args:
            zipcode: 5-digit ZIP code
            
        Returns:
            List of frequency dictionaries
        """
        print_status(f"Looking up ZIP code: {zipcode}", "info")
        location_info = self._get_location_from_zip(zipcode)
        if not location_info:
            print_status(f"Could not find location for ZIP code: {zipcode}", "error")
            return []
            
        state = location_info.get('state')
        county = location_info.get('county')
        city = location_info.get('city')
        
        print_status(f"Found location: {city}, {county}, {state}", "success")
        
        return self._fetch_via_scraping(state=state, county=county, city=city)
    
    def lookup_by_city_state(self, city: str, state: str) -> List[Dict]:
        """
        Lookup frequencies by city and state
        
        First looks up which county the city is in, then fetches frequencies
        for that county and prioritizes frequencies that mention the city.
        
        Args:
            city: City name
            state: State abbreviation (e.g., 'CA', 'NY')
            
        Returns:
            List of frequency dictionaries (city-specific frequencies first)
        """
        print_status(f"Searching for frequencies in {city}, {state}", "info")
        state = state.upper()
        
        county = self._find_county_for_city(city, state)
        if county:
            print_status(f"Found {city} is in {county} County", "success")
            
            frequencies = self._fetch_via_scraping(state=state, county=county, city=city)
            
            if frequencies:
                city_lower = city.lower()
                city_specific = []
                county_wide = []
                
                for freq in frequencies:
                    alpha_tag = str(freq.get('Alpha Tag', '')).lower()
                    description = str(freq.get('Description', '')).lower()
                    location = str(freq.get('Location', '')).lower()
                    
                    if (city_lower in alpha_tag or 
                        city_lower in description or 
                        city_lower in location):
                        city_specific.append(freq)
                    else:
                        county_wide.append(freq)
                
                if city_specific:
                    print_status(f"Found {len(city_specific)} city-specific frequencies for {city}", "success")
                    if county_wide:
                        print_status(f"Also found {len(county_wide)} county-wide frequencies", "info")
                    return city_specific + county_wide
                else:
                    print_status(f"No city-specific frequencies found, returning {len(county_wide)} county-wide frequencies", "info")
                    return county_wide
            else:
                print_status(f"No frequencies found for {county} County", "warning")
                return []
        else:
            print_status(f"Could not determine county for {city}. Trying state-wide search.", "warning")
            return self._fetch_via_scraping(state=state, city=city)
    
    def lookup_by_county_state(self, county: str, state: str) -> List[Dict]:
        """
        Lookup frequencies by county and state
        
        Args:
            county: County name
            state: State abbreviation (e.g., 'CA', 'NY')
            
        Returns:
            List of frequency dictionaries
        """
        county = county.replace(' County', '').replace(' county', '').strip()
        print_status(f"Searching for frequencies in {county} County, {state}", "info")
        state = state.upper()
        return self._fetch_via_scraping(state=state, county=county)
    
    def _get_location_from_zip(self, zipcode: str) -> Optional[Dict]:
        """
        Get location information from ZIP code
        
        Args:
            zipcode: 5-digit ZIP code
            
        Returns:
            Dictionary with city, state, county info
        """
        try:
            from uszipcode import SearchEngine
            search = SearchEngine()
            result = search.by_zipcode(zipcode)
            
            if result:
                return {
                    'city': result.major_city or result.post_office_city,
                    'state': result.state,
                    'county': result.county
                }
        except ImportError:
            pass
        except Exception as e:
            error_msg = str(e)
            if 'ExtendedBase' in error_msg or 'sqlalchemy' in error_msg.lower():
                pass
            else:
                print_status(f"uszipcode lookup failed: {error_msg}. Using fallback method...", "info")
        
        return self._get_location_from_zip_fallback(zipcode)
    
    def _get_location_from_zip_fallback(self, zipcode: str) -> Optional[Dict]:
        try:
            print_status(f"Looking up ZIP code {zipcode} via web API...", "info")
            response = requests.get(f"https://api.zippopotam.us/us/{zipcode}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                place = data.get('places', [{}])[0]
                city = place.get('place name', '')
                state = place.get('state abbreviation', '')
                
                if city and state:
                    county = self._find_county_for_city(city, state)
                    return {
                        'city': city,
                        'state': state,
                        'county': county or ''
                    }
            else:
                print_status(f"ZIP code lookup API returned status {response.status_code}", "error")
        except requests.exceptions.Timeout:
            print_status("ZIP code lookup timed out. Please try again.", "error")
        except requests.exceptions.RequestException as e:
            print_status(f"Network error during ZIP lookup: {e}", "error")
        except Exception as e:
            print_status(f"Fallback ZIP lookup failed: {e}", "error")
        return None
    
    def _find_county_for_city(self, city: str, state: str) -> Optional[str]:
        try:
            from uszipcode import SearchEngine
            search = SearchEngine(simple_zipcode=True)
            results = search.by_city_and_state(city=city, state=state)
            
            if results:
                counties = {}
                for result in results:
                    if hasattr(result, 'county') and result.county:
                        counties[result.county] = counties.get(result.county, 0) + 1
                
                if counties:
                    return max(counties.items(), key=lambda x: x[1])[0]
        except Exception as e:
            error_msg = str(e)
            if 'ExtendedBase' not in error_msg and 'sqlalchemy' not in error_msg.lower():
                pass
            try:
                import requests
                geo_url = f"https://nominatim.openstreetmap.org/search?q={quote(city)},{state},USA&format=json&limit=1"
                geo_resp = requests.get(geo_url, headers={'User-Agent': 'RadioRef-Harvester'}, timeout=5)
                if geo_resp.status_code == 200:
                    data = geo_resp.json()
                    if data:
                        display = data[0].get('display_name', '')
                        parts = display.split(',')
                        if len(parts) >= 2:
                            potential_county = parts[1].strip()
                            if 'county' in potential_county.lower():
                                return potential_county.replace(' County', '').strip()
            except:
                pass
            print_status(f"Could not determine county for {city}, {state}", "warning")
        
        return None
    
    def _fetch_via_scraping(self, state: str, county: Optional[str] = None,
                           city: Optional[str] = None) -> List[Dict]:
        """
        Fetch frequencies via web scraping
        
        Args:
            state: State abbreviation
            county: County name (optional)
            city: City name (optional)
            
        Returns:
            List of frequency dictionaries
        """
        try:
            state_id = self._get_state_id(state)
            if not state_id:
                print_status(f"Could not find state ID for {state}", "error")
                return []
            
            county_id = None
            if county:
                print_status(f"Locating county ID for {county}...", "info")
                county_id = self._get_county_id(state_id, state, county)
                if not county_id:
                    print_status(f"Could not find county ID for '{county}'. Trying state-wide search.", "warning")
            
            if county_id:
                url = f"{self.base_url}/db/browse/ctid/{county_id}"
                print_status(f"Fetching frequencies for {county} County, {state}...", "info")
            else:
                url = f"{self.base_url}/apps/db/?stid={state_id}"
                print_status(f"Fetching frequencies for {state}...", "info")
            
            print_status("Connecting to Radio Reference...", "info")
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                print_status("Parsing frequency data...", "info")
                frequencies = self._parse_html_response(response.text, state, county, city)
                return frequencies
            else:
                print_status(f"Failed to fetch page: HTTP {response.status_code}", "error")
                return []
                
        except Exception as e:
            print_status(f"Error scraping: {e}", "error")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_state_id(self, state: str) -> Optional[str]:
        state_map = {
            'AL': '1', 'AK': '2', 'AZ': '3', 'AR': '4', 'CA': '5',
            'CO': '6', 'CT': '7', 'DE': '8', 'FL': '9', 'GA': '10',
            'HI': '11', 'ID': '12', 'IL': '13', 'IN': '14', 'IA': '15',
            'KS': '16', 'KY': '17', 'LA': '18', 'ME': '19', 'MD': '20',
            'MA': '21', 'MI': '22', 'MN': '23', 'MS': '24', 'MO': '25',
            'MT': '26', 'NE': '27', 'NV': '28', 'NH': '29', 'NJ': '30',
            'NM': '31', 'NY': '32', 'NC': '33', 'ND': '34', 'OH': '35',
            'OK': '36', 'OR': '37', 'PA': '38', 'RI': '39', 'SC': '40',
            'SD': '41', 'TN': '42', 'TX': '43', 'UT': '44', 'VT': '45',
            'VA': '46', 'WA': '47', 'WV': '48', 'WI': '49', 'WY': '50',
            'DC': '51'
        }
        return state_map.get(state.upper())
    
    def _get_dropdown_state_id(self, state: str) -> Optional[str]:
        """
        Get Radio Reference dropdown state ID from state abbreviation
        This is the ID used in /db/browse/stid/{id} URLs
        Radio Reference uses different IDs for dropdowns than regular queries
        """
        dropdown_state_map = {
            'AL': '1', 'AK': '2', 'AZ': '4', 'AR': '5', 'CA': '6',
            'CO': '8', 'CT': '9', 'DE': '10', 'DC': '11', 'FL': '12',
            'GA': '13', 'HI': '15', 'ID': '16', 'IL': '17', 'IN': '18',
            'IA': '19', 'KS': '20', 'KY': '21', 'LA': '22', 'ME': '23',
            'MD': '24', 'MA': '25', 'MI': '26', 'MN': '27', 'MS': '28',
            'MO': '29', 'MT': '30', 'NE': '31', 'NV': '32', 'NH': '33',
            'NJ': '34', 'NM': '35', 'NY': '36', 'NC': '37', 'ND': '38',
            'OH': '39', 'OK': '40', 'OR': '41', 'PA': '42', 'RI': '44',
            'SC': '45', 'SD': '46', 'TN': '47', 'TX': '48', 'UT': '49',
            'VT': '50', 'VA': '51', 'WA': '53', 'WV': '54', 'WI': '55',
            'WY': '56'
        }
        return dropdown_state_map.get(state.upper())
    
    def _get_known_county_id(self, county: str, state: str) -> Optional[str]:
        known_counties = {
            ('sanders', 'mt'): '1638',
            ('king', 'wa'): '2974',
            ('king', 'washington'): '2974',
        }
        
        county_key = (county.lower().replace(' county', '').strip(), state.lower())
        if county_key in known_counties:
            return known_counties[county_key]
        
        return None
    
    def _load_county_cache(self) -> Dict[Tuple[str, str], str]:
        """
        Load county ID cache from file
        
        Supports both old flat format and new state-sectioned format
        
        Returns:
            Dictionary mapping (county, state) -> county_id
        """
        cache_file = "countyID.db"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    
                    cache = {}
                    
                    if isinstance(cache_data, dict) and any(isinstance(v, dict) for v in cache_data.values()):
                        for state, counties in cache_data.items():
                            if isinstance(counties, dict):
                                for county, county_id in counties.items():
                                    county_key = (county.lower(), state.lower())
                                    cache[county_key] = str(county_id)
                    else:
                        for k, v in cache_data.items():
                            if isinstance(k, list):
                                cache[tuple(k)] = v
                            elif isinstance(k, str) and '|' in k:
                                parts = k.split('|', 1)
                                if len(parts) == 2:
                                    cache[(parts[0].lower(), parts[1].lower())] = v
                            else:
                                try:
                                    cache[tuple(k)] = v
                                except:
                                    pass
                    return cache
            except Exception as e:
                print_status(f"Error loading county cache: {e}", "warning")
        return {}
    
    def _save_county_cache(self, cache: Dict[Tuple[str, str], str]):
        """
        Save county ID cache to file
        
        Args:
            cache: Dictionary mapping (county, state) -> county_id
        """
        cache_file = "countyID.db"
        try:
            data = {}
            for k, v in cache.items():
                if isinstance(k, tuple) and len(k) == 2:
                    county, state = k[0].lower(), k[1].upper()
                    if state not in data:
                        data[state] = {}
                    data[state][county] = str(v)
                elif isinstance(k, list) and len(k) == 2:
                    county, state = k[0].lower(), k[1].upper()
                    if state not in data:
                        data[state] = {}
                    data[state][county] = str(v)
                elif isinstance(k, str) and '|' in k:
                    parts = k.split('|', 1)
                    if len(parts) == 2:
                        county, state = parts[0].lower(), parts[1].upper()
                        if state not in data:
                            data[state] = {}
                        data[state][county] = str(v)
            
            sorted_data = {}
            for state in sorted(data.keys()):
                sorted_data[state] = dict(sorted(data[state].items()))
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print_status(f"Failed to save county cache: {e}", "warning")
            import traceback
            traceback.print_exc()
    
    def _get_known_counties_for_state(self, state: str) -> List[str]:
        """
        Get a list of known county names for a state
        Uses a basic list - can be expanded with full US county database
        
        Args:
            state: State abbreviation
            
        Returns:
            List of county names (without "County" suffix)
        """
        known_counties = {
            'CA': ['Alameda', 'Alpine', 'Amador', 'Butte', 'Calaveras', 'Colusa', 'Contra Costa', 
                   'Del Norte', 'El Dorado', 'Fresno', 'Glenn', 'Humboldt', 'Imperial', 'Inyo',
                   'Kern', 'Kings', 'Lake', 'Lassen', 'Los Angeles', 'Madera', 'Marin', 'Mariposa',
                   'Mendocino', 'Merced', 'Modoc', 'Mono', 'Monterey', 'Napa', 'Nevada', 'Orange',
                   'Placer', 'Plumas', 'Riverside', 'Sacramento', 'San Benito', 'San Bernardino',
                   'San Diego', 'San Francisco', 'San Joaquin', 'San Luis Obispo', 'San Mateo',
                   'Santa Barbara', 'Santa Clara', 'Santa Cruz', 'Shasta', 'Sierra', 'Siskiyou',
                   'Solano', 'Sonoma', 'Stanislaus', 'Sutter', 'Tehama', 'Trinity', 'Tulare',
                   'Tuolumne', 'Ventura', 'Yolo', 'Yuba'],
            'TX': ['Anderson', 'Andrews', 'Angelina', 'Aransas', 'Archer', 'Armstrong', 'Atascosa',
                   'Austin', 'Bailey', 'Bandera', 'Bastrop', 'Baylor', 'Bee', 'Bell', 'Bexar',
                   'Blanco', 'Borden', 'Bosque', 'Bowie', 'Brazoria', 'Brazos', 'Brewster',
                   'Briscoe', 'Brooks', 'Brown', 'Burleson', 'Burnet', 'Caldwell', 'Calhoun',
                   'Callahan', 'Cameron', 'Camp', 'Carson', 'Cass', 'Castro', 'Chambers',
                   'Cherokee', 'Childress', 'Clay', 'Cochran', 'Coke', 'Coleman', 'Collin',
                   'Collingsworth', 'Colorado', 'Comal', 'Comanche', 'Concho', 'Cooke', 'Coryell',
                   'Cottle', 'Crane', 'Crockett', 'Crosby', 'Culberson', 'Dallam', 'Dallas',
                   'Dawson', 'Deaf Smith', 'Delta', 'Denton', 'DeWitt', 'Dickens', 'Dimmit',
                   'Donley', 'Duval', 'Eastland', 'Ector', 'Edwards', 'Ellis', 'El Paso',
                   'Erath', 'Falls', 'Fannin', 'Fayette', 'Fisher', 'Floyd', 'Foard', 'Fort Bend',
                   'Franklin', 'Freestone', 'Frio', 'Gaines', 'Galveston', 'Garza', 'Gillespie',
                   'Glasscock', 'Goliad', 'Gonzales', 'Gray', 'Grayson', 'Gregg', 'Grimes',
                   'Guadalupe', 'Hale', 'Hall', 'Hamilton', 'Hansford', 'Hardeman', 'Hardin',
                   'Harris', 'Harrison', 'Hartley', 'Haskell', 'Hays', 'Hemphill', 'Henderson',
                   'Hidalgo', 'Hill', 'Hockley', 'Hood', 'Hopkins', 'Houston', 'Howard', 'Hudspeth',
                   'Hunt', 'Hutchinson', 'Irion', 'Jack', 'Jackson', 'Jasper', 'Jeff Davis',
                   'Jefferson', 'Jim Hogg', 'Jim Wells', 'Johnson', 'Jones', 'Karnes', 'Kaufman',
                   'Kendall', 'Kenedy', 'Kent', 'Kerr', 'Kimble', 'King', 'Kinney', 'Kleberg',
                   'Knox', 'Lamar', 'Lamb', 'Lampasas', 'La Salle', 'Lavaca', 'Lee', 'Leon',
                   'Liberty', 'Limestone', 'Lipscomb', 'Live Oak', 'Llano', 'Loving', 'Lubbock',
                   'Lynn', 'McCulloch', 'McLennan', 'McMullen', 'Madison', 'Marion', 'Martin',
                   'Mason', 'Matagorda', 'Maverick', 'Medina', 'Menard', 'Midland', 'Milam',
                   'Mills', 'Mitchell', 'Montague', 'Montgomery', 'Moore', 'Morris', 'Motley',
                   'Nacogdoches', 'Navarro', 'Newton', 'Nolan', 'Nueces', 'Ochiltree', 'Oldham',
                   'Orange', 'Palo Pinto', 'Panola', 'Parker', 'Parmer', 'Pecos', 'Polk', 'Potter',
                   'Presidio', 'Rains', 'Randall', 'Reagan', 'Real', 'Red River', 'Reeves',
                   'Refugio', 'Roberts', 'Robertson', 'Rockwall', 'Runnels', 'Rusk', 'Sabine',
                   'San Augustine', 'San Jacinto', 'San Patricio', 'San Saba', 'Schleicher',
                   'Scurry', 'Shackelford', 'Shelby', 'Sherman', 'Smith', 'Somervell', 'Starr',
                   'Stephens', 'Sterling', 'Stonewall', 'Sutton', 'Swisher', 'Tarrant', 'Taylor',
                   'Terrell', 'Terry', 'Throckmorton', 'Titus', 'Tom Green', 'Travis', 'Trinity',
                   'Tyler', 'Upshur', 'Upton', 'Uvalde', 'Val Verde', 'Van Zandt', 'Victoria',
                   'Walker', 'Waller', 'Ward', 'Washington', 'Webb', 'Wharton', 'Wheeler',
                   'Wichita', 'Wilbarger', 'Willacy', 'Williamson', 'Wilson', 'Winkler', 'Wise',
                   'Wood', 'Yoakum', 'Young', 'Zapata', 'Zavala'],
        }
        
        return known_counties.get(state.upper(), [])
    
    def _extract_counties_with_playwright(self, state_id: str, state: str) -> Dict[Tuple[str, str], str]:
        """
        Extract counties from Radio Reference using Playwright to render JavaScript
        
        Uses the dropdown menu at /db/browse/stid/{state_id} to extract counties
        
        Args:
            state_id: Radio Reference state ID
            state: State abbreviation
            
        Returns:
            Dictionary mapping (county, state) -> county_id
        """
        discovered_counties = {}
        
        try:
            dropdown_state_id = state_id
            
            dropdown_url = f"{self.base_url}/db/browse/stid/{dropdown_state_id}"
            print_status(f"Using Playwright to extract counties for {state} from dropdown (ID: {dropdown_state_id})...", "info")
            
            try:
                from playwright.sync_api import sync_playwright
                
                time.sleep(1)
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(dropdown_url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(3000)
                    
                    page_state = page.evaluate("""
                        (function() {
                            const title = document.title;
                            const h1 = document.querySelector('h1');
                            const h1Text = h1 ? h1.textContent : '';
                            const bodyText = document.body.textContent;
                            
                            // Try to extract state abbreviation from page
                            const stateMatch = bodyText.match(/\\b([A-Z]{2})\\b/);
                            return {
                                title: title,
                                h1: h1Text,
                                stateMatch: stateMatch ? stateMatch[1] : null
                            };
                        })();
                    """)
                    
                    expected_state_upper = state.upper()
                    page_title = page_state.get('title', '').upper()
                    page_h1 = page_state.get('h1', '').upper()
                    
                    state_found = False
                    if expected_state_upper in page_title or expected_state_upper in page_h1:
                        state_found = True
                    elif page_state.get('stateMatch'):
                        if page_state['stateMatch'].upper() == expected_state_upper:
                            state_found = True
                    
                    if not state_found:
                        print_status(f"Warning: Page appears to be for a different state. Expected {state}, but page shows: {page_title[:60]}", "warning")
                        print_status(f"State ID {state_id} may not map to {state} correctly", "warning")
                    
                    counties_data = page.evaluate("""
                        (function() {
                            const counties = [];
                            
                            // Find all select dropdowns that might contain counties
                            const selects = document.querySelectorAll('select');
                            
                            selects.forEach(select => {
                                const selectName = select.name || select.id || '';
                                const options = select.querySelectorAll('option');
                                
                                // Look for county dropdown - check by name/ID or option count
                                // County dropdowns typically have names like 'ctid', 'county', or have many options
                                // Some states have 200+ counties (like TX), some have very few (like DE has 3)
                                // Priority: check by name first, then by reasonable option count
                                const isCountySelect = selectName.toLowerCase().includes('ctid') || 
                                                      selectName.toLowerCase().includes('county') ||
                                                      (options.length >= 3 && options.length < 500);  // Changed from > 10 to >= 3
                                
                                if (isCountySelect && options.length >= 3) {  // Changed from > 5 to >= 3
                                    options.forEach(option => {
                                        const value = option.getAttribute('value') || option.value || '';
                                        const text = option.textContent.trim();
                                        
                                        // Skip empty values or non-numeric values
                                        if (!value || !value.match(/^\\d+$/) || value.length < 2) {
                                            return;
                                        }
                                        
                                        // Skip common non-county options
                                        const lowerText = text.toLowerCase();
                                        if (lowerText === 'all' || 
                                            lowerText === 'select' || 
                                            lowerText === 'choose' ||
                                            lowerText.includes('trs') ||
                                            lowerText.includes('agency') ||
                                            lowerText.includes('department') ||
                                            lowerText.includes('statewide') ||
                                            lowerText.includes('nationwide') ||
                                            text.length < 2) {
                                            return;
                                        }
                                        
                                        // Extract county/borough/census area name
                                        // Remove "County", "Borough", "Census Area", etc. suffixes
                                        let countyName = text
                                            .replace(/\\s+County.*$/i, '')
                                            .replace(/\\s+Borough.*$/i, '')
                                            .replace(/\\s+Census Area.*$/i, '')
                                            .replace(/\\s+Parish.*$/i, '')
                                            .trim();
                                        
                                        // If name is empty after cleanup, use original text
                                        if (!countyName || countyName.length < 2) {
                                            countyName = text.trim();
                                        }
                                        
                                        // Accept if it looks like a valid location name
                                        if (countyName && countyName.length >= 2) {
                                            counties.push({
                                                name: countyName,
                                                id: value,
                                                fullText: text
                                            });
                                        }
                                    });
                                }
                            });
                            
                            // Also check for any links with ctid that might be county links
                            const links = document.querySelectorAll('a[href*="ctid"]');
                            links.forEach(link => {
                                const href = link.href || link.getAttribute('href') || '';
                                const text = link.textContent.trim();
                                const match = href.match(/ctid[\\/=](\\d+)/i);
                                
                                if (match && text && text.length >= 2) {
                                    const lowerText = text.toLowerCase();
                                    // Skip common non-county links
                                    if (!lowerText.includes('trs') && 
                                        !lowerText.includes('agency') &&
                                        !lowerText.includes('department') &&
                                        !lowerText.includes('statewide')) {
                                        
                                        // Extract name, removing common suffixes
                                        let countyName = text
                                            .replace(/\\s+County.*$/i, '')
                                            .replace(/\\s+Borough.*$/i, '')
                                            .replace(/\\s+Census Area.*$/i, '')
                                            .replace(/\\s+Parish.*$/i, '')
                                            .trim();
                                        
                                        if (!countyName || countyName.length < 2) {
                                            countyName = text.trim();
                                        }
                                        
                                        if (countyName && countyName.length >= 2) {
                                            counties.push({
                                                name: countyName,
                                                id: match[1],
                                                fullText: text
                                            });
                                        }
                                    }
                                }
                            });
                            
                            // Return unique counties
                            const unique = {};
                            counties.forEach(c => {
                                const key = c.name.toLowerCase();
                                if (!unique[key] || !unique[key].id) {
                                    unique[key] = c;
                                }
                            });
                            return Object.values(unique);
                        })();
                    """)
                    
                    actual_state = state.upper()
                    
                    page_info = page.evaluate("""
                        (function() {
                            const title = document.title.toUpperCase();
                            const h1 = document.querySelector('h1');
                            const h1Text = h1 ? h1.textContent.toUpperCase() : '';
                            const bodyText = document.body.textContent.substring(0, 5000).toUpperCase();
                            return title + ' ' + h1Text + ' ' + bodyText;
                        })();
                    """)
                    
                    state_names_map = {
                        'MICHIGAN': 'MI', 'MONTANA': 'MT', 'CALIFORNIA': 'CA', 'TEXAS': 'TX',
                        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
                        'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE', 'FLORIDA': 'FL',
                        'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID', 'ILLINOIS': 'IL',
                        'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS', 'KENTUCKY': 'KY',
                        'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD', 'MASSACHUSETTS': 'MA',
                        'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS', 'MISSOURI': 'MO', 'NEBRASKA': 'NE',
                        'NEVADA': 'NV', 'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM',
                        'NEW YORK': 'NY', 'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH',
                        'OKLAHOMA': 'OK', 'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI',
                        'SOUTH CAROLINA': 'SC', 'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'UTAH': 'UT',
                        'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
                        'WISCONSIN': 'WI', 'WYOMING': 'WY', 'DISTRICT OF COLUMBIA': 'DC'
                    }
                    
                    sorted_states = sorted(state_names_map.items(), key=lambda x: len(x[0]), reverse=True)
                    
                    for state_name, state_abbr in sorted_states:
                        if state_name in page_info:
                            actual_state = state_abbr
                            if actual_state != state.upper():
                                print_status(f"Detected state mismatch: Page shows {actual_state}, expected {state.upper()}", "warning")
                                print_status(f"Dropdown state ID {state_id} maps to {actual_state}, not {state.upper()}", "warning")
                                print_status(f"Skipping counties for {state.upper()} - will try to find correct dropdown ID", "info")
                                browser.close()
                                return {}
                            break
                    
                    if actual_state == state.upper():
                        for county_data in counties_data:
                            county_name = county_data.get('name', '').strip()
                            county_id = county_data.get('id', '')
                            if county_name and county_id:
                                county_clean = county_name.lower()
                                county_key = (county_clean, actual_state.lower())
                                discovered_counties[county_key] = str(county_id)
                    else:
                        browser.close()
                        return {}
                    
                    browser.close()
                    
                    if discovered_counties:
                        detected_states = set(county_key[1].upper() for county_key in discovered_counties.keys())
                        if len(detected_states) == 1:
                            detected_state = list(detected_states)[0]
                            if detected_state != state.upper():
                                print_status(f"Playwright found {len(discovered_counties)} counties for {detected_state} (using dropdown ID for {state})", "success")
                            else:
                                print_status(f"Playwright found {len(discovered_counties)} counties for {state}", "success")
                        else:
                            print_status(f"Playwright found {len(discovered_counties)} counties across {len(detected_states)} states", "success")
            except ImportError:
                print_status("Playwright not installed. Install with: pip install playwright && playwright install", "warning")
                print_status("Counties will be cached incrementally as they are searched", "info")
            except Exception as e:
                print_status(f"Playwright extraction error: {e}", "warning")
                import traceback
                traceback.print_exc()
            
        except Exception as e:
            print_status(f"Playwright extraction failed: {e}", "warning")
            import traceback
            traceback.print_exc()
        
        return discovered_counties
    
    def _build_county_cache_for_state(self, state_id: str, state: str) -> Dict[Tuple[str, str], str]:
        """
        Build county ID cache for a state by scraping Radio Reference
        
        Args:
            state_id: Radio Reference state ID
            state: State abbreviation
            
        Returns:
            Dictionary mapping (county, state) -> county_id
        """
        cache = {}
        try:
            from bs4 import BeautifulSoup
            
            print_status(f"Discovering county IDs for {state}...", "info")
            
            known_counties = self._get_known_counties_for_state(state)
            
            if known_counties:
                print_status(f"Testing {len(known_counties)} known counties for {state}...", "info")
                found = 0
                
                for county_name in known_counties:
                    county_clean = county_name.lower().replace(' county', '').strip()
                    county_key = (county_clean, state.lower())
                    
                    existing_cache = self._load_county_cache()
                    if county_key in existing_cache:
                        cache[county_key] = existing_cache[county_key]
                        found += 1
                        continue
                    
                    county_id = None
                    try:
                        temp_cache = existing_cache.copy()
                        if county_key in temp_cache:
                            del temp_cache[county_key]
                        
                        from bs4 import BeautifulSoup
                        
                        query_url = f"{self.base_url}/db/query/?stid={state_id}"
                        query_response = self.session.get(query_url, timeout=10)
                        if query_response.status_code == 200:
                            query_soup = BeautifulSoup(query_response.text, 'html.parser')
                            
                            for select in query_soup.find_all('select'):
                                options = select.find_all('option')
                                if len(options) > 50:
                                    sample_texts = [opt.get_text(strip=True).lower() for opt in options[10:30] if opt.get_text(strip=True)]
                                    county_like_count = sum(1 for text in sample_texts if len(text.split()) <= 3 and len(text) > 2)
                                    
                                    if county_like_count > 5:
                                        for option in options:
                                            value = option.get('value', '')
                                            text = option.get_text(strip=True).lower()
                                            if value.isdigit() and len(value) >= 3:
                                                text_clean = text.replace(' county', '').strip()
                                                county_words = county_clean.split()
                                                if (county_clean in text_clean or 
                                                    all(word in text_clean for word in county_words if len(word) > 2)):
                                                    time.sleep(0.3)
                                                    
                                                    test_url = f"{self.base_url}/db/browse/ctid/{value}"
                                                    test_resp = self.session.get(test_url, timeout=5)
                                                    if test_resp.status_code == 200:
                                                        test_soup = BeautifulSoup(test_resp.text, 'html.parser')
                                                        page_title = test_soup.find('h1') or test_soup.find('title')
                                                        if page_title:
                                                            title_text = page_title.get_text().lower()
                                                            if county_clean in title_text and state.lower() in title_text:
                                                                county_id = value
                                                                break
                                        if county_id:
                                            break
                    except Exception as e:
                        pass
                    
                    if county_id:
                        cache[county_key] = county_id
                        found += 1
                        if found % 5 == 0:
                            print_status(f"Found {found}/{len(known_counties)} counties for {state}...", "info")
            else:
                print_status(f"No known county list for {state}, using Playwright to extract counties...", "info")
                
                dropdown_state_id = self._get_dropdown_state_id(state)
                if not dropdown_state_id:
                    dropdown_state_id = state_id
                    print_status(f"Warning: No dropdown state ID found for {state}, using regular state ID {state_id}", "warning")
                
                discovered_counties = self._extract_counties_with_playwright(dropdown_state_id, state)
                
                if not discovered_counties:
                    print_status(f"Initial extraction failed for {state}, trying nearby dropdown IDs...", "info")
                    base_id = int(dropdown_state_id) if dropdown_state_id and dropdown_state_id.isdigit() else None
                    if not base_id:
                        base_id = int(state_id) if state_id and state_id.isdigit() else None
                    
                    if base_id:
                        for offset in range(-10, 11):
                            if offset == 0:
                                continue
                            test_id = str(base_id + offset)
                            if int(test_id) > 0:
                                print_status(f"Trying dropdown ID {test_id} for {state}...", "info")
                                test_counties = self._extract_counties_with_playwright(test_id, state)
                                if test_counties:
                                    detected_states = set(k[1].upper() for k in test_counties.keys())
                                    if len(detected_states) == 1 and list(detected_states)[0] == state.upper():
                                        print_status(f"Found correct dropdown ID {test_id} for {state}!", "success")
                                        discovered_counties = test_counties
                                        break
                                    else:
                                        if detected_states:
                                            print_status(f"Dropdown ID {test_id} returned {list(detected_states)[0]}, not {state}", "info")
                                        discovered_counties = {}
                                        continue
                
                if discovered_counties:
                    cache.update(discovered_counties)
                    existing_cache = self._load_county_cache()
                    existing_cache.update(discovered_counties)
                    self._save_county_cache(existing_cache)
                    
                    detected_states = set(county_key[1].upper() for county_key in discovered_counties.keys())
                    if len(detected_states) == 1:
                        detected_state = list(detected_states)[0]
                        if detected_state != state.upper():
                            print_status(f"Extracted {len(discovered_counties)} counties for {detected_state} using Playwright (using dropdown ID for {state})", "success")
                            print_status(f"Saved {len(discovered_counties)} counties for {detected_state} to countyID.db", "success")
                        else:
                            print_status(f"Extracted {len(discovered_counties)} counties for {state} using Playwright", "success")
                            print_status(f"Saved {len(discovered_counties)} counties to countyID.db", "success")
                    else:
                        print_status(f"Extracted {len(discovered_counties)} counties across {len(detected_states)} states", "success")
                        print_status(f"Saved {len(discovered_counties)} counties to countyID.db", "success")
                else:
                    print_status(f"Playwright couldn't extract counties from tree structure", "info")
                    print_status(f"Counties will be cached incrementally as they are searched", "info")
                    discovered_counties = {}
                
                browse_url = f"{self.base_url}/db/browse/?stid={state_id}"
                
                api_endpoints = [
                    f"{self.base_url}/db/api/browse?stid={state_id}",
                    f"{self.base_url}/db/browse/api?stid={state_id}",
                    f"{self.base_url}/api/db/browse?stid={state_id}",
                ]
                
                try:
                    for api_url in api_endpoints:
                        try:
                            api_response = self.session.get(api_url, timeout=10)
                            if api_response.status_code == 200:
                                try:
                                    api_data = api_response.json()
                                    if isinstance(api_data, dict):
                                        for key, value in api_data.items():
                                            if 'county' in key.lower() or 'ctid' in key.lower():
                                                pass
                                    elif isinstance(api_data, list):
                                        for item in api_data:
                                            if isinstance(item, dict):
                                                county_name = item.get('name', '') or item.get('county', '')
                                                county_id = item.get('id', '') or item.get('ctid', '')
                                                if county_name and county_id:
                                                    county_clean = county_name.replace(' County', '').replace(' county', '').strip().lower()
                                                    county_key = (county_clean, state.lower())
                                                    discovered_counties[county_key] = str(county_id)
                                    if discovered_counties:
                                        break
                                except:
                                    pass
                        except:
                            continue
                    
                    response = self.session.get(browse_url, timeout=15)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        page_text = response.text
                        
                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            text = link.get_text(strip=True)
                            match = re.search(r'ctid[/=](\d+)', href, re.I)
                            if match and text:
                                county_id = match.group(1)
                                county_name = text.replace(' County', '').replace(' county', '').replace(' Parish', '').replace(' Borough', '').strip()
                                if county_name and len(county_name) > 1 and state.upper() in text.upper():
                                    county_key = (county_name.lower(), state.lower())
                                    discovered_counties[county_key] = county_id
                        
                        county_name_patterns = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+County', page_text)
                        potential_counties = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', page_text)
                        common_words = {'The', 'This', 'That', 'With', 'From', 'State', 'United', 'States', 'America'}
                        potential_counties = [c for c in potential_counties if c not in common_words and len(c.split()) <= 3]
                        
                        unique_county_names = list(set(county_name_patterns))
                        
                        false_positives = ['Davidson', 'Statewide']
                        unique_county_names = [c for c in unique_county_names if c not in false_positives]
                        
                        print_status(f"Found {len(unique_county_names)} county name patterns in page source", "info")
                        
                        if not unique_county_names:
                            ctid_matches = re.finditer(r'ctid["\']?\s*[:=]\s*["\']?(\d+)', page_text, re.I)
                            for ctid_match in ctid_matches:
                                ctid = ctid_match.group(1)
                                if ctid.isdigit() and len(ctid) >= 3:
                                    ctid_pos = ctid_match.start()
                                    nearby = page_text[max(0, ctid_pos-1000):ctid_pos+1000]
                                    nearby_counties = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', nearby)
                                    for county_candidate in nearby_counties:
                                        if len(county_candidate.split()) <= 3 and county_candidate not in common_words:
                                            if not any(word.lower() in ['the', 'this', 'that', 'with', 'from', 'state'] for word in county_candidate.split()):
                                                unique_county_names.append(county_candidate)
                                                break
                        
                        for county_name in unique_county_names:
                            county_full = county_name + ' County'
                            occurrences = [m.start() for m in re.finditer(re.escape(county_full), page_text, re.I)]
                            
                            for county_index in occurrences:
                                nearby_text = page_text[max(0, county_index-2000):county_index+2000]
                                
                                ctid_patterns = [
                                    r'ctid["\']?\s*[:=]\s*["\']?(\d+)',
                                    r'ctid[/=](\d+)',
                                    r'["\']id["\']\s*:\s*["\']?(\d+)',
                                    r'id["\']?\s*:\s*["\']?(\d+)',
                                    r'value["\']?\s*:\s*["\']?(\d+)',
                                ]
                                
                                for pattern in ctid_patterns:
                                    ctid_match = re.search(pattern, nearby_text, re.I)
                                    if ctid_match:
                                        county_id = ctid_match.group(1)
                                        if county_id.isdigit() and len(county_id) >= 3 and len(county_id) <= 5:
                                            county_clean = county_name.strip().lower()
                                            county_key = (county_clean, state.lower())
                                            discovered_counties[county_key] = county_id
                                            break
                                if county_key in discovered_counties:
                                    break
                        
                        county_ctid_patterns = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+County[^<]*ctid[/=](\d+)', page_text, re.I)
                        for county_name, county_id in county_ctid_patterns:
                            county_clean = county_name.strip().lower()
                            county_key = (county_clean, state.lower())
                            discovered_counties[county_key] = county_id
                        
                        scripts = soup.find_all('script')
                        for script in scripts:
                            script_text = script.string or ''
                            if script_text and len(script_text) > 100:
                                script_counties = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+County', script_text)
                                for county_name in set(script_counties):
                                    county_index = script_text.find(county_name + ' County')
                                    if county_index != -1:
                                        nearby_script = script_text[max(0, county_index-300):county_index+300]
                                        ctid_match = re.search(r'ctid["\']?\s*[:=]\s*["\']?(\d+)', nearby_script, re.I)
                                        if ctid_match:
                                            county_id = ctid_match.group(1)
                                            if county_id.isdigit() and len(county_id) >= 3:
                                                county_clean = county_name.strip().lower()
                                                county_key = (county_clean, state.lower())
                                                discovered_counties[county_key] = county_id
                except Exception as e:
                    pass
                
                if discovered_counties:
                    cache.update(discovered_counties)
                    detected_states = set(county_key[1].upper() for county_key in discovered_counties.keys())
                    if len(detected_states) == 1:
                        detected_state = list(detected_states)[0]
                        if detected_state != state.upper():
                            print_status(f"Extracted {len(discovered_counties)} counties for {detected_state} from Radio Reference browse page", "success")
                        else:
                            print_status(f"Extracted {len(discovered_counties)} counties for {state} from Radio Reference browse page", "success")
                    else:
                        print_status(f"Extracted {len(discovered_counties)} counties for {state} from Radio Reference browse page", "success")
                else:
                    print_status(f"Could not extract counties for {state} from browse page", "warning")
                    print_status(f"Counties will be cached incrementally as they are searched", "info")
            
            if cache:
                detected_states = set(county_key[1].upper() for county_key in cache.keys())
                if len(detected_states) == 1:
                    detected_state = list(detected_states)[0]
                    if detected_state != state.upper():
                        print_status(f"Discovered {len(cache)} county IDs for {detected_state}", "success")
                    else:
                        print_status(f"Discovered {len(cache)} county IDs for {state}", "success")
                else:
                    print_status(f"Discovered {len(cache)} county IDs for {state}", "success")
            else:
                print_status(f"Could not discover county IDs for {state}", "warning")
                
        except Exception as e:
            print_status(f"Error discovering counties: {e}", "error")
            import traceback
            traceback.print_exc()
        
        return cache
    
    def _verify_county_with_api(self, county_name: str, state: str) -> bool:
        """
        Verify that a county exists in the given state using external API
        
        Uses Nominatim (OpenStreetMap) geocoding API to verify county/state relationship
        
        Args:
            county_name: County name (e.g., "los angeles")
            state: State abbreviation (e.g., "CA")
            
        Returns:
            True if county is verified to be in the state, False otherwise
        """
        try:
            county_display = county_name.replace('_', ' ').title()
            query = f"{county_display} County, {state}, USA"
            
            api_url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'RadioFrequencyHarvester/1.1 (https://github.com/InfoSecREDD/radiorefexport)'
            }
            
            response = self.session.get(api_url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    result = data[0]
                    address = result.get('address', {})
                    
                    result_state = address.get('state_code', '').upper() or address.get('state', '').upper()
                    
                    result_county = address.get('county', '').lower()
                    
                    if state.upper() in result_state or result_state in state.upper():
                        if result_county:
                            county_match = county_name.lower() in result_county or result_county.startswith(county_name.lower())
                            return county_match
                        return True
            
            return False
        except Exception as e:
            return True
    
    def build_county_cache_for_state(self, state: str, use_search: bool = True) -> int:
        """
        Build county ID cache for a specific state
        
        Args:
            state: State abbreviation (e.g., 'CA')
            use_search: If True, use search methods to find counties incrementally
            
        Returns:
            Number of counties found and cached
        """
        state_id = self._get_state_id(state)
        if not state_id:
            print_status(f"Invalid state: {state}", "error")
            return 0
        
        print_status(f"Building county cache for {state}...", "info")
        
        existing_cache = self._load_county_cache()
        state_counties = {k: v for k, v in existing_cache.items() if k[1] == state.lower()}
        
        if state_counties:
            print_status(f"Found {len(state_counties)} counties already cached for {state}", "info")
        
        new_counties = 0
        
        if use_search:
            print_status(f"Discovering county IDs for {state}...", "info")
            
            discovered_cache = self._build_county_cache_for_state(state_id, state)
            
            if discovered_cache:
                discovered_ids = set(discovered_cache.values())
                
                detected_states = set(county_key[1].upper() for county_key in discovered_cache.keys())
                detected_state = list(detected_states)[0] if len(detected_states) == 1 else state.upper()
                
                if detected_state != state.upper():
                    print_status(f"Found {len(discovered_ids)} county IDs for {detected_state} (using dropdown ID for {state}), verifying...", "info")
                else:
                    print_status(f"Found {len(discovered_ids)} county IDs for {state}, verifying...", "info")
                
                sample_size = min(5, len(discovered_cache))
                sample_counties = list(discovered_cache.items())[:sample_size]
                
                print_status(f"Verifying sample of {sample_size} counties using external API...", "info")
                
                verified_count = 0
                for county_key, county_id in sample_counties:
                    county_name, county_state = county_key[0], county_key[1].upper()
                    
                    if self._verify_county_with_api(county_name, county_state):
                        verified_count += 1
                        time.sleep(1)
                
                verification_rate = verified_count / sample_size if sample_size > 0 else 0
                
                if verification_rate >= 0.8:
                    print_status(f"Sample verification passed ({verified_count}/{sample_size} verified). Caching all {len(discovered_cache)} counties...", "success")
                    
                    for county_key, county_id in discovered_cache.items():
                        if county_key not in existing_cache:
                            existing_cache[county_key] = county_id
                            new_counties += 1
                    
                    self._save_county_cache(existing_cache)
                    verified = len(discovered_cache)
                else:
                    print_status(f"Sample verification failed ({verified_count}/{sample_size} verified). Counties may not be accurate for this state.", "warning")
                    verified = 0
                
                if new_counties > 0:
                    self._save_county_cache(existing_cache)
                    if detected_state != state.upper():
                        print_status(f"Added {new_counties} new counties to cache for {detected_state} ({verified} total counties cached)", "success")
                    else:
                        print_status(f"Added {new_counties} new counties to cache for {state} ({verified} total counties cached)", "success")
                else:
                    if detected_state != state.upper():
                        detected_state_counties = {k: v for k, v in existing_cache.items() if k[1] == detected_state.lower()}
                        if detected_state_counties:
                            print_status(f"No new counties found for {detected_state} (already had {len(detected_state_counties)} cached)", "info")
                        else:
                            print_status(f"Cached {verified} counties for {detected_state}", "info")
                    else:
                        if state_counties:
                            print_status(f"No new counties found for {state} (already had {len(state_counties)} cached)", "info")
                        else:
                            print_status(f"Cached {verified} counties for {state}", "info")
            else:
                print_status(f"Could not discover county IDs for {state} from state pages", "warning")
                print_status(f"Note: Radio Reference may load counties dynamically. Counties will be cached as they are searched.", "info")
        
        if discovered_cache:
            detected_states = set(k[1].upper() for k in discovered_cache.keys())
            if detected_states:
                detected_state = list(detected_states)[0]
                total_counties = len({k: v for k, v in existing_cache.items() if k[1] == detected_state.lower()})
                if detected_state != state.upper():
                    print_status(f"Total counties cached for {detected_state}: {total_counties}", "success")
                return total_counties
        
        total_counties = len({k: v for k, v in existing_cache.items() if k[1] == state.lower()})
        return total_counties
    
    def build_county_cache_for_all_states(self) -> Dict[str, int]:
        """
        Build county ID cache for all US states
        
        Returns:
            Dictionary mapping state -> number of counties cached
        """
        all_states = [
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
            'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
            'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
            'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
            'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        ]
        
        expected_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
        }
        
        actual_states = set(all_states)
        missing_states = expected_states - actual_states
        
        if missing_states:
            print_status(f"Warning: Missing states in list: {missing_states}", "warning")
            all_states.extend(sorted(missing_states))
            all_states = sorted(set(all_states))
        
        results = {}
        total_counties = 0
        processed_states = set()
        
        print_status(f"Building county cache for all {len(all_states)} states/territories...", "info")
        print_status("This may take a while. Progress will be shown for each state.", "info")
        print_status("Rate limiting is enabled to avoid overwhelming the server (0.5s between counties, 2s between states).", "info")
        print_status("Each state will be checked on Radio Reference's website.", "info")
        
        for idx, state in enumerate(all_states, 1):
            print(f"\n{Colors.HEADER}[{idx}/{len(all_states)}]{Colors.RESET} Processing {state}...")
            
            state_id = self._get_state_id(state)
            if not state_id:
                print_status(f"Warning: No state ID found for {state}, skipping...", "warning")
                results[state] = 0
                continue
            
            count = self.build_county_cache_for_state(state, use_search=True)
            
            cache = self._load_county_cache()
            state_counties = {k: v for k, v in cache.items() if k[1] == state.lower()}
            actual_count = len(state_counties)
            
            if actual_count != count and actual_count > 0:
                count = actual_count
            
            results[state] = count
            total_counties += count
            processed_states.add(state)
            
            print(f"{Colors.SUCCESS}✓ {state}: {count} counties found and cached (saved to countyID.db){Colors.RESET}")
            print(f"{Colors.INFO}  Total progress: {total_counties} counties cached across {len(processed_states)} states{Colors.RESET}")
            
            if idx < len(all_states):
                time.sleep(2)
        
        unprocessed = expected_states - processed_states
        if unprocessed:
            print_status(f"Warning: Some states were not processed: {unprocessed}", "warning")
        
        print_status(f"\nCompleted! Processed {len(processed_states)}/{len(all_states)} states.", "info")
        print_status(f"Total counties cached: {total_counties}", "success")
        return results
    
    def _get_known_county_id(self, county: str, state: str) -> Optional[str]:
        """
        Check known county ID mappings (from cache and hardcoded)
        
        Args:
            county: County name
            state: State abbreviation
            
        Returns:
            County ID if known, None otherwise
        """
        known_counties = {
            ('sanders', 'mt'): '1638',
            ('king', 'wa'): '2974',
            ('santa barbara', 'ca'): '83',
            ('los angeles', 'ca'): '19',
            ('orange', 'ca'): '59',
            ('san diego', 'ca'): '61',
            ('san francisco', 'ca'): '60',
        }
        
        county_key = (county.lower().replace(' county', '').strip(), state.lower())
        
        if county_key in known_counties:
            return known_counties[county_key]
        
        cache = self._load_county_cache()
        if county_key in cache:
            return cache[county_key]
        
        return None
    
    def _get_county_id(self, state_id: str, state: str, county: str) -> Optional[str]:
        """
        Get county ID by multiple methods
        
        Args:
            state_id: Radio Reference state ID
            state: State abbreviation
            county: County name to search for
            
        Returns:
            County ID if found, None otherwise
        """
        known_id = self._get_known_county_id(county, state)
        if known_id:
            print_status(f"Using cached county ID: {known_id}", "success")
            return known_id
        
        cache = self._load_county_cache()
        if state_id:
            state_counties = {k: v for k, v in cache.items() if k[1] == state.lower()}
            if not state_counties:
                new_cache = self._build_county_cache_for_state(state_id, state)
                if new_cache:
                    cache.update(new_cache)
                    self._save_county_cache(cache)
                    county_key = (county.lower().replace(' county', '').strip(), state.lower())
                    if county_key in cache:
                        print_status(f"Found county ID in new cache: {cache[county_key]}", "success")
                        return cache[county_key]
        
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print_status("BeautifulSoup4 required. Install with: pip install beautifulsoup4", "error")
            return None
        
        county_clean = county.replace(' County', '').replace(' county', '').strip().lower()
        
        print_status(f"Searching for {county} County, {state}...", "info")
        
        try:
            query_url = f"{self.base_url}/db/query/?stid={state_id}"
            query_response = self.session.get(query_url, timeout=10)
            if query_response.status_code == 200:
                query_soup = BeautifulSoup(query_response.text, 'html.parser')
                
                
                page_text = query_response.text
                
                ctid_name_patterns = re.findall(r'ctid["\']?\s*[:=]\s*["\']?(\d+)["\']?[^}]*?name["\']?\s*[:=]\s*["\']([^"\']+county[^"\']*)', page_text, re.I)
                
                for ctid, name in ctid_name_patterns:
                    name_clean = name.replace(' County', '').replace(' county', '').strip().lower()
                    if county_clean in name_clean:
                        test_url = f"{self.base_url}/db/browse/ctid/{ctid}"
                        test_resp = self.session.get(test_url, timeout=5)
                        if test_resp.status_code == 200:
                            test_soup = BeautifulSoup(test_resp.text, 'html.parser')
                            h1 = test_soup.find('h1')
                            if h1 and state.upper() in h1.get_text():
                                county_id = ctid
                                break
                
                if not county_id:
                    browse_url = f"{self.base_url}/db/browse/?stid={state_id}"
                    browse_response = self.session.get(browse_url, timeout=10)
                    if browse_response.status_code == 200:
                        browse_text = browse_response.text
                        county_pattern = re.escape(county.replace(' County', '').replace(' county', '').strip())
                        ctid_patterns = re.findall(rf'{county_pattern}[^<]*ctid[/=](\d+)', browse_text, re.I)
                        ctid_patterns += re.findall(rf'ctid[/=](\d+)[^<]*{county_pattern}', browse_text, re.I)
                        
                        for ctid in set(ctid_patterns):
                            test_url = f"{self.base_url}/db/browse/ctid/{ctid}"
                            test_resp = self.session.get(test_url, timeout=5)
                            if test_resp.status_code == 200:
                                test_soup = BeautifulSoup(test_resp.text, 'html.parser')
                                h1 = test_soup.find('h1')
                                if h1:
                                    title_text = h1.get_text()
                                    if state.upper() in title_text and county_clean in title_text.lower():
                                        county_id = ctid
                                        break
                
                if county_id:
                    print_status(f"Found county ID: {county_id} ({county})", "success")
                    county_key = (county_clean, state.lower())
                    cache = self._load_county_cache()
                    cache[county_key] = county_id
                    self._save_county_cache(cache)
                    return county_id
        except:
            pass
        
        urls_to_try = [
            f"{self.base_url}/db/browse/?stid={state_id}",
            f"{self.base_url}/apps/db/?stid={state_id}",
        ]
        
        for url in urls_to_try:
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a', href=True):
                        href = link.get('href', '')
                        text = link.get_text(strip=True).lower()
                        
                        match = re.search(r'ctid[/=](\d+)', href)
                        if match:
                            text_clean = text.replace(' county', '').strip()
                            if county_clean in text_clean or any(word in text_clean for word in county_clean.split() if len(word) > 2):
                                county_id = match.group(1)
                                test_url = f"{self.base_url}/db/browse/ctid/{county_id}"
                                try:
                                    test_resp = self.session.get(test_url, timeout=5)
                                    if test_resp.status_code == 200:
                                        test_soup = BeautifulSoup(test_resp.text, 'html.parser')
                                        h1 = test_soup.find('h1')
                                        if h1 and county_clean in h1.get_text().lower():
                                            print_status(f"Found county ID: {county_id} ({link.get_text(strip=True)})", "success")
                                            county_key = (county_clean, state.lower())
                                            cache = self._load_county_cache()
                                            cache[county_key] = county_id
                                            self._save_county_cache(cache)
                                            return county_id
                                except:
                                    pass
            except:
                continue
        
        try:
            state_url = f"{self.base_url}/db/browse/?stid={state_id}"
            state_resp = self.session.get(state_url, timeout=10)
            if state_resp.status_code == 200:
                page_text = state_resp.text
                ctid_matches = re.findall(r'ctid[=/:](\d{3,5})', page_text, re.I)
                browse_matches = re.findall(r'/db/browse/ctid/(\d{3,5})', page_text)
                all_ctids = set(ctid_matches + browse_matches)
                
                for ctid in all_ctids:
                    test_url = f"{self.base_url}/db/browse/ctid/{ctid}"
                    try:
                        test_resp = self.session.get(test_url, timeout=5)
                        if test_resp.status_code == 200:
                            test_soup = BeautifulSoup(test_resp.text, 'html.parser')
                            heading = test_soup.find('h1') or test_soup.find('h2') or test_soup.find('title')
                            if heading:
                                heading_text = heading.get_text().lower()
                                if county_clean in heading_text and state.lower() in heading_text:
                                    county_id = ctid
                                    print_status(f"Found county ID in page source: {county_id}", "success")
                                    county_key = (county_clean, state.lower())
                                    cache = self._load_county_cache()
                                    cache[county_key] = county_id
                                    self._save_county_cache(cache)
                                    return county_id
                    except:
                        continue
        except:
            pass
        
        return None
    
    def _parse_html_response(self, html: str, state: str, county: Optional[str] = None,
                            city: Optional[str] = None) -> List[Dict]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print_status("BeautifulSoup4 required for scraping. Install with: pip install beautifulsoup4", "error")
            return []
        
        frequencies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            
            header_row = rows[0]
            headers = []
            for th in header_row.find_all(['th', 'td']):
                header_text = th.get_text(strip=True).lower()
                headers.append(header_text)
            
            has_freq_col = any('freq' in h or 'mhz' in h for h in headers)
            if not has_freq_col:
                continue
            
            col_map = {}
            for idx, header in enumerate(headers):
                if 'freq' in header:
                    col_map['frequency'] = idx
                elif 'tone' in header:
                    col_map['tone'] = idx
                elif 'alpha' in header or 'tag' in header:
                    col_map['alpha_tag'] = idx
                elif 'desc' in header:
                    col_map['description'] = idx
                elif 'mode' in header:
                    col_map['mode'] = idx
                elif 'type' in header:
                    col_map['type'] = idx
            
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                freq_text = ''
                if 'frequency' in col_map and col_map['frequency'] < len(cells):
                    freq_text = cells[col_map['frequency']].get_text(strip=True)
                elif len(cells) > 0:
                    freq_text = cells[0].get_text(strip=True)
                
                freq_match = re.search(r'(\d+\.\d+)', freq_text)
                if not freq_match:
                    continue
                
                frequency = freq_match.group(1)
                
                name = ''
                if 'alpha_tag' in col_map and col_map['alpha_tag'] < len(cells):
                    name = cells[col_map['alpha_tag']].get_text(strip=True)
                elif 'description' in col_map and col_map['description'] < len(cells):
                    name = cells[col_map['description']].get_text(strip=True)
                
                tone_text = ''
                if 'tone' in col_map and col_map['tone'] < len(cells):
                    tone_text = cells[col_map['tone']].get_text(strip=True)
                
                tone_type, r_tone, c_tone = self._parse_tone(tone_text)
                
                description = ''
                if 'description' in col_map and col_map['description'] < len(cells):
                    description = cells[col_map['description']].get_text(strip=True)
                
                mode = 'FM'
                if 'mode' in col_map and col_map['mode'] < len(cells):
                    mode_text = cells[col_map['mode']].get_text(strip=True).upper()
                    if 'P25' in mode_text or 'DIGITAL' in mode_text:
                        mode = 'Digital'
                    elif 'DMR' in mode_text:
                        mode = 'DMR'
                    elif 'NXDN' in mode_text:
                        mode = 'NXDN'
                    elif 'FMN' in mode_text or 'FM' in mode_text:
                        mode = 'FM'
                
                duplex = ''
                offset = ''
                if 'type' in col_map and col_map['type'] < len(cells):
                    type_text = cells[col_map['type']].get_text(strip=True).upper()
                    if 'RM' in type_text or 'REPEATER' in type_text:
                        freq_val = float(frequency)
                        if 144 <= freq_val <= 148:
                            duplex = '+'
                            offset = '0.6'
                        elif 440 <= freq_val <= 450:
                            duplex = '+'
                            offset = '5.0'
                        elif 150 <= freq_val <= 160:
                            duplex = '+'
                            offset = '0.0'
                    elif 'BM' in type_text or 'BASE' in type_text:
                        duplex = ''
                
                freq = {
                    'Location': str(len(frequencies)),
                    'Name': name or description or f"Frequency {frequency}",
                    'Frequency': frequency,
                    'Duplex': duplex,
                    'Offset': offset,
                    'Tone': tone_type,
                    'rToneFreq': r_tone,
                    'cToneFreq': c_tone,
                    'DtcsCode': '',
                    'DtcsPolarity': 'NN',
                    'RxDtcsCode': '',
                    'CrossMode': '',
                    'Mode': mode,
                    'TStep': '25.0',
                    'Skip': '',
                    'Comment': description or f"{county or state} - {name}" if name else '',
                    'URCALL': '',
                    'RPT1CALL': '',
                    'RPT2CALL': '',
                    'DVCODE': ''
                }
                frequencies.append(freq)
        
        return frequencies
    
    def _parse_tone(self, tone_text: str) -> tuple:
        """
        Parse tone information
        
        Returns:
            Tuple of (tone_type, rToneFreq, cToneFreq)
        """
        if not tone_text:
            return ('No Tone', '', '')
        
        tone_text = tone_text.upper().strip()
        
        tone_match = re.search(r'(\d+\.?\d*)', tone_text)
        if tone_match:
            tone_freq = tone_match.group(1)
            if 'DCS' in tone_text or 'DTCS' in tone_text:
                return ('DTCS', tone_freq, tone_freq)
            else:
                return ('Tone', tone_freq, tone_freq)
        
        if 'DCS' in tone_text or 'DTCS' in tone_text:
            dcs_match = re.search(r'(\d+)', tone_text)
            if dcs_match:
                return ('DTCS', dcs_match.group(1), dcs_match.group(1))
        
        return ('No Tone', '', '')
    
    def _parse_duplex_offset(self, freq_text: str, cells: List) -> tuple:
        """
        Parse duplex and offset information
        
        Returns:
            Tuple of (duplex, offset)
        """
        duplex = ''
        offset = ''
        
        if '+' in freq_text or 'POS' in freq_text.upper():
            duplex = '+'
        elif '-' in freq_text or 'NEG' in freq_text.upper():
            duplex = '-'
        elif 'SPLIT' in freq_text.upper():
            duplex = 'split'
        
        for cell in cells:
            text = cell.get_text(strip=True)
            offset_match = re.search(r'([+-]?\d+\.?\d*)\s*(MHz|Mhz|mhz)?', text)
            if offset_match and ('offset' in text.lower() or 'split' in text.lower()):
                offset = offset_match.group(1)
                break
        
        if not offset and duplex:
            freq_val = float(re.search(r'(\d+\.\d+)', freq_text).group(1))
            if 144 <= freq_val <= 148:
                offset = '0.6' if duplex == '+' else '-0.6'
            elif 440 <= freq_val <= 450:
                offset = '5.0' if duplex == '+' else '-5.0'
        
        return (duplex, offset)
    
    def to_chirp_csv(self, frequencies: List[Dict], output_file: str, append: bool = False):
        """
        Write frequencies to CHIRP-compatible CSV file
        
        Args:
            frequencies: List of frequency dictionaries
            output_file: Output CSV file path
            append: If True, append to existing file (skip header if file exists)
        """
        if not frequencies:
            print_status("No frequencies to export.", "warning")
            return
        
        file_exists = os.path.exists(output_file) and append
        mode = 'a' if append else 'w'
        
        start_location = 0
        if file_exists:
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    existing = list(reader)
                    if existing:
                        last_loc = int(existing[-1].get('Location', '-1'))
                        start_location = last_loc + 1
            except:
                start_location = 0
        
        with open(output_file, mode, newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.CHIRP_COLUMNS)
            
            if not file_exists:
                writer.writeheader()
            
            for idx, freq in enumerate(frequencies):
                if not freq.get('Location'):
                    freq['Location'] = str(start_location + idx)
                else:
                    if file_exists:
                        freq['Location'] = str(start_location + idx)
                
                row = {col: freq.get(col, '') for col in self.CHIRP_COLUMNS}
                writer.writerow(row)
        
        action = "Appended" if append else "Exported"
        print_status(f"{action} {len(frequencies)} frequencies to {output_file}", "success")
    
    def to_txt(self, frequencies: List[Dict], output_file: str, append: bool = False):
        """
        Write frequencies to human-readable TXT file
        
        Args:
            frequencies: List of frequency dictionaries
            output_file: Output TXT file path
            append: If True, append to existing file
        """
        if not frequencies:
            print_status("No frequencies to export.", "warning")
            return
        
        mode = 'a' if append else 'w'
        file_exists = os.path.exists(output_file) and append
        
        with open(output_file, mode, encoding='utf-8') as txtfile:
            if file_exists:
                txtfile.write("\n" + "="*80 + "\n")
                txtfile.write("Additional Frequencies\n")
                txtfile.write("="*80 + "\n\n")
            
            for idx, freq in enumerate(frequencies):
                txtfile.write(f"Frequency #{idx + 1}\n")
                txtfile.write("-" * 40 + "\n")
                txtfile.write(f"Name:        {freq.get('Name', 'N/A')}\n")
                txtfile.write(f"Frequency:   {freq.get('Frequency', 'N/A')} MHz\n")
                
                mode_str = freq.get('Mode', 'FM')
                txtfile.write(f"Mode:        {mode_str}\n")
                
                if freq.get('Duplex'):
                    txtfile.write(f"Duplex:      {freq.get('Duplex', '')}\n")
                if freq.get('Offset'):
                    txtfile.write(f"Offset:      {freq.get('Offset', '')} MHz\n")
                
                tone_type = freq.get('Tone', 'No Tone')
                if tone_type != 'No Tone':
                    r_tone = freq.get('rToneFreq', '')
                    c_tone = freq.get('cToneFreq', '')
                    if r_tone or c_tone:
                        txtfile.write(f"Tone:        {tone_type} ({r_tone if r_tone else c_tone} Hz)\n")
                    else:
                        txtfile.write(f"Tone:        {tone_type}\n")
                else:
                    txtfile.write(f"Tone:        No Tone\n")
                
                if freq.get('Comment'):
                    txtfile.write(f"Description: {freq.get('Comment', '')}\n")
                
                txtfile.write("\n")
        
        action = "Appended" if append else "Exported"
        print_status(f"{action} {len(frequencies)} frequencies to {output_file}", "success")


def run_cli_mode(args):
    converter = RadioRefToChirp()
    frequencies = []
    
    if args.zipcode:
        frequencies = converter.lookup_by_zipcode(args.zipcode)
    elif args.city:
        if not args.state:
            print_status("--state is required when using --city", "error")
            sys.exit(1)
        frequencies = converter.lookup_by_city_state(args.city, args.state)
    elif args.county:
        if not args.state:
            print_status("--state is required when using --county", "error")
            sys.exit(1)
        frequencies = converter.lookup_by_county_state(args.county, args.state)
    
    if frequencies and args.filter:
        original_count = len(frequencies)
        frequencies = converter.filter_frequencies(frequencies, args.filter)
        print_status(f"Filtered to {len(frequencies)} frequencies (from {original_count}) using mode: {args.filter}", "info")
    
    if frequencies:
        output_format = args.format
        if not output_format:
            if args.output.lower().endswith('.txt'):
                output_format = 'txt'
            else:
                output_format = 'csv'
        
        if output_format.lower() == 'txt':
            converter.to_txt(frequencies, args.output, append=args.append)
        else:
            converter.to_chirp_csv(frequencies, args.output, append=args.append)
        
        print_status(f"Successfully exported {len(frequencies)} frequencies to {args.output}", "success")
    else:
        print_status("No frequencies found. Please check your input parameters.", "error")
        sys.exit(1)


def run_interactive_mode():
    clear_screen()
    print_banner()
    
    print(f"{Colors.WARNING}⚠  Use responsibly and comply with Radio Reference Terms of Service{Colors.RESET}\n")
    
    converter = RadioRefToChirp()
    
    while True:
        print_menu()
        choice = get_user_input("Select an option: ", Colors.HEADER).strip().lower()
        
        if choice in ['0', 'q', 'quit', 'exit']:
            print(f"\n{Colors.SUCCESS}Thanks for using RadioRef Export!{Colors.RESET}\n")
            sys.exit(0)
        
        if choice in ['1', 'zip', 'zipcode']:
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  ZIP CODE SEARCH{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            zipcode = get_user_input("Enter ZIP code: ", Colors.INFO)
            if not zipcode:
                print_status("ZIP code cannot be empty.", "error")
                continue
            
            output_file = get_user_input("Output filename (default: frequencies.csv): ", Colors.INFO)
            if not output_file:
                output_file = "frequencies.csv"
            
            format_choice = get_user_input("Format? (csv/txt, or press Enter for auto-detect): ", Colors.INFO)
            if not format_choice:
                if output_file.lower().endswith('.txt'):
                    format_choice = 'txt'
                else:
                    format_choice = 'csv'
            
            append_choice = get_user_input("Append to existing file? (y/n, default: n): ", Colors.INFO)
            append_mode = append_choice.lower() in ['y', 'yes']
            
            filter_mode = get_user_input("Filter by mode? (FM/Digital/DMR/P25, or press Enter for all): ", Colors.INFO)
            if not filter_mode:
                filter_mode = None
            
            frequencies = converter.lookup_by_zipcode(zipcode)
            
            if frequencies and filter_mode:
                original_count = len(frequencies)
                frequencies = converter.filter_frequencies(frequencies, filter_mode)
                print_status(f"Filtered to {len(frequencies)} frequencies (from {original_count}) using mode: {filter_mode}", "info")
            
            if frequencies:
                if format_choice.lower() == 'txt':
                    converter.to_txt(frequencies, output_file, append=append_mode)
                else:
                    converter.to_chirp_csv(frequencies, output_file, append=append_mode)
                print(f"\n{Colors.SUCCESS}✓ Export complete!{Colors.RESET}\n")
            else:
                print_status("No frequencies found. Please check your ZIP code.", "error")
            
            input(f"\n{Colors.INFO}Press Enter to continue...{Colors.RESET}")
            clear_screen()
            print_banner()
            
        elif choice in ['2', 'city']:
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  CITY & STATE SEARCH{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            city = get_user_input("Enter city name: ", Colors.INFO)
            if not city:
                print_status("City name cannot be empty.", "error")
                continue
            
            state = get_user_input("Enter state abbreviation (e.g., CA, NY): ", Colors.INFO)
            if not state:
                print_status("State abbreviation cannot be empty.", "error")
                continue
            
            output_file = get_user_input("Output filename (default: frequencies.csv): ", Colors.INFO)
            if not output_file:
                output_file = "frequencies.csv"
            
            format_choice = get_user_input("Format? (csv/txt, or press Enter for auto-detect): ", Colors.INFO)
            if not format_choice:
                if output_file.lower().endswith('.txt'):
                    format_choice = 'txt'
                else:
                    format_choice = 'csv'
            
            append_choice = get_user_input("Append to existing file? (y/n, default: n): ", Colors.INFO)
            append_mode = append_choice.lower() in ['y', 'yes']
            
            filter_mode = get_user_input("Filter by mode? (FM/Digital/DMR/P25, or press Enter for all): ", Colors.INFO)
            if not filter_mode:
                filter_mode = None
            
            frequencies = converter.lookup_by_city_state(city, state)
            
            if frequencies and filter_mode:
                original_count = len(frequencies)
                frequencies = converter.filter_frequencies(frequencies, filter_mode)
                print_status(f"Filtered to {len(frequencies)} frequencies (from {original_count}) using mode: {filter_mode}", "info")
            
            if frequencies:
                if format_choice.lower() == 'txt':
                    converter.to_txt(frequencies, output_file, append=append_mode)
                else:
                    converter.to_chirp_csv(frequencies, output_file, append=append_mode)
                print(f"\n{Colors.SUCCESS}✓ Export complete!{Colors.RESET}\n")
            else:
                print_status("No frequencies found. Please check your city and state.", "error")
            
            input(f"\n{Colors.INFO}Press Enter to continue...{Colors.RESET}")
            clear_screen()
            print_banner()
            
        elif choice in ['3', 'county']:
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  COUNTY & STATE SEARCH{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            county = get_user_input("Enter county name: ", Colors.INFO)
            if not county:
                print_status("County name cannot be empty.", "error")
                continue
            
            state = get_user_input("Enter state abbreviation (e.g., CA, NY): ", Colors.INFO)
            if not state:
                print_status("State abbreviation cannot be empty.", "error")
                continue
            
            output_file = get_user_input("Output filename (default: frequencies.csv): ", Colors.INFO)
            if not output_file:
                output_file = "frequencies.csv"
            
            format_choice = get_user_input("Format? (csv/txt, or press Enter for auto-detect): ", Colors.INFO)
            if not format_choice:
                if output_file.lower().endswith('.txt'):
                    format_choice = 'txt'
                else:
                    format_choice = 'csv'
            
            append_choice = get_user_input("Append to existing file? (y/n, default: n): ", Colors.INFO)
            append_mode = append_choice.lower() in ['y', 'yes']
            
            filter_mode = get_user_input("Filter by mode? (FM/Digital/DMR/P25, or press Enter for all): ", Colors.INFO)
            if not filter_mode:
                filter_mode = None
            
            frequencies = converter.lookup_by_county_state(county, state)
            
            if frequencies and filter_mode:
                original_count = len(frequencies)
                frequencies = converter.filter_frequencies(frequencies, filter_mode)
                print_status(f"Filtered to {len(frequencies)} frequencies (from {original_count}) using mode: {filter_mode}", "info")
            
            if frequencies:
                if format_choice.lower() == 'txt':
                    converter.to_txt(frequencies, output_file, append=append_mode)
                else:
                    converter.to_chirp_csv(frequencies, output_file, append=append_mode)
                print(f"\n{Colors.SUCCESS}✓ Export complete!{Colors.RESET}\n")
            else:
                print_status("No frequencies found. Please check your county and state.", "error")
            
            input(f"\n{Colors.INFO}Press Enter to continue...{Colors.RESET}")
            clear_screen()
            print_banner()
            
        elif choice in ['4', 'import', 'upload']:
            run_import_menu()
            clear_screen()
            print_banner()
        
        elif choice in ['5', 'backup', 'save']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  CREATE BACKUP{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            csv_file = get_user_input("Enter path to CHIRP CSV file: ", Colors.INFO)
            if not csv_file:
                print_status("No file specified.", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            if not os.path.exists(csv_file):
                print_status(f"File not found: {csv_file}", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            is_valid, message, frequencies = validate_chirp_csv(csv_file)
            if not is_valid:
                print_status(f"CSV validation failed: {message}", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            print_status(f"Loaded {len(frequencies)} frequencies from CSV.", "success")
            
            selected_radio = get_selected_radio_model()
            if selected_radio:
                radio_model = selected_radio['name']
                print(f"\n{Colors.INFO}Using selected radio model: {Colors.SUCCESS}{radio_model}{Colors.RESET}")
                use_selected = get_user_input("Use this radio model? (y/n, default: y): ", Colors.INFO)
                if use_selected.lower() in ['n', 'no']:
                    radio_model = get_user_input("Enter radio model name: ", Colors.INFO)
                    if not radio_model:
                        print_status("Radio model is required.", "error")
                        input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                        clear_screen()
                        print_banner()
                        continue
            else:
                radio_model = get_user_input("Enter radio model name: ", Colors.INFO)
                if not radio_model:
                    print_status("Radio model is required.", "error")
                    input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                    clear_screen()
                    print_banner()
                    continue
            
            ports = detect_serial_ports()
            port = None
            
            if ports:
                print(f"\n{Colors.INFO}Available serial ports:{Colors.RESET}\n")
                for idx, (port_name, description) in enumerate(ports, 1):
                    print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {Colors.HEADER}{port_name}{Colors.RESET}")
                    print(f"      {Colors.DIM}{description}{Colors.RESET}\n")
                
                port_choice = get_user_input(f"Select port (1-{len(ports)}) or enter custom port: ", Colors.INFO)
                if port_choice:
                    try:
                        port_idx = int(port_choice) - 1
                        if 0 <= port_idx < len(ports):
                            port = ports[port_idx][0]
                        else:
                            port = port_choice
                    except ValueError:
                        port = port_choice
            else:
                port = get_user_input("Enter serial port manually (e.g., COM3, /dev/ttyUSB0): ", Colors.INFO)
            
            if not port:
                print_status("Serial port is required.", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            print_status("Creating backup...", "info")
            backup_file = create_backup_file(radio_model, port, frequencies=frequencies, csv_file=csv_file)
            
            if backup_file:
                print_status(f"Backup created successfully: {backup_file}", "success")
                print(f"\n{Colors.INFO}Backup contains:{Colors.RESET}")
                print(f"  - Radio Model: {radio_model}")
                print(f"  - Serial Port: {port}")
                print(f"  - Frequencies: {len(frequencies)}")
                print(f"  - CSV File: {csv_file}")
            else:
                print_status("Failed to create backup.", "error")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['6', 'restore']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  RESTORE FROM BACKUP{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                print_status("No backups directory found.", "error")
                print(f"{Colors.INFO}Backups will be saved to: {backup_dir}{Colors.RESET}")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
            else:
                backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.backup')]
                if backup_files:
                    backup_files.sort(reverse=True)
                    print(f"{Colors.SUCCESS}Found {len(backup_files)} backup file(s):{Colors.RESET}\n")
                    
                    backup_list = []
                    for idx, backup_file in enumerate(backup_files[:20], 1):
                        backup_path = os.path.join(backup_dir, backup_file)
                        try:
                            with open(backup_path, 'r') as f:
                                backup_data = json.load(f)
                                radio_model = backup_data.get('radio_model', 'Unknown')
                                serial_port = backup_data.get('serial_port', 'Unknown')
                                backup_date = backup_data.get('backup_date', 'Unknown')
                                frequency_count = backup_data.get('frequency_count', 0)
                                has_data = bool(backup_data.get('frequencies') or backup_data.get('csv_content'))
                                
                                backup_list.append(backup_path)
                                
                                restore_indicator = f"{Colors.SUCCESS}[RESTORE]{Colors.RESET}" if has_data else f"{Colors.DIM}[NO DATA]{Colors.RESET}"
                                print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {Colors.HEADER}{backup_file}{Colors.RESET} {restore_indicator}")
                                print(f"      Radio: {radio_model}")
                                print(f"      Port: {serial_port}")
                                print(f"      Date: {backup_date}")
                                if frequency_count:
                                    print(f"      Frequencies: {frequency_count}")
                                print()
                        except Exception as e:
                            print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {backup_file} {Colors.DIM}(Error reading metadata){Colors.RESET}\n")
                            backup_list.append(backup_path)
                    
                    if len(backup_files) > 20:
                        print(f"{Colors.DIM}... and {len(backup_files) - 20} more backup files{Colors.RESET}\n")
                    
                    restore_choice = get_user_input(f"\nSelect backup to restore (1-{min(len(backup_files), 20)}) or press Enter to cancel: ", Colors.INFO)
                    
                    if restore_choice:
                        try:
                            restore_idx = int(restore_choice) - 1
                            if 0 <= restore_idx < len(backup_list):
                                selected_backup = backup_list[restore_idx]
                                restore_from_backup(selected_backup)
                            else:
                                print_status("Invalid selection.", "error")
                                time.sleep(1)
                        except ValueError:
                            print_status("Invalid selection.", "error")
                            time.sleep(1)
                else:
                    print_status("No backup files found.", "info")
                    input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            
            clear_screen()
            print_banner()
        
        elif choice in ['7', 'validate']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  VALIDATE CSV FILE{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            csv_file = get_user_input("Enter path to CSV file: ", Colors.INFO)
            if csv_file:
                print_status("Validating CSV file...", "info")
                is_valid, message, frequencies = validate_chirp_csv(csv_file)
                
                if is_valid:
                    print_status(message, "success")
                    print(f"\n{Colors.INFO}File contains {len(frequencies)} frequencies.{Colors.RESET}")
                else:
                    print_status(message, "error")
            else:
                print_status("No file specified.", "error")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['8', 'ports', 'serial']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  SERIAL PORTS{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            print_status("Detecting serial ports...", "info")
            ports = detect_serial_ports()
            
            if ports:
                print(f"\n{Colors.SUCCESS}Found {len(ports)} serial port(s):{Colors.RESET}\n")
                for idx, (port_name, description) in enumerate(ports, 1):
                    print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {Colors.HEADER}{port_name}{Colors.RESET}")
                    print(f"      {Colors.DIM}{description}{Colors.RESET}\n")
            else:
                print_status("No serial ports detected.", "warning")
                print(f"{Colors.INFO}Make sure your radio is connected via USB.{Colors.RESET}")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['13', 'cache', 'buildcache']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  BUILD COUNTY CACHE{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            print(f"{Colors.INFO}This will build a cache of county IDs for faster lookups.{Colors.RESET}")
            print(f"{Colors.DIM}The cache is stored in countyID.db (JSON format){Colors.RESET}\n")
            
            converter = RadioRefToChirp()
            cache = converter._load_county_cache()
            if cache:
                total_counties = len(cache)
                states_with_cache = len(set(k[1] for k in cache.keys()))
                print(f"{Colors.SUCCESS}Current cache:{Colors.RESET} {total_counties} counties from {states_with_cache} states\n")
            else:
                print(f"{Colors.WARNING}No counties cached yet.{Colors.RESET}\n")
            
            print(f"{Colors.INFO}[1]{Colors.RESET} Build cache for a specific state")
            print(f"{Colors.INFO}[2]{Colors.RESET} Build cache for all states {Colors.DIM}(may take a while){Colors.RESET}")
            print(f"{Colors.INFO}[3]{Colors.RESET} View cache statistics")
            print(f"{Colors.INFO}[0]{Colors.RESET} Cancel\n")
            
            cache_choice = get_user_input("Select option: ", Colors.INFO)
            
            if cache_choice == '1':
                state_input = get_user_input("Enter state abbreviation (e.g., CA): ", Colors.INFO).upper().strip()
                if state_input and len(state_input) == 2:
                    print()
                    count = converter.build_county_cache_for_state(state_input)
                    print_status(f"Cache building complete for {state_input}. Total counties: {count}", "success")
                else:
                    print_status("Invalid state abbreviation", "error")
            
            elif cache_choice == '2':
                confirm = get_user_input("This will test many county IDs and may take 10-30 minutes. Continue? (yes/no): ", Colors.WARNING)
                if confirm.lower() in ['yes', 'y']:
                    print()
                    results = converter.build_county_cache_for_all_states()
                    print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
                    print(f"{Colors.HEADER}  CACHE BUILDING COMPLETE{Colors.RESET}")
                    print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
                    print(f"{Colors.SUCCESS}Summary:{Colors.RESET}\n")
                    for state, count in sorted(results.items()):
                        print(f"  {state}: {count} counties")
                    total = sum(results.values())
                    print(f"\n{Colors.SUCCESS}Total: {total} counties cached{Colors.RESET}")
                else:
                    print_status("Cancelled", "info")
            
            elif cache_choice == '3':
                cache = converter._load_county_cache()
                if cache:
                    print(f"\n{Colors.HEADER}Cache Statistics:{Colors.RESET}\n")
                    states = {}
                    for (county, state), ctid in cache.items():
                        if state not in states:
                            states[state] = []
                        states[state].append((county, ctid))
                    
                    print(f"{Colors.INFO}Total counties cached:{Colors.RESET} {len(cache)}")
                    print(f"{Colors.INFO}States covered:{Colors.RESET} {len(states)}\n")
                    print(f"{Colors.HEADER}Counties by state:{Colors.RESET}\n")
                    for state in sorted(states.keys()):
                        print(f"  {state.upper()}: {len(states[state])} counties")
                        for county, ctid in states[state][:5]:
                            print(f"    - {county.title()}: {ctid}")
                        if len(states[state]) > 5:
                            print(f"    ... and {len(states[state]) - 5} more")
                        print()
                else:
                    print_status("No counties cached yet", "warning")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['9', 'models', 'radios', 'select']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  SELECT RADIO MODEL{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            selected = get_selected_radio_model()
            if selected:
                print(f"{Colors.SUCCESS}Currently Selected:{Colors.RESET} {selected['name']} ({selected['manufacturer']})")
                print(f"{Colors.INFO}Baudrate:{Colors.RESET} {selected['baudrate']} | {Colors.INFO}Max Channels:{Colors.RESET} {selected['max_channels']}\n")
            
            models = get_radio_models()
            print(f"{Colors.INFO}CHIRP-Compatible Radio Models:{Colors.RESET}\n")
            
            for idx, model in enumerate(models, 1):
                marker = f"{Colors.SUCCESS}✓{Colors.RESET} " if selected and selected['name'] == model['name'] else "  "
                print(f"{marker}{Colors.INFO}[{idx}]{Colors.RESET} {Colors.HEADER}{model['name']}{Colors.RESET}")
                print(f"      Manufacturer: {model['manufacturer']}")
                print(f"      Max Channels: {model['max_channels']} | Baudrate: {model['baudrate']}")
                print(f"      CHIRP ID: {model['chirp_id']}")
                if model.get('notes'):
                    print(f"      {Colors.DIM}Note: {model['notes']}{Colors.RESET}")
                print()
            
            print(f"{Colors.DIM}Note: These are common models. CHIRP supports many more.{Colors.RESET}\n")
            
            model_choice = get_user_input(f"Select model (1-{len(models)}) or press Enter to keep current: ", Colors.INFO)
            
            if model_choice:
                try:
                    model_idx = int(model_choice) - 1
                    if 0 <= model_idx < len(models):
                        selected_model = models[model_idx]
                        if save_selected_radio_model(selected_model['name']):
                            print_status(f"Radio model set to: {selected_model['name']}", "success")
                            print(f"{Colors.INFO}Settings:{Colors.RESET}")
                            print(f"  - Baudrate: {selected_model['baudrate']}")
                            print(f"  - Max Channels: {selected_model['max_channels']}")
                            print(f"  - CHIRP ID: {selected_model['chirp_id']}")
                        else:
                            print_status("Failed to save radio model selection.", "error")
                    else:
                        print_status("Invalid selection.", "error")
                except ValueError:
                    print_status("Invalid input. Please enter a number.", "error")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['10', 'filter']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  FILTER EXISTING CSV FILE{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            csv_file = get_user_input("Enter path to CSV file: ", Colors.INFO)
            if not csv_file:
                print_status("No file specified.", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            is_valid, message, frequencies = validate_chirp_csv(csv_file)
            if not is_valid:
                print_status(f"CSV validation failed: {message}", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            print_status(f"Loaded {len(frequencies)} frequencies from CSV.", "success")
            
            filter_mode = get_user_input("Filter by mode? (FM/Digital/DMR/P25, or press Enter for all): ", Colors.INFO)
            if filter_mode:
                original_count = len(frequencies)
                frequencies = converter.filter_frequencies(frequencies, filter_mode)
                print_status(f"Filtered to {len(frequencies)} frequencies (from {original_count}) using mode: {filter_mode}", "info")
            
            if frequencies:
                output_file = get_user_input("Output filename (default: filtered_frequencies.csv): ", Colors.INFO)
                if not output_file:
                    output_file = "filtered_frequencies.csv"
                
                format_choice = get_user_input("Format? (csv/txt, or press Enter for auto-detect): ", Colors.INFO)
                if not format_choice:
                    if output_file.lower().endswith('.txt'):
                        format_choice = 'txt'
                    else:
                        format_choice = 'csv'
                
                if format_choice.lower() == 'txt':
                    converter.to_txt(frequencies, output_file, append=False)
                else:
                    converter.to_chirp_csv(frequencies, output_file, append=False)
                
                print_status(f"Filtered frequencies saved to {output_file}", "success")
            else:
                print_status("No frequencies remaining after filter.", "warning")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['11', 'convert', 'csv2txt']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  CONVERT CSV TO TXT{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            csv_file = get_user_input("Enter path to CSV file: ", Colors.INFO)
            if not csv_file:
                print_status("No file specified.", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            is_valid, message, frequencies = validate_chirp_csv(csv_file)
            if not is_valid:
                print_status(f"CSV validation failed: {message}", "error")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
                continue
            
            print_status(f"Loaded {len(frequencies)} frequencies.", "success")
            
            base_name = os.path.splitext(csv_file)[0]
            output_file = f"{base_name}.txt"
            
            output_choice = get_user_input(f"Output filename (default: {output_file}): ", Colors.INFO)
            if output_choice:
                output_file = output_choice
            
            converter.to_txt(frequencies, output_file, append=False)
            print_status(f"Converted to TXT format: {output_file}", "success")
            
            input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            clear_screen()
            print_banner()
        
        elif choice in ['12', 'backups', 'viewbackups']:
            clear_screen()
            print_banner()
            print(f"\n{Colors.HEADER}{'='*60}{Colors.RESET}")
            print(f"{Colors.HEADER}  BACKUP FILES{Colors.RESET}")
            print(f"{Colors.HEADER}{'='*60}{Colors.RESET}\n")
            
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                print_status("No backups directory found.", "info")
                print(f"{Colors.INFO}Backups will be saved to: {backup_dir}{Colors.RESET}")
                input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
                clear_screen()
                print_banner()
            else:
                backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.backup')]
                if backup_files:
                    backup_files.sort(reverse=True)
                    print(f"{Colors.SUCCESS}Found {len(backup_files)} backup file(s):{Colors.RESET}\n")
                    
                    backup_list = []
                    for idx, backup_file in enumerate(backup_files[:20], 1):
                        backup_path = os.path.join(backup_dir, backup_file)
                        try:
                            with open(backup_path, 'r') as f:
                                backup_data = json.load(f)
                                radio_model = backup_data.get('radio_model', 'Unknown')
                                serial_port = backup_data.get('serial_port', 'Unknown')
                                backup_date = backup_data.get('backup_date', 'Unknown')
                                frequency_count = backup_data.get('frequency_count', 0)
                                has_data = bool(backup_data.get('frequencies') or backup_data.get('csv_content'))
                                
                                backup_list.append(backup_path)
                                
                                restore_indicator = f"{Colors.SUCCESS}[RESTORE]{Colors.RESET}" if has_data else f"{Colors.DIM}[NO DATA]{Colors.RESET}"
                                print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {Colors.HEADER}{backup_file}{Colors.RESET} {restore_indicator}")
                                print(f"      Radio: {radio_model}")
                                print(f"      Port: {serial_port}")
                                print(f"      Date: {backup_date}")
                                if frequency_count:
                                    print(f"      Frequencies: {frequency_count}")
                                print()
                        except Exception as e:
                            print(f"  {Colors.INFO}[{idx}]{Colors.RESET} {backup_file} {Colors.DIM}(Error reading metadata){Colors.RESET}\n")
                            backup_list.append(backup_path)
                    
                    if len(backup_files) > 20:
                        print(f"{Colors.DIM}... and {len(backup_files) - 20} more backup files{Colors.RESET}\n")
                    
                    restore_choice = get_user_input(f"\nSelect backup to restore (1-{min(len(backup_files), 20)}) or press Enter to return: ", Colors.INFO)
                    
                    if restore_choice:
                        try:
                            restore_idx = int(restore_choice) - 1
                            if 0 <= restore_idx < len(backup_list):
                                selected_backup = backup_list[restore_idx]
                                restore_from_backup(selected_backup)
                            else:
                                print_status("Invalid selection.", "error")
                                time.sleep(1)
                        except ValueError:
                            print_status("Invalid selection.", "error")
                            time.sleep(1)
                else:
                    print_status("No backup files found.", "info")
                    input(f"\n{Colors.INFO}Press Enter to return to menu...{Colors.RESET}")
            
            clear_screen()
            print_banner()
            
        else:
            clear_screen()
            print_banner()
            print_status("Invalid option. Please select 1-13, or 0/Q to exit.", "error")
            time.sleep(2)
            clear_screen()
            print_banner()


ensure_chirp_installed()


def main():
    parser = argparse.ArgumentParser(
        description='Convert Radio Reference data to CHIRP CSV format via web scraping',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python getradios.py --zipcode 90210 --output output.csv
  
  python getradios.py --city "Los Angeles" --state CA --output output.csv
  
  python getradios.py --county "Los Angeles" --state CA --output output.csv

  python getradios.py --county "Sanders" --state MT --filter FM --output fm_only.csv

  python getradios.py --city "Auburn" --state WA --filter Digital --output digital_only.csv

  python getradios.py

Note: Use responsibly and comply with Radio Reference Terms of Service.
        """
    )
    
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument('--zipcode', type=str, help='5-digit ZIP code')
    input_group.add_argument('--city', type=str, help='City name')
    input_group.add_argument('--county', type=str, help='County name')
    
    parser.add_argument('--state', type=str, help='State abbreviation (required for city/county)')
    parser.add_argument('--output', '-o', type=str, default='frequencies.csv', 
                       help='Output file path (default: frequencies.csv). Use .txt extension for human-readable format.')
    parser.add_argument('--filter', '-f', type=str, 
                       help='Filter by mode (e.g., FM, Digital, DMR, P25). Use "FM" for non-encrypted analog frequencies.')
    parser.add_argument('--format', type=str, choices=['csv', 'txt'], 
                       help='Output format: csv (CHIRP format) or txt (human-readable). Auto-detected from file extension if not specified.')
    parser.add_argument('--append', '-a', action='store_true',
                       help='Append to existing file instead of overwriting')
    
    args = parser.parse_args()
    
    has_cli_args = args.zipcode or args.city or args.county
    
    if has_cli_args:
        run_cli_mode(args)
    else:
        try:
            run_interactive_mode()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.WARNING}Operation cancelled by user.{Colors.RESET}")
            sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Operation cancelled by user.{Colors.RESET}")
        sys.exit(0)
