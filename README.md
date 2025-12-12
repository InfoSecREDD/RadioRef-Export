# Radio Ref Exporter

A powerful Python script that pulls frequency data from Radio Reference via web scraping and converts it to CHIRP-compatible CSV format for import into handheld radios. Features an interactive menu-driven interface with colorful ASCII art and comprehensive radio management capabilities.

**Created by InfoSecREDD**

## Features

### Core Functionality
- **Query by ZIP Code**: Automatically resolves location and finds frequencies
- **Query by City & State**: Search frequencies for specific cities
- **Query by County & State**: Get county-wide frequency listings
- **Web Scraping Based**: No API key required - uses Playwright for JavaScript-rendered content
- **CHIRP-Compatible Output**: Generates CSV files ready for CHIRP import
- **Human-Readable TXT Export**: Option to export as formatted text files
- **Frequency Filtering**: Filter by mode (FM, Digital, DMR, P25, etc.)
- **Append Mode**: Add frequencies to existing CSV or TXT files

### Radio Management
- **Import CSV to Handheld**: Full workflow for uploading frequencies to radios
- **Create Backup**: Standalone backup creation from CSV files
- **Restore from Backup**: Restore radio configurations from backup files
- **View Backup Files**: Browse and manage all backup files
- **Select Radio Model**: Choose from CHIRP-compatible radio models with proper settings
- **Serial Port Detection**: Automatic USB serial port detection (filters out Bluetooth/debug ports)
- **Connection Status**: Real-time display of radio connection status

### Advanced Features
- **County Cache System**: Build and maintain a cache of county IDs for faster lookups
- **CSV Validation**: Validate CSV files against CHIRP format requirements
- **Filter Existing CSV**: Apply mode filters to existing CSV files
- **Convert CSV to TXT**: Convert CHIRP CSV files to human-readable text format
- **View Serial Ports**: List all available USB serial ports

## Installation

**No manual installation required!** The script automatically checks and installs missing dependencies on first run.

The script will automatically detect and use the correct `pip` or `pip3` command and install:
- `requests` - HTTP library for web scraping
- `beautifulsoup4` - HTML parsing
- `colorama` - Colored terminal output
- `uszipcode` - ZIP code lookup (with automatic fallback)
- `lxml` - HTML parser backend
- `python-Levenshtein` - Fast string matching (speeds up fuzzywuzzy)
- `pyserial` - Serial port detection
- `playwright` - JavaScript rendering for dynamic content

## Usage

### Interactive Menu Mode (Default)

Simply run the script without any arguments to use the interactive menu:

```bash
python getradios.py
# or
python3 getradios.py
```

The script displays a colorful ASCII art banner and interactive menu with the following options:

1. **Search by ZIP Code** - Enter a 5-digit ZIP code
2. **Search by City & State** - Enter city name and state abbreviation
3. **Search by County & State** - Enter county name and state abbreviation
4. **Import CSV to Handheld** - Upload frequencies to your radio
5. **Create Backup** - Create a backup from a CSV file
6. **Restore from Backup** - Restore radio configuration from backup
7. **Validate CSV File** - Validate CSV files against CHIRP format
8. **View Serial Ports** - List available USB serial ports
9. **Select Radio Model** - Choose radio model with proper CHIRP settings
10. **Filter Existing CSV** - Apply filters to existing CSV files
11. **Convert CSV to TXT** - Convert CSV to human-readable text
12. **View Backup Files** - Browse and manage backup files
13. **Build County Cache** - Build cache of county IDs for faster lookups

### Command-Line Mode

You can also use command-line arguments for automation or scripting:

```bash
# Using ZIP code
python getradios.py --zipcode 90210 --output frequencies.csv

# Using city and state
python getradios.py --city "Los Angeles" --state CA --output frequencies.csv

# Using county and state
python getradios.py --county "Los Angeles" --state CA --output frequencies.csv

# With filtering (FM frequencies only)
python getradios.py --zipcode 90210 --filter FM --output fm_frequencies.csv

# Export as TXT format
python getradios.py --zipcode 90210 --format txt --output frequencies.txt

# Append to existing file
python getradios.py --zipcode 90210 --output frequencies.csv --append
```

### Command-Line Options

- `--zipcode`: 5-digit ZIP code
- `--city`: City name
- `--county`: County name
- `--state`: State abbreviation (required for city/county queries)
- `--output` / `-o`: Output file path (default: frequencies.csv)
- `--format`: Output format - `csv` (default) or `txt`
- `--filter` / `-f`: Filter by mode (FM, Digital, DMR, P25, etc.)
- `--append`: Append to existing file instead of overwriting

## Menu Shortcuts

The interactive menu supports text shortcuts for faster navigation:

- `zip` or `zipcode` - Search by ZIP Code
- `city` - Search by City & State
- `county` - Search by County & State
- `import` or `upload` - Import CSV to Handheld
- `backup` or `save` - Create Backup
- `restore` - Restore from Backup
- `validate` - Validate CSV File
- `ports` or `serial` - View Serial Ports
- `models`, `radios`, or `select` - Select Radio Model
- `filter` - Filter Existing CSV
- `convert` or `csv2txt` - Convert CSV to TXT
- `backups` or `backup` - View Backup Files
- `cache` or `buildcache` - Build County Cache
- `0`, `Q`, `quit`, or `exit` - Exit the program

## CHIRP Import Workflow

### Method 1: Using the Script's Import Feature

1. Export frequencies using this script (Search by ZIP/City/County)
2. Select option **4: Import CSV to Handheld**
3. Select your CSV file
4. Choose serial port and radio model
5. Create backup (recommended)
6. Follow the instructions to complete upload via CHIRP

### Method 2: Manual CHIRP Import

1. Export frequencies using this script
2. Open CHIRP software
3. File → Import from CSV
4. Select your exported CSV file
5. Review and upload to your radio

## Backup and Restore

### Creating Backups

**Option 5: Create Backup** allows you to create backups from CSV files:
- Validates the CSV file
- Saves frequency data and CSV content
- Stores radio model and port information
- Timestamped backup files

**Automatic Backups**: When importing CSV to handheld (Option 4), you'll be prompted to create a backup before uploading.

### Restoring from Backups

**Option 6: Restore from Backup** allows you to:
- Browse all available backup files
- Select a backup to restore
- Extract CSV content from backup
- Restore to your handheld radio

Backup files are stored in the `backups/` directory with the format:
`{RadioModel}_{Port}_{Timestamp}.backup`

## County Cache System

The script includes a sophisticated county caching system for faster lookups:

- **Automatic Caching**: County IDs are cached as they're discovered
- **Build Cache for All States**: Option 13 allows building a complete cache
- **State-Sectioned Storage**: Cache stored in `countyID.db` (JSON format)
- **Rate Limiting**: Built-in delays to respect Radio Reference's servers
- **API Verification**: Uses external APIs to verify county-state relationships

Cache files are stored in `countyID.db` and organized by state for efficient lookups.

## Radio Model Support

The script supports a wide range of CHIRP-compatible radio models with proper settings:
- Automatic detection of baudrate, max channels, and CHIRP ID
- Radio model selection persists across sessions
- Custom radio models can be entered manually
- Connection status displayed in main menu

## File Formats

### CHIRP CSV Format
Standard CHIRP-compatible CSV with all required columns:
- Location, Name, Frequency, Duplex, Offset, Tone, rToneFreq, cToneFreq, DtcsCode, DtcsPolarity, Mode, TStep, Skip, Comment, URCALL, RPT1CALL, RPT2CALL, DVCODE

### TXT Format
Human-readable text format with:
- Frequency listings
- Mode information
- Alpha tags and descriptions
- Formatted for easy reading

## Notes

- **Important**: Use responsibly and comply with Radio Reference Terms of Service
- The script includes rate limiting and respectful scraping practices
- Radio Reference's page structure may change - the script may need updates
- Some frequency details (tones, offsets) may need manual adjustment after import
- USB serial ports only - Bluetooth and debug ports are automatically filtered
- County cache building may take time - be patient for all-state cache builds

## Troubleshooting

### Common Issues

- **"Could not find location"**: Verify your ZIP code, city, or county name
- **"No frequencies found"**: Radio Reference's page structure may have changed, or the location may not have frequencies listed
- **"Could not find county ID"**: Try using city/state instead, or build the county cache for that state
- **"uszipcode lookup failed"**: The script automatically falls back to web API - this is normal
- **Import errors in CHIRP**: Verify the CSV format matches CHIRP's expected structure
- **No serial ports detected**: Make sure your radio is connected via USB (not Bluetooth)
- **"Radio Not Connected"**: Connect your radio via USB cable and select the port

### County Cache Issues

- **Missing counties**: Use Option 13 to build cache for specific states
- **Cache not updating**: Delete `countyID.db` and rebuild the cache
- **Slow cache building**: This is normal - rate limiting prevents server overload

## Project Structure

```
radiorefexport/
├── getradios.py          # Main script
├── countyID.db          # County ID cache (JSON format)
├── backups/              # Backup files directory
│   └── *.backup         # Backup files
├── .radio_config.json   # Radio model and port configuration
└── README.md            # This file
```

## Credits

**Created by InfoSecREDD**

This project uses web scraping to extract frequency data from Radio Reference. All data is sourced from Radio Reference's public database.

### Technologies Used

- **Playwright**: JavaScript rendering for dynamic content extraction
- **BeautifulSoup4**: HTML parsing
- **Requests**: HTTP requests
- **Colorama**: Terminal colors
- **PySerial**: Serial port detection
- **uszipcode**: ZIP code lookup (with fallback to zippopotam.us)

### Data Sources

- **Radio Reference**: Frequency database (https://www.radioreference.com)
- **zippopotam.us**: ZIP code lookup API (fallback)
- **Nominatim (OpenStreetMap)**: Geocoding API for county verification

## License

Use responsibly and in compliance with Radio Reference's Terms of Service.

---

**Radio Frequency Harvester v1.1**  
*Scraping Radio Reference → CHIRP CSV*
