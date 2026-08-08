import database as db
import pandas as pd
import time
import os

def test_and_populate():
    print("[INFO] Initializing SQLite database...")
    db.init_db()
    
    # Check if there are already records
    df_existing, count = db.get_clients_dataframe()
    if count >= 1500:
        print(f"[SUCCESS] Database already contains {count} records. Skipping population.")
        return
        
    print(f"[INFO] Wiping old data and populating 1,500 mock clients...")
    db.clear_all_clients()
    
    # Generate 1,500 mock clients
    mock_data = []
    categories = ["VIP", "Retail", "Corporate", "Wholesale", "Lead"]
    
    for i in range(1, 1501):
        client_id = f"TPA-{i:04d}"
        name = f"Client {i}"
        phone = f"9198765{i:05d}"
        category = categories[i % len(categories)]
        status = "Active" if i % 10 != 0 else "Inactive"  # 10% inactive
        
        mock_data.append({
            "client_id": client_id,
            "name": name,
            "phone": phone,
            "category": category,
            "status": status
        })
        
    # Convert to DataFrame and bulk import
    df = pd.DataFrame(mock_data)
    
    start_time = time.time()
    result = db.bulk_import(df, default_country_code="91")
    end_time = time.time()
    
    print(f"[RESULT] Bulk Import Summary:")
    print(f"   - Successfully imported: {result['success']} records")
    print(f"   - Failed records: {result['failed']}")
    print(f"   - Execution time: {round(end_time - start_time, 4)} seconds")
    
    # Test paginated query
    print("[INFO] Testing paginated query speed...")
    q_start = time.time()
    df_page, total = db.get_clients_dataframe(search_query="Client 123", limit=50, offset=0)
    q_end = time.time()
    
    print(f"[RESULT] Search results for 'Client 123' (Total: {total}):")
    print(df_page)
    print(f"[SUCCESS] Query response time: {round(q_end - q_start, 6)} seconds")
    
if __name__ == "__main__":
    test_and_populate()
