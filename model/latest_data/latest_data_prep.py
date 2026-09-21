import os
import pandas as pd

def preprocess_logs(input_dir, output_dir, limit_users=None):
    """
    Reads logon, device, file, and http files from input_dir,
    renames columns (timestamp -> date, user_id -> user, event_id -> id),
    optionally filters by a list of users, and saves to output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    files_to_process = {
        'logon.csv': ['event_id', 'timestamp', 'user_id', 'pc', 'activity', 'auth_result', 'site'],
        'device.csv': ['event_id', 'timestamp', 'user_id', 'pc', 'activity', 'device_id', 'file_size_mb'],
        'file.csv': ['event_id', 'timestamp', 'user_id', 'pc', 'activity', 'filename', 'file_extension', 'file_path', 'destination', 'file_size_mb'],
        'http.csv': ['event_id', 'timestamp', 'user_id', 'pc', 'url', 'domain', 'activity', 'content_type', 'bytes_transferred']
    }
    
    rename_map = {
        'timestamp': 'date',
        'user_id': 'user',
        'event_id': 'id'
    }
    
    print(f"Preprocessing raw logs from '{input_dir}' to '{output_dir}'...")
    if limit_users:
        print(f"Filtering to subset of {len(limit_users)} users: {limit_users[:5]}...")

    for filename, expected_cols in files_to_process.items():
        src_path = os.path.join(input_dir, filename)
        dst_path = os.path.join(output_dir, filename)
        
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Required input log file '{src_path}' not found!")
            
        print(f"Processing '{filename}'...")
        
        # Load the CSV
        df = pd.read_csv(src_path)
        
        # Verify columns exist before renaming
        for col in ['timestamp', 'user_id', 'event_id']:
            if col not in df.columns:
                raise KeyError(f"Expected column '{col}' not found in {filename}!")
                
        # Filter by users if limited
        if limit_users is not None:
            df = df[df['user_id'].isin(limit_users)].copy()
            
        # Rename columns
        df = df.rename(columns=rename_map)
        
        # Save to destination
        df.to_csv(dst_path, index=False)
        print(f"Saved processed '{filename}' to '{dst_path}' (Shape: {df.shape})")

if __name__ == "__main__":
    # Test execution
    input_logs_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\INPUT_LOGS"
    output_logs_dir = r"c:\Users\Guruchandar\Downloads\insiEDR project\InsiEDR\latest_data\raw_logs"
    preprocess_logs(input_logs_dir, output_logs_dir, limit_users=['U0001', 'U0002'])
