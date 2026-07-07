#!/usr/bin/env python3
"""
Test Single Instrument Connection

This script tests connecting to a single instrument at a time.

Author: Fernando Fuentes-Guerra
Date: 2025
"""

def test_single_instrument_connection():
    """Test connecting to a single instrument."""
    print("=" * 50)
    print("Single Instrument Connection Test")
    print("=" * 50)
    
    try:
        from gui_functions import DAQGUIFunctions
        
        gui_funcs = DAQGUIFunctions()
        
        # Test connecting to SMU
        print("\n1. Testing SMU connection...")
        smu_success = gui_funcs.connect_specific_instrument("smu")
        
        if smu_success:
            print("✅ SMU connected successfully!")
        else:
            print("❌ SMU connection failed (this is normal if not connected)")
        
        # Test connecting to Scope
        print("\n2. Testing Scope connection...")
        scope_success = gui_funcs.connect_specific_instrument("scope1")
        
        if scope_success:
            print("✅ Scope connected successfully!")
        else:
            print("❌ Scope connection failed (this is normal if not connected)")
        
        # Test connecting to all instruments
        print("\n3. Testing 'Connect All' functionality...")
        gui_funcs.connect_all_instruments()
        
        # Cleanup
        print("\n4. Cleaning up...")
        gui_funcs.cleanup()
        print("✅ Cleanup completed")
        
        print("\n" + "=" * 50)
        print("Test completed!")
        print("=" * 50)
        
        if smu_success or scope_success:
            print("✅ At least one instrument connected successfully!")
        else:
            print("ℹ️  No instruments connected - this is normal if:")
            print("   • Instruments are not powered on")
            print("   • Network connections are not established")
            print("   • IP addresses need to be updated in config.yaml")
            print("   • You're working with only one instrument at a time")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    test_single_instrument_connection()
