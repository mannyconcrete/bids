def get_project_locations(self, project_name):
    """Get all locations for a project"""
    try:
        self.cursor.execute("""
            SELECT address, status, coordinates, notes, date_added 
            FROM project_locations 
            WHERE project_name = ?
        """, (project_name,))
        locations = self.cursor.fetchall()
        
        # Convert to list of dictionaries
        return [{
            'address': loc[0],
            'status': loc[1],
            'coordinates': json.loads(loc[2]) if loc[2] else None,
            'notes': loc[3],
            'date_added': loc[4]
        } for loc in locations]
    except Exception as e:
        print(f"Error getting project locations: {str(e)}")
        return []

def add_project_location(self, project_name, location_data):
    """Add a new location to a project"""
    try:
        self.cursor.execute("""
            INSERT INTO project_locations 
            (project_name, address, status, coordinates, notes, date_added)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            project_name,
            location_data['address'],
            location_data['status'],
            json.dumps(location_data['coordinates']),
            location_data.get('notes', ''),
            location_data.get('date_added', datetime.now().strftime("%Y-%m-%d"))
        ))
        self.conn.commit()
        return True
    except Exception as e:
        print(f"Error adding project location: {str(e)}")
        return False

def update_project_location_status(self, project_name, location_address, new_status):
    """Update the status of a location"""
    try:
        self.cursor.execute("""
            UPDATE project_locations 
            SET status = ? 
            WHERE project_name = ? AND address = ?
        """, (new_status, project_name, location_address))
        self.conn.commit()
        return True
    except Exception as e:
        print(f"Error updating location status: {str(e)}")
        return False

def update_project_location_notes(self, project_name, location_address, new_notes):
    """Update the notes for a location"""
    try:
        self.cursor.execute("""
            UPDATE project_locations 
            SET notes = ? 
            WHERE project_name = ? AND address = ?
        """, (new_notes, project_name, location_address))
        self.conn.commit()
        return True
    except Exception as e:
        print(f"Error updating location notes: {str(e)}")
        return False

def delete_project_location(self, project_name, location_address):
    """Delete a location from a project"""
    try:
        self.cursor.execute("""
            DELETE FROM project_locations 
            WHERE project_name = ? AND address = ?
        """, (project_name, location_address))
        self.conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting location: {str(e)}")
        return False

def __init__(self):
    """Initialize the database"""
    try:
        self.conn = sqlite3.connect('bid_tracker.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create tables if they don't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT,
                address TEXT,
                status TEXT,
                coordinates TEXT,
                notes TEXT,
                date_added TEXT,
                UNIQUE(project_name, address)
            )
        """)
        self.conn.commit()
        
        # ... rest of your existing initialization code ...
        
    except Exception as e:
        print(f"Database initialization error: {str(e)}")
