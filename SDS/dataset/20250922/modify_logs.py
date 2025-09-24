
import pandas as pd
import glob
import os

# Define the base path to search for the CSV files
base_path = 'C:\\Users\\kuy75\\Documents\\GitHub\\TANGO2\\SDS\\dataset'
search_pattern = os.path.join(base_path, '**\\ShipDataLog.csv')

# 1. Find all ShipDataLog.csv files using the constructed pattern
file_paths = glob.glob(search_pattern, recursive=True)

print(f"Found {len(file_paths)} files to process.")

# 2. Process each file
for file_path in file_paths:
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)

        # Check if 'Timestamp' column exists
        if 'Timestamp' not in df.columns:
            print(f"Skipping {file_path}: 'Timestamp' column not found.")
            continue

        # Convert 'Timestamp' column to datetime objects, coercing errors
        df['Timestamp_dt'] = pd.to_datetime(df['Timestamp'], errors='coerce')

        # Create the 'folder' column from the minute part
        # Using .minute will give values from 0-59. The user example implies 1-based indexing from the minute.
        # Example: 3:01 -> 1. So, minute value is used directly.
        df['folder'] = 'frame_' + df['Timestamp_dt'].dt.minute.astype(str)

        # Get a list of original columns
        cols = df.columns.tolist()

        # Create the new column order
        # Place 'folder' at the beginning
        new_cols = ['folder'] + [col for col in cols if col not in ['folder', 'Timestamp_dt']]

        # Reorder the dataframe and drop the temporary datetime column
        df_reordered = df[new_cols]

        # Save the modified dataframe back to the original file
        df_reordered.to_csv(file_path, index=False)

        print(f"Processed and updated: {file_path}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print("All files processed.")
