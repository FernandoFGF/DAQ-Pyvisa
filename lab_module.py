"""
Laboratory Module

This module provides utility functions for laboratory instrument operations,
file management, and data acquisition tasks.

Author: Fernando Fuentes-Guerra
Date: 2025
"""

import errno
import shutil
import os
from pathlib import Path
import zipfile
import winsound
from datetime import date
import time
from config_loader import get_config, get_output_path


# Configuration instance
config = get_config()


def get_path(measurement_type: str) -> Path:
    """
    Get the output path for a specific measurement type with today's date.
    
    Args:
        measurement_type: Type of measurement ('IV Curves', 'Spectrum', 'Waveform')
        
    Returns:
        Path object for the output directory with date subdirectory
    """
    # Map display names to config keys
    type_mapping = {
        'IV Curves': 'iv_curves',
        'Spectrum': 'spectrum',
        'Waveform': 'waveform'
    }
    
    config_key = type_mapping.get(measurement_type, measurement_type.lower().replace(' ', '_'))
    base_path = get_output_path(config_key)
    
    # Add today's date as subdirectory
    dated_path = base_path / str(date.today())
    
    return dated_path


def create_directory(path: Path) -> None:
    """
    Create a directory if it doesn't exist.
    
    Args:
        path: Path object or string path to create
    """
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise OSError(f"Failed to create directory {path}: {e}")


def create_directory_in_current(folder_name: str) -> Path:
    """
    Create a directory in the current working directory.
    
    Args:
        folder_name: Name of the folder to create
        
    Returns:
        Path object of the created folder
    """
    current_dir = Path.cwd()
    folder_path = current_dir / folder_name
    
    if folder_path.exists():
        print(f"Folder '{folder_name}' already exists in current directory.")
    else:
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            print(f"Created folder '{folder_name}' in current directory.")
        except OSError as e:
            print(f"Could not create folder '{folder_name}': {e}")
    
    return folder_path


def delete_path(filepath: Path) -> None:
    """
    Delete a file or directory if it exists.
    
    Args:
        filepath: Path to file or directory to delete
    """
    filepath = Path(filepath)
    
    if filepath.exists():
        if filepath.is_dir():
            shutil.rmtree(filepath)
        else:
            filepath.unlink()


def create_zip_archive(directory_path: Path, archive_name: str) -> None:
    """
    Create a ZIP archive containing all .txt files from a directory.
    
    Args:
        directory_path: Path to directory to archive
        archive_name: Name for the ZIP archive (without extension)
    """
    directory_path = Path(directory_path)
    zip_path = directory_path / f"{archive_name}.zip"
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in directory_path.rglob('*.txt'):
            # Add file to zip with relative path
            arcname = file_path.relative_to(directory_path)
            zip_file.write(file_path, arcname)
    
    print(f"Created ZIP archive: {zip_path}")


def beep(count: int = None, frequency_start: int = None, duration: int = None) -> None:
    """
    Play audio beeps to signal completion.
    
    Args:
        count: Number of beeps (default from config)
        frequency_start: Starting frequency in Hz (default from config)
        duration: Duration in milliseconds (default from config)
    """
    if not config.get_audio_setting('enable_beep', True):
        return
    
    count = count or config.get_audio_setting('beep_count', 3)
    frequency_start = frequency_start or config.get_audio_setting('beep_frequency_start', 650)
    duration = duration or config.get_audio_setting('beep_duration', 500)
    
    for i in range(count):
        freq = frequency_start - i * 100
        dur = duration - i * 50
        winsound.Beep(freq, dur)


def print_progress(current: int, total: int) -> None:
    """
    Print progress as percentage.
    
    Args:
        current: Current iteration number
        total: Total number of iterations
    """
    percentage = round(current / total * 100, 2)
    print(f"{percentage}%")


def write_waveform_file(file_path: Path, timestamp: str, data: list, index: int) -> None:
    """
    Write waveform data to a file.
    
    Args:
        file_path: Base path for the file (without index and extension)
        timestamp: Timestamp string to write as first line
        data: List of data values to write
        index: File index number
    """
    file_path = Path(file_path)
    full_path = file_path.parent / f"{file_path.name}_{index}.txt"
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(str(timestamp))
        f.write('\n')
        for value in data:
            f.write(f"{round(value, 5)}\n")


def current_time() -> float:
    """
    Get current time in seconds since epoch.
    
    Returns:
        Current time as float
    """
    return time.time()


def initialize_instrument(instrument_type: str):
    """
    Initialize a PyVISA instrument connection using configuration.
    
    Args:
        instrument_type: Type of instrument to initialize
                        (e.g., 'scope1', 'scope2', 'scope3', 'smu', 'arbGen', 'powerSupply')
        
    Returns:
        PyVISA resource object for the instrument
        
    Raises:
        ValueError: If instrument type is not found in configuration
        pyvisa.Error: If connection to instrument fails
    """
    try:
        resource_manager = pyvisa.ResourceManager()
        address = get_instrument_address(instrument_type)
        device = resource_manager.open_resource(address)
        
        # Set timeout if specified in config
        timeout = config.get_instrument_timeout(instrument_type)
        if timeout is not None:
            device.timeout = timeout
        
        return device
        
    except KeyError as e:
        raise ValueError(f"Instrument '{instrument_type}' not found in configuration: {e}")
    except pyvisa.Error as e:
        raise pyvisa.Error(f"Failed to connect to {instrument_type} at {address}: {e}")


def write_iv_data_file(voltage_values: list, current_values: list, file_path: Path) -> None:
    """
    Write IV curve data to a file.
    
    Args:
        voltage_values: List of voltage measurements
        current_values: List of current measurements
        file_path: Path where to save the file (without extension)
    """
    file_path = Path(file_path)
    output_file = file_path.with_suffix('.txt')
    
    indices = np.arange(len(voltage_values))
    
    with open(output_file, 'a+', encoding='utf-8') as f:
        for i in indices:
            f.write(f"{current_values[i]} {voltage_values[i]}\n")
    
    # Append a zero line as delimiter
    with open(output_file, 'a+', encoding='utf-8') as f:
        f.write('0 0\n')


def run_chronometer(start_time: float, target_minutes: float, gui_object=None) -> None:
    """
    Run a chronometer that prints elapsed time until target is reached.
    
    Args:
        start_time: Start time from time.time()
        target_minutes: Target duration in minutes
        gui_object: Optional GUI object to update (with update_idletasks method)
    """
    while round((current_time() - start_time) / 60, 2) < target_minutes:
        time.sleep(0.99)

        # Clear console
        os.system('cls' if os.name == 'nt' else 'clear')

        # Calculate and display elapsed time
        minutes, seconds = divmod(current_time() - start_time, 60)
        print(f"{int(minutes)}:{int(seconds)}")

        # Update GUI if provided
        if gui_object is not None:
            gui_object.update_idletasks()
